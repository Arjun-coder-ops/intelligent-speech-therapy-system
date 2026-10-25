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


class AssessmentJob(db.Model):
    """Asynchronous speech assessment job entity."""
    __tablename__ = "assessment_jobs"

    id = db.Column(db.String(36), primary_key=True)  # UUID4
    user_id = db.Column(db.Integer, nullable=False)
    sentence_id = db.Column(db.Integer, db.ForeignKey("sentences.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="queued", nullable=False)  # queued, processing, completed, failed
    progress = db.Column(db.Integer, default=0)  # 0 to 100 percentage
    result_json = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
