from flask import Blueprint, request, jsonify, current_app
import json
from werkzeug.utils import secure_filename
import os
import time
import numpy as np
import requests
import re
from extensions import db
from modules.sentences.models import Sentence
from modules.assessments.services import (
    calculate_phoneme_accuracy,
    calculate_word_level_accuracy,
    calculate_fluency
)
from modules.observability.metrics import metrics_collector
import random
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

routes_bp = Blueprint('practice', __name__)

ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a", "webm", "ogg", "mp4"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_to_native_types(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    """
    if np is not None:
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
    if isinstance(obj, dict):
        return {key: convert_to_native_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_native_types(item) for item in obj)
    return obj


def extract_json_from_ai(text):
    """
    Safely extract JSON object from AI completion that may include markdown backticks.
    """
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return None


def get_fallback_sentences():
    """Fetch 3 random sentences from the database or fall back to defaults"""
    try:
        from sqlalchemy import inspect
        engine = db.engine
        inspector = inspect(engine)
        if inspector.has_table("sentences"):
            sentences = Sentence.query.order_by(db.func.random()).limit(3).all()
            if sentences and len(sentences) >= 3:
                return [
                    {
                        "text": s.text,
                        "difficulty": s.difficulty or "medium"
                    }
                    for s in sentences[:3]
                ]
    except Exception as e:
        if current_app:
            current_app.logger.warning(f"Database fallback query failed: {e}")

    return [
        {"text": "The quick brown fox jumps over the lazy dog.", "difficulty": "easy"},
        {"text": "She sells seashells by the seashore.", "difficulty": "medium"},
        {"text": "Peter Piper picked a peck of pickled peppers.", "difficulty": "hard"}
    ]


@routes_bp.route('/recommendation', methods=['GET', 'POST'])
@routes_bp.route('/recommend', methods=['GET', 'POST'])
@routes_bp.route('/recomond', methods=['GET', 'POST'])
def recommend_practice_sentences():
    body = request.get_json(silent=True) or {} if request.is_json or request.method == 'POST' else {}

    weak_phonemes = (
        request.args.get('weak_phonemes')
        or request.args.get('weeak_phonemes')
        or body.get('weak_phonemes')
        or body.get('weeak_phonemes')
        or ''
    )
    weak_words = (
        request.args.get('weak_words')
        or body.get('weak_words')
        or ''
    )

    if isinstance(weak_phonemes, list):
        phoneme_list = [str(p).strip() for p in weak_phonemes if str(p).strip()]
    else:
        phoneme_list = [p.strip() for p in str(weak_phonemes).split(',') if p.strip()]

    if isinstance(weak_words, list):
        weak_words_str = ", ".join(str(w) for w in weak_words if str(w).strip())
    else:
        weak_words_str = str(weak_words)

    # If OpenRouter is not configured, immediately return curated database sentences
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.strip() == "":
        metrics_collector.record_llm_fallback("not_configured")
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "fallback": True,
            "fallback_reason": "AI service not configured",
            "note": "AI service not configured, using database practice sentences"
        }), 200

    prompt = f"""
    Generate EXACTLY THREE English practice sentences (10–15 words each) for speech therapy.

    Focus more on these weak phonemes if possible: {phoneme_list}
    The user struggles with these words: {weak_words_str}

    Return ONLY valid JSON in this exact format:
    {{
      "sentences": [
        {{"text": "", "difficulty": ""}},
        {{"text": "", "difficulty": ""}},
        {{"text": "", "difficulty": ""}}
      ]
    }}

    Difficulty must be easy, medium, or hard.
    """.strip()

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 300
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "Content-Type": "application/json"
    }

    # Bounded retries with exponential backoff & jitter for transient failures
    max_retries = 2
    base_delay = 0.5
    response = None
    parsed = None
    fallback_reason = None
    start_llm = time.time()

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=15
            )

            # Check for transient rate limit or gateway error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < max_retries:
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0.1, 0.3)
                    time.sleep(delay)
                    continue
                else:
                    response.raise_for_status()
            elif response.status_code >= 400:
                # Permanent client error (400, 401, 403) -> do not retry
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = extract_json_from_ai(content)
            break
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                delay = (base_delay * (2 ** attempt)) + random.uniform(0.1, 0.3)
                time.sleep(delay)
                continue
            fallback_reason = "provider_timeout"
        except requests.exceptions.HTTPError as he:
            fallback_reason = f"http_{response.status_code}" if response is not None else "http_error"
        except Exception as e:
            fallback_reason = str(e)
            break

    llm_duration = time.time() - start_llm

    if parsed is None:
        metrics_collector.record_llm_request("failed", llm_duration)
        metrics_collector.record_llm_fallback(fallback_reason or "unknown_failure")
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "fallback": True,
            "fallback_reason": fallback_reason or "AI service unavailable",
            "note": "AI service unavailable, using database sentences"
        }), 200

    sentences = parsed.get("sentences") if isinstance(parsed, dict) else None
    if not isinstance(sentences, list) or len(sentences) != 3:
        metrics_collector.record_llm_request("schema_mismatch", llm_duration)
        metrics_collector.record_llm_fallback("invalid_format")
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "fallback": True,
            "fallback_reason": "AI returned unexpected structure",
            "note": "AI returned unexpected format"
        }), 200

    results = []
    for item in sentences:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "").strip()
        difficulty = str(item.get("difficulty", "medium")).lower()

        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        if text:
            results.append({
                "text": text,
                "difficulty": difficulty
            })

    if len(results) != 3:
        metrics_collector.record_llm_request("insufficient_count", llm_duration)
        metrics_collector.record_llm_fallback("insufficient_sentences")
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "fallback": True,
            "fallback_reason": "AI generated fewer than 3 valid sentences",
            "note": "AI returned insufficient sentences"
        }), 200

    metrics_collector.record_llm_request("success", llm_duration)
    return jsonify({
        "sentences": results,
        "source": "ai",
        "fallback": False
    }), 200


