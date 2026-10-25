"""
Tests for Reliable and Observable AI Inference Pipeline.
Covers:
- ThreadSafeAudioLRUCache operations, eviction, and concurrent access
- SpeechAssessmentModel thread-safe singleton lock and status
- Observability metrics registry (Prometheus counters, gauges, histograms)
- /metrics and /health/detailed endpoints
- Resilient LLM fallback tagging
"""
import sys
import unittest
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model_interface import ThreadSafeAudioLRUCache, SpeechTherapyModel, get_model_status, clear_model_cache
from modules.observability.metrics import MetricsCollector, metrics_collector
from app import create_app
from extensions import db
from modules.sentences.models import Sentence


class TestInferenceReliability(unittest.TestCase):
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
            # Seed test sentences
            s1 = Sentence(text="Practice test sentence for phonemes.", source_type="practice", difficulty="medium")
            db.session.add(s1)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_lru_cache_basic_and_eviction(self):
        cache = ThreadSafeAudioLRUCache(capacity=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.size(), 3)

        # Inserting 4th item should evict the least recently used ("c" was accessed least recently since "a" and "b" were get'd)
        cache.set("d", 4)
        self.assertIsNone(cache.get("c"))
        self.assertEqual(cache.get("d"), 4)
        self.assertEqual(cache.size(), 3)

        cache.clear()
        self.assertEqual(cache.size(), 0)
        self.assertIsNone(cache.get("a"))

    def test_lru_cache_concurrency(self):
        cache = ThreadSafeAudioLRUCache(capacity=50)
        errors = []

        def worker(start_idx):
            try:
                for i in range(100):
                    key = f"key_{start_idx}_{i % 20}"
                    cache.set(key, {"value": i})
                    val = cache.get(key)
                    if val is not None and val["value"] != i:
                        errors.append("Value mismatch")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertLessEqual(cache.size(), 50)

    def test_model_status_and_singleton(self):
        status = get_model_status()
        self.assertIn("status", status)
        self.assertIn("cache_size", status)
        self.assertIn("cache_capacity", status)
        self.assertIn("max_concurrent_inferences", status)
        self.assertEqual(status["cache_capacity"], 100)
        self.assertEqual(status["max_concurrent_inferences"], 2)

    def test_metrics_registry(self):
        reg = MetricsCollector()
        reg.record_request("POST", "/test/metrics", 200, 0.05)
        reg.record_inference(0.12, status="success")
        reg.record_llm_request(status="success", duration_seconds=1.2)
        reg.record_llm_fallback(reason="timeout")
        reg.record_job_status(1)

        summary = reg.get_summary()
        self.assertGreaterEqual(summary["total_http_requests"], 1)
        self.assertIn("ai_inference", summary)
        self.assertIn("llm", summary)

        prom_text = reg.generate_prometheus_exposition()
        self.assertIn("speechtherapy_http_requests_total", prom_text)
        self.assertIn("speechtherapy_ai_inference_total", prom_text)
        self.assertIn("speechtherapy_llm_fallbacks_total", prom_text)
        self.assertIn("speechtherapy_active_background_jobs", prom_text)

    def test_metrics_endpoint(self):
        res = self.client.get("/metrics")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/plain", res.content_type)
        data = res.data.decode("utf-8")
        self.assertIn("speechtherapy_uptime_seconds", data)
        self.assertIn("speechtherapy_http_requests_total", data)

    def test_detailed_health_endpoint(self):
        res = self.client.get("/health/detailed")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("database", data)
        self.assertEqual(data["database"]["status"], "connected")
        self.assertIn("ai_engine", data)
        self.assertIn("metrics_summary", data)

    def test_llm_fallback_tagging(self):
        # When OpenRouter fails or is offline/unconfigured, recommendation must return fallback: True
        payload = {
            "weak_words": ["rabbit", "river"],
            "weak_phonemes": ["r"]
        }
        res = self.client.post("/practice/recommendation", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("fallback") is True)
        self.assertEqual(data.get("source"), "database")
        self.assertIn("sentences", data)
        self.assertGreaterEqual(len(data["sentences"]), 1)
        self.assertIn("fallback_reason", data)


if __name__ == "__main__":
    unittest.main()
