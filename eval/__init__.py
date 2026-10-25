"""
AI Evaluation and Regression Testing Package for Intelligent Speech Therapy Platform.
Provides reproducible evaluation for speech recognition, pronunciation scoring,
and LLM-based practice recommendations.
"""

from .metrics import calculate_wer, calculate_cer, validate_recommendation_schema
from .dataset import EvaluationDataset

__all__ = [
    "calculate_wer",
    "calculate_cer",
    "validate_recommendation_schema",
    "EvaluationDataset"
]
