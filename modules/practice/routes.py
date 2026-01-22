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

from dotenv import load_dotenv
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


def convert_to_native_types(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_to_native_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_native_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_native_types(item) for item in obj)
    return obj


routes_bp = Blueprint('practice', __name__)
# practice sentence recommendation for the chosen weak phonemes


# @routes_bp.route('/recommendation', methods=['GET', 'POST'])
# def recommend_practice_sentences():
#     weak_phonemes = request.args.get('weak_phonemes', '')
#     weak_words = request.args.get('weak_words', '')

#     phoneme_list = [p.strip() for p in weak_phonemes.split(',') if p.strip()]

#     # 🔹 Helper function to get fallback sentences from database
#     def get_fallback_sentences():
#         """Fetch 3 random sentences from the database as fallback"""
#         try:
#             sentences = Sentence.query.order_by(
#                 db.func.random()).limit(3).all()
#             if sentences and len(sentences) >= 3:
#                 return [
#                     {
#                         "text": s.text,
#                         "difficulty": s.difficulty if hasattr(s, 'difficulty') and s.difficulty else "medium"
#                     }
#                     for s in sentences[:3]
#                 ]
#         except Exception as e:
#             current_app.logger.error(f"Database fallback failed: {e}")

#         # Ultimate fallback - hardcoded sentences
#         return [
#             {"text": "The quick brown fox jumps over the lazy dog.",
#                 "difficulty": "easy"},
#             {"text": "She sells seashells by the seashore.", "difficulty": "medium"},
#             {"text": "Peter Piper picked a peck of pickled peppers.", "difficulty": "hard"}
#         ]

#     # 🔹 Try AI service first, but use fallback if it fails
#     use_fallback = False
#     fallback_reason = None

#     if not OPENROUTER_API_KEY or OPENROUTER_API_KEY.strip() == "":
#         current_app.logger.warning(
#             "OpenRouter API key not configured, using database fallback")
#         use_fallback = True
#         fallback_reason = "AI service not configured"
#     else:
#         # 🔹 Build prompt
#         prompt = f"""
#         Generate EXACTLY THREE English practice sentences (8–15 words each) for speech therapy.

#         Focus more on these weak phonemes if possible: {phoneme_list}
#         The user struggles with these words: {weak_words}

#         Return ONLY valid JSON in this exact format:
#         {{
#           "sentences": [
#             {{"text": "", "difficulty": ""}},
#             {{"text": "", "difficulty": ""}},
#             {{"text": "", "difficulty": ""}}
#           ]
#         }}

#         Difficulty must be easy, medium, or hard.
#         """.strip()

#         payload = {
#             "model": "meta-llama/llama-3.3-70b-instruct:free",
#             "messages": [{"role": "user", "content": prompt}],
#             "temperature": 0.9,
#             "max_tokens": 300
#         }

#         headers = {
#             "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#             "Content-Type": "application/json"
#         }

#         try:
#             response = requests.post(
#                 "https://openrouter.ai/api/v1/chat/completions",
#                 json=payload,
#                 headers=headers,
#                 timeout=15
#             )
#             response.raise_for_status()  # Raise an error for bad status codes
#         except requests.exceptions.RequestException as e:
#             current_app.logger.warning(
#                 f"OpenRouter API request failed: {e}, using database fallback")
#             use_fallback = True
#             fallback_reason = "AI service unavailable (rate limit or network error)"

#         if not use_fallback:
#             # Parse the response
#             try:
#                 response_data = response.json()
#             except json.JSONDecodeError as e:
#                 current_app.logger.warning(
#                     f"Failed to parse OpenRouter response: {e}, using database fallback")
#                 use_fallback = True
#                 fallback_reason = "Invalid AI service response"

#         if not use_fallback:
#             # Check if response has the expected structure
#             if "choices" not in response_data:
#                 current_app.logger.warning(
#                     f"OpenRouter response missing 'choices' key, using database fallback")
#                 use_fallback = True
#                 fallback_reason = "Invalid AI service response format"
#             elif not response_data["choices"] or len(response_data["choices"]) == 0:
#                 current_app.logger.warning(
#                     f"OpenRouter response has empty choices, using database fallback")
#                 use_fallback = True
#                 fallback_reason = "AI service returned no results"

