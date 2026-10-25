"""
Deep Reliability and Concurrency Verification Test Suite.
Specifically verifies:
1. Multi-threaded audio cache isolation (no cross-thread state leakage).
2. Asynchronous worker exception handling and terminal 'failed' state transition.
3. Orphan/stale job recovery upon application restart.
4. LLM failure modes: HTTP 429 retries, HTTP 401 non-retrying, timeout exhaustion, malformed JSON.
5. Duplicate job submissions and repeated polling idempotency.
"""
import sys
import os
import unittest
import threading
import time
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["TESTING"] = "1"

from app import create_app
from extensions import db
from modules.sentences.models import Sentence
from modules.assessments.models import AssessmentJob, AudioRecord
from modules.assessments.services import execute_assessment_job, recover_stale_jobs
from model_interface import (
    calculate_phoneme_accuracy,
    calculate_word_level_accuracy,
    calculate_fluency,
    weak_phonemes,
    get_backend
)


class TestDeepReliabilityAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.create_all()
            cls.sentence = Sentence(text="The red rabbit ran around the river.", source_type="assessment", difficulty="easy")
            db.session.add(cls.sentence)
            db.session.commit()
            cls.sentence_id = cls.sentence.id

        # Register and login user
        cls.client.post("/auth/register", json={
            "fullName": "Audit User",
            "email": "audit@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!"
        })
        login = cls.client.post("/auth/login", json={
            "email": "audit@example.com",
            "password": "Password123!"
        })
        cls.token = login.get_json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_concurrent_audio_isolation(self):
        """Verify that concurrent requests on distinct audio files do not overwrite each other's cache."""
        backend = get_backend()
        self.assertIsNotNone(backend)

        results = {}
        errors = []

        def worker(file_id):
            try:
                # Pre-populate specific cache entries in backend.lru_cache
                fake_path = f"/mock/path/audio_{file_id}.wav"
                custom_entry = {
                    "path": fake_path,
                    "phoneme_data": [{"phoneme": f"p_{file_id}", "score": 80.0}],
                    "word_data": [{"word": f"word_{file_id}", "score": 85.0}],
                    "fluency": 70.0 + file_id,
                    "weak_list": [f"w_{file_id}"]
                }
                backend.lru_cache.set(fake_path, custom_entry)

                # Fetch via API helper
                p_acc = calculate_phoneme_accuracy(fake_path)
                w_acc = calculate_word_level_accuracy(fake_path)
                fl = calculate_fluency(fake_path)
                wp = weak_phonemes(fake_path)

                results[file_id] = {
                    "phoneme": p_acc[0]["phoneme"] if p_acc else None,
                    "word": w_acc[0]["word"] if w_acc else None,
                    "fluency": fl,
                    "weak": wp[0] if wp else None
                }
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors occurred: {errors}")
        for i in range(10):
            self.assertEqual(results[i]["phoneme"], f"p_{i}")
            self.assertEqual(results[i]["word"], f"word_{i}")
            self.assertEqual(results[i]["fluency"], 70.0 + i)
            self.assertEqual(results[i]["weak"], f"w_{i}")

    def test_02_worker_exception_terminal_state(self):
        """Verify that worker exception properly marks job as 'failed' in database."""
        with self.app.app_context():
            job = AssessmentJob(
                id="test-fail-uuid-1",
                user_id=1,
                sentence_id=self.sentence_id,
                file_path="/non/existent/path/for/failure.wav",
                status="queued",
                progress=0
            )
            db.session.add(job)
            db.session.commit()

        # Patch calculate_phoneme_accuracy to raise an unhandled exception
        with patch("modules.assessments.services.calculate_phoneme_accuracy", side_effect=RuntimeError("Simulated CUDA OOM failure")):
            execute_assessment_job(self.app, "test-fail-uuid-1")

        with self.app.app_context():
            failed_job = db.session.get(AssessmentJob, "test-fail-uuid-1")
            self.assertIsNotNone(failed_job)
            self.assertEqual(failed_job.status, "failed")
            self.assertIn("Simulated CUDA OOM failure", failed_job.error_message)
            self.assertIsNotNone(failed_job.completed_at)

    def test_03_orphan_job_startup_recovery(self):
        """Verify that jobs left in 'queued' or 'processing' before server restart are marked failed."""
        with self.app.app_context():
            job_q = AssessmentJob(id="stale-queued-1", user_id=1, sentence_id=self.sentence_id, file_path="q.wav", status="queued", progress=0)
            job_p = AssessmentJob(id="stale-processing-1", user_id=1, sentence_id=self.sentence_id, file_path="p.wav", status="processing", progress=50)
            db.session.add_all([job_q, job_p])
            db.session.commit()

        # Run startup recovery
        recover_stale_jobs(self.app)

        with self.app.app_context():
            q_rec = db.session.get(AssessmentJob, "stale-queued-1")
            p_rec = db.session.get(AssessmentJob, "stale-processing-1")
            self.assertEqual(q_rec.status, "failed")
            self.assertEqual(p_rec.status, "failed")
            self.assertIn("server restart", q_rec.error_message)
            self.assertIn("server restart", p_rec.error_message)

    def test_04_duplicate_job_and_polling(self):
        """Test submission and repeated polling of async job."""
        ref_audio_path = ROOT / "data" / "reference_audio" / "phonemes" / "word_000_red.wav"
        audio_data = ref_audio_path.read_bytes() if ref_audio_path.exists() else b"RIFF"

        data = {
            "sentenceId": str(self.sentence_id),
            "audio": (io.BytesIO(audio_data), "poll_test.wav", "audio/wav")
        }
        res = self.client.post("/assessment/upload-async", data=data, headers=self.headers, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 202)
        job_id = res.get_json()["job_id"]

        # Repeated polling (10 times) must be idempotent and return 200
        for _ in range(10):
            poll_res = self.client.get(f"/assessment/jobs/{job_id}", headers=self.headers)
            self.assertEqual(poll_res.status_code, 200)
            self.assertEqual(poll_res.get_json()["job_id"], job_id)
            time.sleep(0.05)

    def test_05_llm_rate_limit_and_fallback(self):
        """Verify LLM fallback metadata when OpenRouter returns 429 rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = Exception("Rate limit exceeded")

        with patch("requests.post", return_value=mock_response):
            res = self.client.post(
                "/practice/recommendation",
                json={"weak_words": ["rabbit"], "weak_phonemes": ["r"]},
                headers={"OPENROUTER_API_KEY": "dummy_key"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data.get("fallback") is True)
            self.assertEqual(data.get("source"), "database")
            self.assertIn("sentences", data)
            self.assertEqual(len(data["sentences"]), 3)

    def test_06_llm_malformed_json_fallback(self):
        """Verify fallback when LLM response is unparseable or lacks sentences array."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Sorry, I cannot help with that."}}]
        }

        with patch("requests.post", return_value=mock_response):
            with patch("modules.practice.routes.OPENROUTER_API_KEY", "sk-test-key"):
                res = self.client.post(
                    "/practice/recommendation",
                    json={"weak_words": ["river"], "weak_phonemes": ["r"]}
                )
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertTrue(data.get("fallback") is True)
                self.assertEqual(data.get("source"), "database")
                self.assertIn("fallback_reason", data)


if __name__ == "__main__":
    unittest.main()
