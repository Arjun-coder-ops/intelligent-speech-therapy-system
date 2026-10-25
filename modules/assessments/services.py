import logging
import traceback

# Robust import: try local module first, then package-relative
mi = None
try:
    import model_interface as mi
except Exception as e:
    try:
        from ... import model_interface as mi  # type: ignore
    except Exception as e2:
        try:
            import importlib
            mi = importlib.import_module("model_interface")
        except Exception as e3:
            logging.warning("model_interface not available; audio models disabled: %s", e3)
            mi = None


if mi is not None:
    mi_calc_phoneme_accuracy = getattr(mi, 'calculate_phoneme_accuracy', None)
    mi_calc_word_level_accuracy = getattr(mi, 'calculate_word_level_accuracy', None)
    mi_calc_fluency = getattr(mi, 'calculate_fluency', None)
    mi_weak_phonemes = getattr(mi, 'weak_phonemes', None)
else:
    def _not_available(*args, **kwargs):
        raise RuntimeError("model_interface not available: import failed")
    mi_calc_phoneme_accuracy = _not_available
    mi_calc_word_level_accuracy = _not_available
    mi_calc_fluency = _not_available
    mi_weak_phonemes = _not_available


# Wrapper functions with logging and safe defaults
def calculate_phoneme_accuracy(audio_path):
    try:
        res = mi_calc_phoneme_accuracy(audio_path)
        return res
    except Exception:
        logging.exception("calculate_phoneme_accuracy failed for %s", audio_path)
        return []

def calculate_word_level_accuracy(audio_path):
    try:
        res = mi_calc_word_level_accuracy(audio_path)
        return res
    except Exception:
        logging.exception("calculate_word_level_accuracy failed for %s", audio_path)
        return []

def calculate_fluency(audio_path):
    try:
        res = mi_calc_fluency(audio_path)
        return res
    except Exception:
        logging.exception("calculate_fluency failed for %s", audio_path)
        return 0

def weak_phonemes(audio_path):
    try:
        res = mi_weak_phonemes(audio_path)
        return res
    except Exception:
        logging.exception("weak_phonemes failed for %s", audio_path)
        return []


def run_assessment(audio_path):
    results = {}
    results['phoneme_accuracy'] = calculate_phoneme_accuracy(audio_path)
    results['word_level_accuracy'] = calculate_word_level_accuracy(audio_path)
    results['fluency'] = calculate_fluency(audio_path)
    results['weak_phonemes'] = weak_phonemes(audio_path)
    print("Assessment Results:", results)
    return results


# Asynchronous Job Execution Pool
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

_job_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="assessment_worker")


def execute_assessment_job(app, job_id: str):
    """Worker task executed in background thread pool."""
    from extensions import db
    from modules.assessments.models import AssessmentJob, AudioRecord
    from modules.observability.metrics import metrics_collector
    import time

    start_time = time.time()
    with app.app_context():
        job = db.session.get(AssessmentJob, job_id)
        if not job:
            logging.error("Job %s not found in database", job_id)
            return

        metrics_collector.record_job_status(1)
        job.status = "processing"
        job.progress = 25
        db.session.commit()

        try:
            # 1. Run inference
            phoneme_data = calculate_phoneme_accuracy(job.file_path)
            job.progress = 50
            db.session.commit()

            word_data = calculate_word_level_accuracy(job.file_path)
            fluency_score = calculate_fluency(job.file_path)
            weak_ph = weak_phonemes(job.file_path)
            job.progress = 75
            db.session.commit()

            # Helper for score averaging
            scores = []
            if isinstance(phoneme_data, list):
                for item in phoneme_data:
                    if isinstance(item, dict) and 'score' in item:
                        scores.append(float(item.get('score', 0)))
                    elif isinstance(item, (int, float)):
                        scores.append(float(item))
            phoneme_accuracy = round(sum(scores) / len(scores), 2) if scores else None

            w_scores = []
            if isinstance(word_data, list):
                for item in word_data:
                    if isinstance(item, dict) and 'score' in item:
                        w_scores.append(float(item.get('score', 0)))
                    elif isinstance(item, (int, float)):
                        w_scores.append(float(item))
            word_accuracy = round(sum(w_scores) / len(w_scores), 2) if w_scores else None

            weak_words = [
                w["word"] for w in word_data
                if isinstance(w, dict) and w.get("status") == "Mispronounced" and "word" in w
            ] if isinstance(word_data, list) else []

            # 2. Persist AudioRecord
            audio_record = AudioRecord(
                user_id=job.user_id,
                file_path=job.file_path,
                sentence_id=job.sentence_id,
                phoneme_accuracy=phoneme_accuracy,
                word_accuracy=word_accuracy,
                fluency_score=fluency_score,
                weak_words=weak_words,
                weak_phonemes=weak_ph or []
            )
            db.session.add(audio_record)
            db.session.commit()

            # 3. Mark job completed
            result_payload = {
                "record_id": audio_record.id,
                "user_id": audio_record.user_id,
                "sentence_id": audio_record.sentence_id,
                "phoneme_accuracy": phoneme_accuracy,
                "word_accuracy": word_accuracy,
                "fluency_score": fluency_score,
                "weak_phonemes": weak_ph or [],
                "weak_words": weak_words,
                "duration_seconds": round(time.time() - start_time, 2)
            }

            job.status = "completed"
            job.progress = 100
            job.result_json = result_payload
            job.completed_at = datetime.utcnow()
            db.session.commit()
            metrics_collector.record_inference(time.time() - start_time, "success")

        except Exception as e:
            db.session.rollback()
            logging.exception("Async assessment job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.session.commit()
            metrics_collector.record_inference(time.time() - start_time, "failed")
        finally:
            metrics_collector.record_job_status(-1)


def queue_async_assessment(app, job_id: str):
    """Enqueue assessment job into background thread pool."""
    _job_executor.submit(execute_assessment_job, app, job_id)