#         if not use_fallback:
#             # Extract content safely
#             try:
#                 content = response_data["choices"][0]["message"]["content"]
#             except (KeyError, IndexError) as e:
#                 current_app.logger.warning(
#                     f"Failed to extract content from OpenRouter response: {e}, using database fallback")
#                 use_fallback = True
#                 fallback_reason = "Invalid AI service response structure"

#         if not use_fallback:
#             # 🔹 Safe JSON extractor
#             def extract_json(text):
#                 match = re.search(r'\{[\s\S]*\}', text)
#                 if not match:
#                     return None
#                 try:
#                     return json.loads(match.group())
#                 except json.JSONDecodeError:
#                     return None

#             parsed = extract_json_from_ai(content)

#             if not parsed or "sentences" not in parsed:
#                 current_app.logger.warning(
#                     f"Invalid model response format. Raw content: {content}"
#                 )
#                 use_fallback = True
#                 fallback_reason = "AI service returned invalid format"
#             else:
#                 results = []

#                 for item in parsed.get("sentences", []):
#                     text = item.get("text", "").strip()
#                     if not text:
#                         continue

#                     difficulty = item.get("difficulty", "medium").lower()
#                     if difficulty not in ("easy", "medium", "hard"):
#                         difficulty = "medium"

#                     results.append({
#                         "text": text,
#                         "difficulty": difficulty
#                     })

#                 if len(results) != 3:
#                     current_app.logger.warning(
#                         f"AI returned {len(results)} sentences instead of 3"
#                     )
#                     use_fallback = True
#                     fallback_reason = "AI service returned insufficient sentences"
#                 else:
#                     return jsonify({
#                         "sentences": results,
#                         "source": "ai"
#                     }), 200

#     # 🔹 Use fallback sentences
#     fallback_sentences = get_fallback_sentences()
#     return jsonify({
#         "sentences": fallback_sentences,
#         "source": "database",
#         "note": fallback_reason or "Using database sentences"
#     }), 200

