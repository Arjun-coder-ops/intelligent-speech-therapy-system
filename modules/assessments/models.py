from extensions import db
from datetime import datetime


# AUDIO RECORD TABLE

class AudioRecord(db.Model):
    __tablename__ = "assessment"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    sentence_id = db.Column(db.Integer, db.ForeignKey("sentences.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    phoneme_accuracy = db.Column(db.Float, nullable=True)
    word_accuracy = db.Column(db.Float, nullable=True)
    fluency_score = db.Column(db.Float, nullable=True)
    weak_phonemes = db.Column(db.JSON, nullable=True)  # list of weak phonemes
    weak_words = db.Column(db.JSON, nullable=True)     # list of weak words
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
