from .services import (
    calculate_phoneme_accuracy,
    calculate_word_level_accuracy,
    calculate_fluency,
    weak_phonemes
)
from extensions import db
from modules.sentences.models import Sentence
from .models import AudioRecord
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import time
from sqlalchemy import text
import numpy as np
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

assess_bp = Blueprint("assessment", __name__)

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


@assess_bp.route("/add-sentence", methods=["POST"])
def add_sentence():
    data = request.get_json(silent=True) or {}
    sentence_text = data.get("text") or data.get("sentence")
    if not sentence_text:
        return jsonify({"error": "Sentence text is required"}), 400

    new_sentence = Sentence(
        text=sentence_text.strip(),
        source_type='custom',
        difficulty='medium',
    )
    db.session.add(new_sentence)
    db.session.commit()

    return jsonify({"message": "Sentence added successfully", "sentence_id": new_sentence.id}), 201


@assess_bp.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file part in the request"}), 400

    file = request.files["audio"]
    user_id = request.form.get("user_id")
    sentence_id = request.form.get("sentence_id")

    if not file or file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not sentence_id:
        return jsonify({"error": "Sentence ID missing"}), 400

    try:
        sentence_id_val = int(sentence_id)
    except (ValueError, TypeError):
        return jsonify({"error": "sentence_id must be an integer"}), 400

    sentence = db.session.get(Sentence, sentence_id_val)
    if not sentence:
        return jsonify({"error": "Invalid sentence_id"}), 404


    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        user_id_val = int(user_id)
    except (ValueError, TypeError):
        user_id_val = user_id

    if file and allowed_file(file.filename):
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()

        timestamp = int(time.time())
        filename = f"assessment_audio_{timestamp}{ext}"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Raw outputs (may be detailed lists or summary floats)
        phoneme_data = calculate_phoneme_accuracy(file_path)
        word_data = calculate_word_level_accuracy(file_path)
        fluency_score = calculate_fluency(file_path)
        weak_phonemes_list = weak_phonemes(file_path)

        # Convert all numpy types to native Python types
        phoneme_data = convert_to_native_types(phoneme_data)
        word_data = convert_to_native_types(word_data)
        fluency_score = convert_to_native_types(fluency_score)
        weak_phonemes_list = convert_to_native_types(weak_phonemes_list)

        # Helper: derive numeric average from model outputs
        def _avg_score_from_list(data):
            try:
                if data is None:
                    return None
                if isinstance(data, list):
                    scores = []
                    for item in data:
                        if isinstance(item, dict) and 'score' in item:
                            try:
                                s = float(item.get('score', 0))
                                scores.append(s)
                            except Exception:
                                continue
                        elif isinstance(item, (int, float)):
                            scores.append(float(item))
                    if not scores:
                        return None
                    return round(sum(scores) / len(scores), 2)
                elif isinstance(data, (int, float)):
                    return float(data)
            except Exception as e:
                current_app.logger.exception("Failed to summarize scores: %s", e)
            return None

        # Convert detailed outputs to DB-friendly numeric values
        phoneme_accuracy = _avg_score_from_list(phoneme_data)
        word_accuracy = _avg_score_from_list(word_data)

        weak_words = [
            w["word"] for w in word_data
            if isinstance(w, dict) and w.get("status") == "Mispronounced" and "word" in w
        ] if isinstance(word_data, list) else []

        warning = None
        if phoneme_accuracy is None and word_accuracy is None and (fluency_score in (None, 0)) and (not weak_phonemes_list):
            current_app.logger.warning("Assessment returned default results for file %s", file_path)
            warning = "Assessment metrics are using fallback estimation; ensure audio models are loaded."

        audio_record = AudioRecord(
            user_id=user_id_val,
            file_path=file_path,
            sentence_id=sentence_id_val,
            phoneme_accuracy=phoneme_accuracy,
            word_accuracy=word_accuracy,
            fluency_score=fluency_score,
            weak_words=weak_words,
            weak_phonemes=weak_phonemes_list or []
        )

        details = {
            "phoneme_details": phoneme_data,
            "word_details": word_data
        }

        try:
            db.session.add(audio_record)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database error during commit: {e}")
            try:
                db.session.remove()
                db.session.add(audio_record)
                db.session.commit()
            except Exception as retry_error:
                db.session.rollback()
                current_app.logger.error(f"Retry failed: {retry_error}")
                return jsonify({
                    "error": "Failed to save assessment results",
                    "details": str(retry_error)
                }), 500

        return jsonify({
            "message": "File uploaded and assessed successfully",
            "warning": warning,
            "data": {
                "id": audio_record.id,
                "user_id": audio_record.user_id,
                "sentence_id": audio_record.sentence_id,
                "phoneme_accuracy": phoneme_accuracy,
                "word_accuracy": word_accuracy,
                "fluency_score": fluency_score,
                "weak_phonemes": weak_phonemes_list or [],
                "weak_words": weak_words,
                "details": details
            }
        }), 201
    else:
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400


