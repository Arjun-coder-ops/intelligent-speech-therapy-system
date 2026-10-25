"""
Tests for AI Evaluation and Regression Testing Pipeline.
Covers metrics (WER, CER, schema validation), dataset loader, and evaluation helpers.
"""
import unittest
import json
from pathlib import Path

from eval.metrics import calculate_wer, calculate_cer, validate_recommendation_schema
from eval.dataset import load_dataset, EvaluationDataset


class TestAIEvaluationPipeline(unittest.TestCase):
    def test_wer_exact_match(self):
        ref = "the quick brown fox"
        hyp = "the quick brown fox"
        res = calculate_wer(ref, hyp)
        self.assertEqual(res["wer"], 0.0)
        self.assertEqual(res["substitutions"], 0)
        self.assertEqual(res["deletions"], 0)
        self.assertEqual(res["insertions"], 0)

    def test_wer_substitutions_and_deletions(self):
        ref = "the red rabbit ran"
        hyp = "the red hare"  # rabbit -> hare (sub), ran deleted (del)
        res = calculate_wer(ref, hyp)
        self.assertGreater(res["wer"], 0.0)
        self.assertEqual(res["substitutions"], 1)
        self.assertEqual(res["deletions"], 1)

    def test_wer_insertions(self):
        ref = "the dog barked"
        hyp = "the big noisy dog barked"
        res = calculate_wer(ref, hyp)
        self.assertEqual(res["insertions"], 2)
        self.assertGreater(res["wer"], 0.0)

    def test_wer_empty_strings(self):
        self.assertEqual(calculate_wer("", "")["wer"], 0.0)
        self.assertEqual(calculate_wer("hello", "")["wer"], 1.0)
        self.assertEqual(calculate_wer("", "hello")["wer"], 1.0)

    def test_cer_calculation(self):
        ref = "apple"
        hyp = "aple"  # 1 deletion
        res = calculate_cer(ref, hyp)
        self.assertAlmostEqual(res["cer"], 0.2, places=2)
        self.assertEqual(res["ref_chars"], 5)

    def test_schema_validator_valid(self):
        valid_rec = {
            "sentences": [
                {"text": "The red rabbit hopped across the field.", "difficulty": "easy"},
                {"text": "Rivers run rapidly through rugged rocks.", "difficulty": "medium"},
                {"text": "Rarely roar without remarkable resonance.", "difficulty": "hard"}
            ]
        }
        is_valid, errors = validate_recommendation_schema(valid_rec, expected_count=3)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_schema_validator_invalid_types_and_missing(self):
        invalid_rec = {
            "sentences": "not a list"
        }
        is_valid, errors = validate_recommendation_schema(invalid_rec)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_dataset_loader(self):
        dataset_path = Path(__file__).resolve().parent.parent / "eval" / "data" / "v1" / "dataset.json"
        dataset = load_dataset(dataset_path)
        self.assertIsInstance(dataset, EvaluationDataset)
        self.assertEqual(dataset.version, "1.0.0")
        self.assertGreaterEqual(len(dataset.speech_samples), 10)
        self.assertGreaterEqual(len(dataset.llm_cases), 5)


if __name__ == "__main__":
    unittest.main()