@routes_bp.route('/recommendation', methods=['GET'])
def recommend_practice_sentences():
    weak_phonemes = request.args.get('weak_phonemes', '')
    weak_words = request.args.get('weak_words', '')

    phoneme_list = [p.strip() for p in weak_phonemes.split(',') if p.strip()]

    # ---------------- FALLBACK ----------------
    def get_fallback_sentences():
        try:
            sentences = Sentence.query.order_by(
                db.func.random()).limit(3).all()
            if sentences and len(sentences) >= 3:
                return [
                    {
                        "text": s.text,
                        "difficulty": s.difficulty or "medium"
                    }
                    for s in sentences[:3]
                ]
        except Exception as e:
            current_app.logger.error(f"Database fallback failed: {e}")

        return [
            {"text": "The quick brown fox jumps over the lazy dog.",
                "difficulty": "easy"},
            {"text": "She sells seashells by the seashore.", "difficulty": "medium"},
            {"text": "Peter Piper picked a peck of pickled peppers.", "difficulty": "hard"}
        ]

    # ---------------- VALIDATION HELPERS ----------------
    def word_count_ok(text):
        return 10 <= len(text.split()) <= 15

    # ---------------- API KEY CHECK ----------------
    # print("API", OPENROUTER_API_KEY)
    # if not OPENROUTER_API_KEY:
    #     return jsonify({
    #         "sentences": get_fallback_sentences(),
    #         "source": "database",
    #         "note": "AI service not configured"
    #     }), 200

    # ---------------- PROMPT ----------------
    prompt = f"""
    Generate EXACTLY THREE English practice sentences (10–15 words each) for speech therapy.

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
        "temperature": 0.7,
        "max_tokens": 300
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # ---------------- OPENROUTER CALL ----------------
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as e:
        current_app.logger.warning(f"AI failed, fallback used: {e}")
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "note": "AI service unavailable"
        }), 200

    # ---------------- STRUCTURE VALIDATION ----------------
    sentences = parsed.get("sentences")
    if not isinstance(sentences, list) or len(sentences) != 3:
        return jsonify({
            "sentences": get_fallback_sentences(),
            "source": "database",
            "note": "AI returned invalid sentence count"
        }), 200

    # ---------------- FINAL SANITIZATION ----------------
    results = []
    for item in sentences:
        text = item.get("text", "").strip()
        difficulty = item.get("difficulty", "medium").lower()

        # if not text or not word_count_ok(text):
        #     return jsonify({
        #         "sentences": get_fallback_sentences(),
        #         "source": "database",
        #         "note": "AI sentence length invalid"
        #     }), 200

        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"

        results.append({
            "text": text,
            "difficulty": difficulty
        })

    # ---------------- SUCCESS ----------------
    return jsonify({
        "sentences": results,
        "source": "ai"
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
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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

    # 🔴 DO NOT raise_for_status() — we want to see raw response
    raw_text = None
    raw_json = None

    try:
        raw_json = response.json()
        raw_text = raw_json.get("choices", [{}])[0].get(
            "message", {}).get("content")
    except Exception as e:
        raw_text = f"Failed to parse JSON: {e}"

    return jsonify({
        "http_status": response.status_code,
        "model": payload["model"],
        "prompt_sent": prompt,
        "raw_ai_text": raw_text,
        "raw_openrouter_response": raw_json
    }), 200


# Submit practice audio and return assessment using existing services (no DB persistence by default)
ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@routes_bp.route('/submit', methods=['POST'])
def submit_practice_audio():
    # Expects multipart/form-data with 'audio' file and 'sentence_id' (and optional 'user_id')
    if 'audio' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['audio']
    sentence_id = request.form.get('sentence_id')

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        _, ext = os.path.splitext(file.filename)
        timestamp = int(time.time())
        filename = secure_filename(file.filename)
        filename = f"practice_audio_{timestamp}{ext}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Call assessment services - these return detailed arrays
        phoneme_details = calculate_phoneme_accuracy(file_path)
        word_details = calculate_word_level_accuracy(file_path)
        fluency_score = calculate_fluency(file_path)

        # Convert all numpy types to native Python types
        phoneme_details = convert_to_native_types(phoneme_details)
        word_details = convert_to_native_types(word_details)
        fluency_score = convert_to_native_types(fluency_score)

        # Calculate summary metrics from detailed results
        # phoneme_details is an array of {phoneme, score, word}
        # word_details is an array of {word, score, status}

        # Calculate average phoneme accuracy (for Sentence Accuracy)
        phoneme_accuracy_avg = 0
        if isinstance(phoneme_details, list) and len(phoneme_details) > 0:
            phoneme_scores = [p.get('score', 0)
                              for p in phoneme_details if isinstance(p, dict)]
            if phoneme_scores:
                phoneme_accuracy_avg = sum(
                    phoneme_scores) / len(phoneme_scores)

        # Calculate average word accuracy (for Overall Accuracy)
        word_accuracy_avg = 0
        if isinstance(word_details, list) and len(word_details) > 0:
            word_scores = [w.get('score', 0)
                           for w in word_details if isinstance(w, dict)]
            if word_scores:
                word_accuracy_avg = sum(word_scores) / len(word_scores)

        # Get weak phonemes
        try:
            from modules.assessments.services import weak_phonemes as get_weak
            weak_phonemes_list = get_weak(file_path)
            weak_phonemes_list = convert_to_native_types(weak_phonemes_list)
        except Exception:
            weak_phonemes_list = []

        # Return response with correct structure for frontend
        # Frontend expects:
        # - phoneme_accuracy (number) → displayed as "Sentence Accuracy"
        # - word_accuracy (number) → displayed as "Overall Accuracy"
        # - fluency_score (number) → displayed as "Word Accuracy"
        return jsonify({
            "message": "Practice submission evaluated",
            "data": {
                # Sentence Accuracy
                "phoneme_accuracy": round(phoneme_accuracy_avg, 2),
                # Overall Accuracy
                "word_accuracy": round(word_accuracy_avg, 2),
                # Word Accuracy
                "fluency_score": round(fluency_score, 2) if isinstance(fluency_score, (int, float)) else fluency_score,
                "weak_phonemes": weak_phonemes_list,
                "details": {
                    "phoneme_details": phoneme_details,
                    "word_details": word_details
                }
            }
        }), 201

    return jsonify({"error": "Invalid file type"}), 400
