"""
LLM Recommendation Evaluation Module.
Evaluates schema validity, required fields, formatting recovery (markdown fences),
timeout resiliency, rate-limit recovery, and deterministic database fallback behavior.
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from eval.dataset import EvaluationDataset
from eval.metrics import validate_recommendation_schema
from modules.practice.routes import extract_json_from_ai, get_fallback_sentences
from app import create_app


def evaluate_llm_pipeline(dataset: EvaluationDataset) -> Dict[str, Any]:
    """
    Run comprehensive evaluation on the practice recommendation pipeline:
    1. Schema compliance on simulated and live recommendation structures
    2. Edge case recovery (markdown fences, malformed responses)
    3. Deterministic database fallback reliability
    """
    app = create_app()
    test_client = app.test_client()

    case_results = []
    schema_passes = 0
    total_cases = 0

    # 1. Evaluate Standard Recommendation Flows
    for case in dataset.llm_cases:
        total_cases += 1
        case_id = case["id"]
        weak_phonemes = ",".join(case["weak_phonemes"])
        weak_words = ",".join(case["weak_words"])

        # Invoke recommendation endpoint
        url = f"/practice/recommendation?weak_phonemes={weak_phonemes}&weak_words={weak_words}"
        res = test_client.get(url)
        status_code = res.status_code
        data = res.get_json(silent=True) or {}

        is_valid_schema, schema_errors = validate_recommendation_schema(data)
        if is_valid_schema and status_code == 200:
            schema_passes += 1

        case_results.append({
            "case_id": case_id,
            "name": case.get("name"),
            "status_code": status_code,
            "source": data.get("source"),
            "is_valid_schema": is_valid_schema,
            "schema_errors": schema_errors,
            "sentence_count": len(data.get("sentences", [])) if isinstance(data.get("sentences"), list) else 0
        })

    # 2. Evaluate Robustness Edge Cases
    edge_results = []
    edge_passes = 0

    for edge in dataset.llm_edge_cases:
        edge_id = edge["id"]
        edge_type = edge["type"]
        passed = False
        diagnostic = ""

        if edge_type == "format_recovery":
            # Test markdown code block extraction
            raw_ai = edge.get("simulated_raw", "")
            extracted = extract_json_from_ai(raw_ai)
            is_valid, errors = validate_recommendation_schema(extracted)
            passed = is_valid
            diagnostic = f"Parsed {len(extracted.get('sentences', [])) if isinstance(extracted, dict) else 0} sentences. Errors: {errors}"

        elif edge_type in ("timeout", "rate_limit", "json_parse_error"):
            # Test fallback determinism with database sentences
            with app.app_context():
                fallback = get_fallback_sentences()
                is_valid = isinstance(fallback, list) and len(fallback) == 3
                has_fields = all("text" in s and "difficulty" in s for s in fallback if isinstance(s, dict))
                passed = is_valid and has_fields
                diagnostic = f"Fallback generated {len(fallback)} sentences with valid fields: {has_fields}"

        if passed:
            edge_passes += 1

        edge_results.append({
            "edge_id": edge_id,
            "name": edge.get("name"),
            "passed": passed,
            "diagnostic": diagnostic
        })

    total_evaluated = total_cases + len(dataset.llm_edge_cases)
    total_passed = schema_passes + edge_passes
    compliance_rate = round(total_passed / total_evaluated, 4) if total_evaluated > 0 else 0.0

    return {
        "dataset_version": dataset.version,
        "standard_cases_evaluated": total_cases,
        "standard_schema_passes": schema_passes,
        "edge_cases_evaluated": len(dataset.llm_edge_cases),
        "edge_cases_passed": edge_passes,
        "overall_compliance_rate": compliance_rate,
        "standard_results": case_results,
        "edge_results": edge_results
    }
