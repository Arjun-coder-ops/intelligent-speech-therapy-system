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


