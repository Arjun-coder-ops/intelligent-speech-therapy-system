from flask import Blueprint, request, jsonify, current_app
import requests
import json
from modules.sentences.models import Sentence
from modules.assessments.models import AudioRecord
from modules.auth.models import users
from extensions import db

history_bp = Blueprint("history", __name__)


@history_bp.route("/prev_results", methods=["GET"])
def gethistory():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"message": "user_id is required"}), 400
    
    user = users.query.filter(users.id == user_id).first()
    
    if not user:
        return jsonify({"message": "user_id is not in the data"}), 404

    assess_history = AudioRecord.query.filter(
        AudioRecord.user_id == user_id).all()

    # Serialize the results to JSON-compatible dictionaries
    history_data = []
    for record in assess_history:
        history_data.append({
            "id": record.id,
            "user_id": record.user_id,
            "sentence_id": record.sentence_id,
            "sentence": Sentence.query.filter(Sentence.id == record.sentence_id).first().text,
            "sent_accuracy": record.phoneme_accuracy,
            "word_accuracy": record.word_accuracy,
            "weak_phonemes": record.weak_phonemes,
            "weak_words": record.weak_words,
            "assessemt_date": record.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return jsonify({"response": history_data}), 200