@assess_bp.route("/results/<int:record_id>", methods=["GET"])
def get_assessment_result(record_id):
    record = db.session.get(AudioRecord, record_id)
    if not record:
        return jsonify({"error": "Assessment record not found"}), 404

    sentence = db.session.get(Sentence, record.sentence_id)
    return jsonify({
        "id": record.id,
        "user_id": record.user_id,
        "sentence_id": record.sentence_id,
        "sentence_text": sentence.text if sentence else None,
        "phoneme_accuracy": record.phoneme_accuracy,
        "word_accuracy": record.word_accuracy,
        "fluency_score": record.fluency_score,
        "weak_phonemes": record.weak_phonemes or [],
        "weak_words": record.weak_words or [],
        "created_at": record.created_at.isoformat() if record.created_at else None
    }), 200


@assess_bp.route("/history", methods=["GET"])
def get_assessment_history():
    user_id = request.args.get("user_id")
    query = AudioRecord.query
    if user_id:
        try:
            query = query.filter_by(user_id=int(user_id))
        except (ValueError, TypeError):
            query = query.filter_by(user_id=user_id)

    records = query.order_by(AudioRecord.created_at.desc()).all()
    results = []
    for r in records:
        sentence = db.session.get(Sentence, r.sentence_id)

        results.append({
            "id": r.id,
            "user_id": r.user_id,
            "sentence_id": r.sentence_id,
            "sentence_text": sentence.text if sentence else None,
            "phoneme_accuracy": r.phoneme_accuracy,
            "word_accuracy": r.word_accuracy,
            "fluency_score": r.fluency_score,
            "weak_phonemes": r.weak_phonemes or [],
            "weak_words": r.weak_words or [],
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    return jsonify({"assessments": results}), 200


@assess_bp.route("/recommend", methods=["GET"])
def recommend_sentence():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        user_id_val = int(user_id)
    except (ValueError, TypeError):
        user_id_val = user_id

    # Get sentence IDs already attempted by this user
    used_records = (
        db.session.query(AudioRecord.sentence_id)
        .filter(AudioRecord.user_id == user_id_val)
        .all()
    )
    used_sentence_ids = [sid[0] for sid in used_records if sid[0] is not None]

    # Get a sentence not used before
    sentence = None
    if used_sentence_ids:
        sentence = (
            db.session.query(Sentence)
            .filter(~Sentence.id.in_(used_sentence_ids))
            .first()
        )

    # If all available sentences have been practiced, cycle back to the first sentence
    if not sentence:
        sentence = db.session.query(Sentence).first()

    if not sentence:
        return jsonify({
            "message": "No sentences available in database"
        }), 404

    return jsonify({
        "sentence_id": sentence.id,
        "text": sentence.text,
        "difficulty": sentence.difficulty
    }), 200

