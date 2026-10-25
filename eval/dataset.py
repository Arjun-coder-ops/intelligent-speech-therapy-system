"""
Versioned evaluation dataset loader and schema manager.
Loads test fixtures, reference transcripts, and evaluation parameters.
"""
import json
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_PATH = ROOT_DIR / "eval" / "data" / "v1" / "dataset.json"


class EvaluationDataset:
    def __init__(self, dataset_path: Path = DEFAULT_DATASET_PATH):
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Evaluation dataset not found at: {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    @property
    def version(self) -> str:
        return self._data.get("version", "unknown")

    @property
    def speech_samples(self) -> List[Dict[str, Any]]:
        return self._data.get("speech_evaluation_samples", [])

    @property
    def llm_cases(self) -> List[Dict[str, Any]]:
        return self._data.get("llm_evaluation_test_cases", [])

    @property
    def llm_edge_cases(self) -> List[Dict[str, Any]]:
        return self._data.get("llm_edge_cases", [])

    def get_sample_by_id(self, sample_id: str) -> Dict[str, Any]:
        for s in self.speech_samples:
            if s.get("id") == sample_id:
                return s
        raise KeyError(f"Sample with id '{sample_id}' not found in dataset")


def load_dataset(dataset_path: Path = DEFAULT_DATASET_PATH) -> EvaluationDataset:
    return EvaluationDataset(dataset_path)
