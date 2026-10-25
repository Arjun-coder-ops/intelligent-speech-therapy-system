"""
Speech Evaluation Module.
Evaluates Whisper transcription quality against ground truth references using
Word Error Rate (WER) and Character Error Rate (CER), and verifies pronunciation assessment outputs.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from eval.dataset import EvaluationDataset
from eval.metrics import calculate_wer, calculate_cer
from model_interface import get_backend, calculate_word_level_accuracy, calculate_phoneme_accuracy, calculate_fluency


def evaluate_speech_samples(dataset: EvaluationDataset) -> Dict[str, Any]:
    """
    Run speech evaluation across all samples in the versioned dataset.
    Returns aggregated metrics and per-sample diagnostics.
    """
    samples = dataset.speech_samples
    results = []
    total_wer = 0.0
    total_cer = 0.0
    processed_count = 0

    backend = get_backend()
    ai_available = backend is not None and getattr(backend, "align_model", None) is not None

    for sample in samples:
        sample_id = sample["id"]
        ref_text = sample["reference_text"]
        rel_path = sample["audio_path"]
        abs_path = ROOT_DIR / rel_path

        if not abs_path.exists():
            logging.warning("Audio file for %s does not exist at %s. Skipping.", sample_id, abs_path)
            continue

        # Get transcription hypothesis from model
        hyp_text = ""
        word_details = []
        phoneme_details = []
        fluency = 0

        try:
            word_details = calculate_word_level_accuracy(str(abs_path))
            phoneme_details = calculate_phoneme_accuracy(str(abs_path))
            fluency = calculate_fluency(str(abs_path))

            if word_details and isinstance(word_details, list):
                hyp_words = [w["word"] for w in word_details if isinstance(w, dict) and "word" in w]
                hyp_text = " ".join(hyp_words).strip()
            elif backend and hasattr(backend, "align_model") and backend.align_model:
                try:
                    res = backend.align_model.transcribe(str(abs_path))
                    hyp_text = getattr(res, "text", "").strip()
                except Exception:
                    hyp_text = ""
        except Exception as e:
            logging.exception("Error evaluating sample %s: %s", sample_id, e)
            hyp_text = ""

        # If model is running in fallback/mock mode without deep learning weights loaded,
        # note fallback execution to maintain evaluation integrity
        if not hyp_text and not ai_available:
            # Deterministic fallback evaluation representation
            hyp_text = ref_text  # Synthetic matching for architecture verification when torchaudio is absent

        wer_res = calculate_wer(ref_text, hyp_text)
        cer_res = calculate_cer(ref_text, hyp_text)

        total_wer += wer_res["wer"]
        total_cer += cer_res["cer"]
        processed_count += 1

        results.append({
            "sample_id": sample_id,
            "category": sample.get("category", "general"),
            "reference": ref_text,
            "hypothesis": hyp_text,
            "is_simulated": not ai_available,
            "wer": wer_res["wer"],
            "cer": cer_res["cer"],
            "substitutions": wer_res["substitutions"],
            "deletions": wer_res["deletions"],
            "insertions": wer_res["insertions"],
            "hits": wer_res["hits"],
            "phoneme_count": len(phoneme_details) if isinstance(phoneme_details, list) else 0,
            "fluency_score": fluency
        })

    mean_wer = round(total_wer / processed_count, 4) if processed_count > 0 else 0.0
    mean_cer = round(total_cer / processed_count, 4) if processed_count > 0 else 0.0
    accuracy = round(max(0.0, 1.0 - mean_wer), 4)

    return {
        "dataset_version": dataset.version,
        "samples_evaluated": processed_count,
        "ai_engine_active": ai_available,
        "evaluation_mode": "live_model_inference" if ai_available else "simulated_pipeline_verification",
        "evaluation_notice": "Real model inference active." if ai_available else "SIMULATED: Neural model weights (Whisper/Wav2Vec2) were not loaded in the test environment. Metrics verify pipeline calculation mechanics, NOT real neural transcription accuracy.",
        "mean_wer": mean_wer,
        "mean_cer": mean_cer,
        "word_accuracy": accuracy,
        "results": results
    }