@routes_bp.route('/recommendationv2', methods=['GET'])
def recommend_practice_sentences_debug():
    weak_phonemes = request.args.get('weak_phonemes', '')
    weak_words = request.args.get('weak_words', '')

    phoneme_list = [p.strip() for p in weak_phonemes.split(',') if p.strip()]

    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.strip() == "":
        return jsonify({
            "error": "OpenRouter API key not configured"
        }), 500

    prompt = f"""
    Generate EXACTLY THREE English practice sentences (10-15 words each) for speech therapy.

    Focus more on these weak phonemes if possible: {phoneme_list}
    The user struggles with these words: {weak_words}

    Return ONLY valid JSON in this exact format:
    {{
      "sentences": [
        {{"text": "", "difficulty": ""}},
        {{"text": "", "difficulty": ""}},
        {{"text": "", "difficulty": ""}}
      ]
    }}

    Difficulty must be easy, medium, or hard.
    """.strip()

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 300
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
    except Exception as e:
        return jsonify({
            "error": "Request to OpenRouter failed",
            "exception": str(e)
        }), 500

    raw_text = None
    raw_json = None

    try:
        raw_json = response.json()
        raw_text = raw_json.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception as e:
        raw_text = f"Failed to parse JSON: {e}"

    return jsonify({
        "http_status": response.status_code,
        "model": payload["model"],
        "prompt_sent": prompt,
        "raw_ai_text": raw_text,
        "raw_openrouter_response": raw_json
    }), 200


@routes_bp.route('/submit', methods=['POST'])
def submit_practice_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file in the request"}), 400

    file = request.files['audio']
    sentence_id = request.form.get('sentence_id')

    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        timestamp = int(time.time())
        filename = f"practice_audio_{timestamp}{ext}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        phoneme_details = calculate_phoneme_accuracy(file_path)
        word_details = calculate_word_level_accuracy(file_path)
        fluency_score = calculate_fluency(file_path)

        phoneme_details = convert_to_native_types(phoneme_details)
        word_details = convert_to_native_types(word_details)
        fluency_score = convert_to_native_types(fluency_score)

        phoneme_accuracy_avg = 0
        if isinstance(phoneme_details, list) and len(phoneme_details) > 0:
            phoneme_scores = [
                p.get('score', 0)
                for p in phoneme_details
                if isinstance(p, dict) and 'score' in p
            ]
            if phoneme_scores:
                phoneme_accuracy_avg = sum(phoneme_scores) / len(phoneme_scores)

        word_accuracy_avg = 0
        if isinstance(word_details, list) and len(word_details) > 0:
            word_scores = [
                w.get('score', 0)
                for w in word_details
                if isinstance(w, dict) and 'score' in w
            ]
            if word_scores:
                word_accuracy_avg = sum(word_scores) / len(word_scores)

        try:
            from modules.assessments.services import weak_phonemes as get_weak
            weak_phonemes_list = get_weak(file_path)
            weak_phonemes_list = convert_to_native_types(weak_phonemes_list)
        except Exception:
            weak_phonemes_list = []

        return jsonify({
            "message": "Practice submission evaluated",
            "data": {
                "sentence_id": sentence_id,
                "phoneme_accuracy": round(phoneme_accuracy_avg, 2),
                "word_accuracy": round(word_accuracy_avg, 2),
                "fluency_score": round(fluency_score, 2) if isinstance(fluency_score, (int, float)) else fluency_score,
                "weak_phonemes": weak_phonemes_list or [],
                "details": {
                    "phoneme_details": phoneme_details,
                    "word_details": word_details
                }
            }
        }), 201

    return jsonify({"error": f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400
