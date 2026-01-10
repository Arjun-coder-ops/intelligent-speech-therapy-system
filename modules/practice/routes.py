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


@routes_bp.route('/recommendation', methods=['GET', 'POST'])
def recommend_practice_sentences():
    weak_phonemes = request.args.get('weak_phonemes', '')
    weak_words = request.args.get('weak_words', '')

    phoneme_list = [p.strip() for p in weak_phonemes.split(',') if p.strip()]

    # 2️⃣ Build prompt dynamically
    prompt = f"""
    Generate ONE English practice sentence (8–12 words) for speech therapy.

    Focus more on these weak phonemes if possible: {phoneme_list}
    The user struggles with {weak_words} words.

    Return ONLY valid JSON in this exact format:
    {{"text":"","difficulty":""}}

    Difficulty must be easy, medium, or hard.
    """.strip()

    payload = {
        "model": "mistralai/mistral-small-3.1-24b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.9,
        "max_tokens": 150
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=15
    )

    content = response.json()["choices"][0]["message"]["content"]

    # 3️⃣ Extract JSON safely
    def extract_json(text):
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    parsed = extract_json(content)

    if not parsed or "text" not in parsed:
        return jsonify({
            "error": "Invalid model response",
            "raw": content
        }), 502

    # 4️⃣ Normalize difficulty
    difficulty = parsed.get("difficulty", "medium").lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    # 5️⃣ Final response (ONLY required fields)
    return jsonify({
        "text": parsed["text"].strip(),
        "difficulty": difficulty
    }), 200
# def recommend_practice_sentences():
#     prompt = f"""
#     Generate ONE random English practice sentence (8–12 words) for speech practice.
#     Avoid repeating similar sentences.
#     Return ONLY valid JSON in this exact format:
#     {{"text":"","difficulty":"","phonemes":[]}}

#     Use ARPAbet phonemes.
#     Difficulty must be easy, medium, or hard.
#     """.strip()

#     # commented
#     ''' {avoid_block}
#     """.strip()'''

#     payload = {
#         "model": "mistralai/mistral-small-3.1-24b-instruct:free",
#         "messages": [{"role": "user", "content": prompt}],
#         "temperature": 0.9,          # randomness
#         "max_tokens": 200
#     }

#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     response = requests.post(
#         "https://openrouter.ai/api/v1/chat/completions",
#         json=payload,
#         headers=headers,
#         timeout=15
#     )

#     # response.raise_for_status()
#     content = response.json()["choices"][0]["message"]["content"]
#     # print("Generated content:", content)

#     # Attempt to extract a JSON object from the model output robustly
#     def _extract_json_from_text(text):
#         # Find candidate JSON object(s) using braces - try the largest first
#         matches = re.findall(r'\{.*?\}', text, re.DOTALL)
#         for m in sorted(matches, key=len, reverse=True):
#             try:
#                 return json.loads(m)
#             except json.JSONDecodeError:
#                 # try a relaxed fallback by replacing single quotes
#                 try:
#                     return json.loads(m.replace("'", '"'))
#                 except Exception:
#                     continue
#         # Fallback: slice from first '{' to last '}' and try again
#         if '{' in text and '}' in text:
#             s = text[text.find('{'): text.rfind('}')+1]
#             try:
#                 return json.loads(s)
#             except Exception:
#                 import ast
#                 try:
#                     return ast.literal_eval(s)
#                 except Exception:
#                     return None
#         return None

#     parsed = _extract_json_from_text(content)
#     if parsed is None:
#         return jsonify({"error": "Failed to parse model response", "raw": content}), 502

#     # Normalize keys and types
#     if isinstance(parsed, dict):
#         # Accept 'phon' as alias for 'phonemes'
#         if 'phon' in parsed and 'phonemes' not in parsed:
#             parsed['phonemes'] = parsed.pop('phon')

#         # Ensure phonemes is a list of strings
#         if 'phonemes' in parsed:
#             if isinstance(parsed['phonemes'], str):
#                 parsed['phonemes'] = [p.strip(' "[],.') for p in re.split(r'[,\s]+', parsed['phonemes']) if p.strip()]
#             elif isinstance(parsed['phonemes'], (list, tuple)):
#                 parsed['phonemes'] = [str(p) for p in parsed['phonemes']]

#         # Normalize difficulty
#         diff = parsed.get('difficulty', '')
#         if not isinstance(diff, str) or diff.lower() not in ('easy', 'medium', 'hard'):
#             parsed['difficulty'] = 'medium'
#         else:
#             parsed['difficulty'] = diff.lower()

#         # Validate text
#         text_val = parsed.get('text', '')
#         if not isinstance(text_val, str) or not text_val.strip():
#             return jsonify({"error": "Model output missing or invalid 'text' field", "raw": content}), 502

#         return jsonify({
#             "sentence_id": None,
#             "text": text_val.strip(),
#             "difficulty": parsed['difficulty'],
#             "phonemes": parsed.get('phonemes', []),
#             "reason": "model_generated"
#         }), 200

#     # If model returned non-object JSON (e.g., an array), return an error
#     return jsonify({"error": "Model returned non-object JSON", "raw": content}), 502


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
    # user_id = request.form.get('user_id')  # Not used for practice submissions

    # if not sentence_id:
    #     return jsonify({"error": "sentence_id is required"}), 400

    # sentence = Sentence.query.get(sentence_id)
    # if not sentence:
    #     return jsonify({"error": "Invalid sentence_id"}), 404

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
