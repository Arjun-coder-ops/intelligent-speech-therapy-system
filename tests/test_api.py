"""
API integration test suite for the Intelligent Speech Therapy Platform.
Tests authentication, sentences, assessments, practice recommendations, and history.
Usage: python tests/test_api.py
"""
import sys
import unittest
import json
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from modules.auth.models import users
from modules.sentences.models import Sentence
from modules.assessments.models import AudioRecord


class TestSpeechTherapyAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.create_all()
            # Add initial sentences
            s1 = Sentence(text="The red rabbit ran around the river.", source_type="assessment", difficulty="easy")
            s2 = Sentence(text="She sells seashells by the seashore.", source_type="practice", difficulty="medium")
            db.session.add_all([s1, s2])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_01_home_endpoint(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "online")
        self.assertIn("endpoints", data)

    def test_02_register_user(self):
        payload = {
            "fullName": "Test Therapist",
            "email": "therapist@example.com",
            "password": "Password123!",
            "confirmPassword": "Password123!"
        }
        res = self.client.post("/auth/register", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "therapist@example.com")
        self.assertEqual(data["user"]["fullName"], "Test Therapist")

    def test_03_login_user(self):
        payload = {
            "email": "therapist@example.com",
            "password": "Password123!"
        }
        res = self.client.post("/auth/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("isLoggedIn"))
        self.assertIn("token", data)
        TestSpeechTherapyAPI.token = data["token"]
        TestSpeechTherapyAPI.user_id = data["id"]

    def test_04_me_endpoint(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = self.client.get("/auth/me", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "therapist@example.com")
        self.assertEqual(data["user"]["fullName"], "Test Therapist")
        self.assertEqual(data["user"]["name"], "Test Therapist")

    def test_05_get_sentences(self):
        res = self.client.get("/sentences")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)

    def test_06_get_sentence_by_id(self):
        res = self.client.get("/sentences/1")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("id"), 1)
        self.assertIn("text", data)

    def test_07_add_sentence(self):
        payload = {
            "sentence": "A quick brown dog.",
            "source_type": "practice",
            "difficulty": "easy"
        }
        res = self.client.post("/sentences", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertIn("id", data)

    def test_08_assessment_recommend(self):
        res = self.client.get(f"/assessment/recommend?user_id={self.user_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("sentence_id", data)
        self.assertIn("text", data)

    def test_09_practice_recommendation(self):
        res = self.client.get("/practice/recommendation?weak_phonemes=S,SH,TH&weak_words=seashore,think")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("sentences", data)
        self.assertEqual(len(data["sentences"]), 3)

    def test_10_history_endpoint(self):
        # Create a mock AudioRecord
        with self.app.app_context():
            rec = AudioRecord(
                user_id=self.user_id,
                sentence_id=1,
                file_path="uploads/test.wav",
                phoneme_accuracy=88.5,
                word_accuracy=92.0,
                fluency_score=85.0,
                weak_phonemes=["R"],
                weak_words=["river"]
            )
            db.session.add(rec)
            db.session.commit()

        res = self.client.get(f"/history/prev_res?user_id={self.user_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("response", data)
        self.assertEqual(len(data["response"]), 1)
        self.assertEqual(data["response"][0]["word_accuracy"], 92.0)
        self.assertEqual(data["response"][0]["weak_phonemes"], ["R"])


if __name__ == "__main__":
    unittest.main()
