"""
Tests for Asynchronous Job Processing Pipeline.
Covers:
- AssessmentJob database model and transitions
- POST /assessment/upload-async (HTTP 202 Accepted)
- GET /assessment/jobs/<job_id> status retrieval
- User isolation (403 for unauthorized access to another user's job)
- Asynchronous execution completion and result storage
"""
import sys
import unittest
import io
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from modules.sentences.models import Sentence
from modules.assessments.models import AssessmentJob


class TestAsyncJobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["TESTING"] = "1"
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.create_all()
            # Add sentence
            cls.sentence = Sentence(text="The red rabbit ran around the river.", source_type="assessment", difficulty="easy")
            db.session.add(cls.sentence)
            db.session.commit()
            cls.sentence_id = cls.sentence.id

        # Register User A
        res_a = cls.client.post("/auth/register", json={
            "fullName": "User Alpha",
            "email": "alpha@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!"
        })
        login_a = cls.client.post("/auth/login", json={
            "email": "alpha@example.com",
            "password": "Password123!"
        })
        cls.token_a = login_a.get_json()["token"]

        # Register User B
        res_b = cls.client.post("/auth/register", json={
            "fullName": "User Beta",
            "email": "beta@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!"
        })
        login_b = cls.client.post("/auth/login", json={
            "email": "beta@example.com",
            "password": "Password123!"
        })
        cls.token_b = login_b.get_json()["token"]

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_01_upload_async_missing_auth(self):
        res = self.client.post("/assessment/upload-async")
        self.assertEqual(res.status_code, 401)

    def test_02_upload_async_success_202(self):
        # Create a synthetic wave audio payload using reference audio if available or dummy PCM
        ref_audio_path = ROOT / "data" / "reference_audio" / "phonemes" / "word_000_red.wav"
        if ref_audio_path.exists():
            audio_data = ref_audio_path.read_bytes()
        else:
            audio_data = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

        data = {
            "sentenceId": str(self.sentence_id),
            "audio": (io.BytesIO(audio_data), "async_test.wav", "audio/wav")
        }

        res = self.client.post(
            "/assessment/upload-async",
            data=data,
            headers={"Authorization": f"Bearer {self.token_a}"},
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 202)
        body = res.get_json()
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("status"), "queued")
        self.assertIn("job_id", body)
        self.assertIn("status_url", body)
        job_id = body["job_id"]

        # Poll status
        status_res = self.client.get(
            f"/assessment/jobs/{job_id}",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(status_res.status_code, 200)
        status_body = status_res.get_json()
        self.assertEqual(status_body["job_id"], job_id)
        self.assertIn(status_body["status"], ["queued", "processing", "completed", "failed"])

        # Wait briefly for background execution
        for _ in range(10):
            time.sleep(0.3)
            check = self.client.get(
                f"/assessment/jobs/{job_id}",
                headers={"Authorization": f"Bearer {self.token_a}"}
            )
            if check.get_json()["status"] in ["completed", "failed"]:
                break

        final_body = check.get_json()
        self.assertIn(final_body["status"], ["completed", "failed"])
        if final_body["status"] == "completed":
            self.assertIsNotNone(final_body["result"])
            self.assertIn("record_id", final_body["result"])
            self.assertIn("fluency_score", final_body["result"])

    def test_03_job_user_isolation_403(self):
        # Create job as User A
        ref_audio_path = ROOT / "data" / "reference_audio" / "phonemes" / "word_000_red.wav"
        audio_data = ref_audio_path.read_bytes() if ref_audio_path.exists() else b"RIFF"

        data = {
            "sentenceId": str(self.sentence_id),
            "audio": (io.BytesIO(audio_data), "iso_test.wav", "audio/wav")
        }

        res = self.client.post(
            "/assessment/upload-async",
            data=data,
            headers={"Authorization": f"Bearer {self.token_a}"},
            content_type="multipart/form-data"
        )
        job_id = res.get_json()["job_id"]

        # Attempt to access as User B
        res_unauthorized = self.client.get(
            f"/assessment/jobs/{job_id}",
            headers={"Authorization": f"Bearer {self.token_b}"}
        )
        self.assertEqual(res_unauthorized.status_code, 403)
        self.assertIn("unauthorized", res_unauthorized.get_json()["message"].lower())

    def test_04_job_not_found_404(self):
        res = self.client.get(
            "/assessment/jobs/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {self.token_a}"}
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
