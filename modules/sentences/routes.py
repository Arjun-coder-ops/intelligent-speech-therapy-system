from flask import Blueprint, request, jsonify
from extensions import db
from .models import Sentence

sentences_bp = Blueprint("sentences", __name__)


@sentences_bp.route("", methods=["GET"])
@sentences_bp.route("/", methods=["GET"])
def get_sentences():
    difficulty = request.args.get("difficulty")
    source_type = request.args.get("source_type")

    query = Sentence.query
    if difficulty:
        query = query.filter_by(difficulty=difficulty)
    if source_type:
        query = query.filter_by(source_type=source_type)

    sentences = query.order_by(Sentence.id.asc()).all()

    return jsonify([{
        "id": s.id,
        "text": s.text,
        "source_type": s.source_type,
        "phonemes": s.phonemes,
        "difficulty": s.difficulty,
        "created_at": s.created_at.isoformat() if s.created_at else None
    } for s in sentences]), 200


@sentences_bp.route("/<int:sentence_id>", methods=["GET"])
def get_sentence_by_id(sentence_id):
    sentence = db.session.get(Sentence, sentence_id)
    if not sentence:
        return jsonify({"message": "Sentence not found"}), 404


    return jsonify({
        "id": sentence.id,
        "text": sentence.text,
        "source_type": sentence.source_type,
        "phonemes": sentence.phonemes,
        "difficulty": sentence.difficulty,
        "created_at": sentence.created_at.isoformat() if sentence.created_at else None
    }), 200


@sentences_bp.route("", methods=["POST"])
@sentences_bp.route("/", methods=["POST"])
@sentences_bp.route("/add-sentence", methods=["POST"])
def add_sentence():
    data = request.get_json(silent=True) or {}

    text = data.get("sentence") or data.get("text")
    if not text:
        return jsonify({"message": "Sentence text is required ('sentence' or 'text' field)"}), 400

    source_type = data.get("source_type", "custom")
    difficulty = data.get("difficulty", "medium")
    phonemes = data.get("phonemes")

    sentence = Sentence(
        text=text.strip(),
        source_type=source_type,
        phonemes=phonemes,
        difficulty=difficulty
    )

    try:
        db.session.add(sentence)
        db.session.commit()
        return jsonify({
            "message": "Sentence added successfully",
            "id": sentence.id,
            "sentence": sentence.text
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "message": "Failed to add sentence",
            "error": str(e)
        }), 500


@sentences_bp.route("/add-bulk-sentences", methods=["POST"])
def add_bulk_sentences():
    data = request.get_json(silent=True)

    if not isinstance(data, list):
        return jsonify({"message": "Expected a JSON array of sentences"}), 400

    sentences = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("sentence")
        if not text:
            continue
        sentence = Sentence(
            text=text.strip(),
            source_type=item.get("source_type", "custom"),
            phonemes=item.get("phonemes"),
            difficulty=item.get("difficulty", "medium")
        )
        sentences.append(sentence)

    if not sentences:
        return jsonify({"message": "No valid sentences provided in array"}), 400

    try:
        db.session.bulk_save_objects(sentences)
        db.session.commit()
        return jsonify({
            "message": "Bulk upload successful",
            "count": len(sentences)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "message": "Bulk upload failed",
            "error": str(e)
        }), 500