from flask import Blueprint, request, jsonify
from modules.sentences.models import Sentence
from modules.assessments.models import AudioRecord
from modules.auth.models import users
from extensions import db

history_bp = Blueprint("history", __name__)


@history_bp.route("/prev_res", methods=["GET"])
@history_bp.route("/prev_results", methods=["GET"])
def gethistory():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"message": "user_id is required"}), 400

    try:
        user_id_val = int(user_id)
    except (ValueError, TypeError):
        user_id_val = user_id

    user = users.query.filter(users.id == user_id_val).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    assess_history = AudioRecord.query.filter(
        AudioRecord.user_id == user_id_val
    ).order_by(AudioRecord.created_at.desc()).all()

    # Serialize the results to JSON-compatible dictionaries
    history_data = []
    for record in assess_history:
        sentence_obj = Sentence.query.filter(Sentence.id == record.sentence_id).first()
        sentence_text = sentence_obj.text if sentence_obj else ""
        date_str = record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else None

        history_data.append({
            "id": record.id,
            "user_id": record.user_id,
            "sentence_id": record.sentence_id,
            "sentence": sentence_text,
            "sent_accuracy": record.phoneme_accuracy,
            "word_accuracy": record.word_accuracy,
            "fluency_score": record.fluency_score,
            "weak_phonemes": record.weak_phonemes or [],
            "weak_words": record.weak_words or [],
            "assessment_date": date_str,
            "assessemt_date": date_str  # Kept for compatibility with existing frontend code
        })

    return jsonify({
        "response": history_data,
        "history": history_data
    }), 200

