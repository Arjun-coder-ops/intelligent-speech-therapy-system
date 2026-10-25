"""
Metrics calculation module for AI evaluation:
- Word Error Rate (WER) using dynamic programming Levenshtein distance
- Character Error Rate (CER)
- Schema and structural compliance for recommendation responses
"""
import re
from typing import Dict, Any, List, Tuple


def _normalize_text(text: str) -> List[str]:
    """Tokenize and normalize text for speech evaluation (lowercase, alphanumeric)."""
    if not text:
        return []
    # Strip punctuation and convert to lowercase
    cleaned = re.sub(r"[^\w\s]", "", text.strip().lower())
    return [word for word in cleaned.split() if word]


def calculate_wer(reference: str, hypothesis: str) -> Dict[str, Any]:
    """
    Calculate Word Error Rate (WER) using Levenshtein distance on tokenized word sequences.
    Formula: WER = (Substitutions + Deletions + Insertions) / Total Reference Words
    """
    ref_tokens = _normalize_text(reference)
    hyp_tokens = _normalize_text(hypothesis)

    r_len = len(ref_tokens)
    h_len = len(hyp_tokens)

    if r_len == 0 and h_len == 0:
        return {
            "wer": 0.0,
            "substitutions": 0,
            "deletions": 0,
            "insertions": 0,
            "hits": 0,
            "reference_words": 0,
            "hypothesis_words": 0,
            "accuracy": 1.0
        }

    if r_len == 0:
        return {
            "wer": 1.0,
            "substitutions": 0,
            "deletions": 0,
            "insertions": h_len,
            "hits": 0,
            "reference_words": 0,
            "hypothesis_words": h_len,
            "accuracy": 0.0
        }

    # Initialize dynamic programming table for edit distance
    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]

    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                substitution = dp[i - 1][j - 1] + 1
                deletion = dp[i - 1][j] + 1
                insertion = dp[i][j - 1] + 1
                dp[i][j] = min(substitution, deletion, insertion)

    # Backtrace to compute detailed error types
    i = r_len
    j = h_len
    substitutions = 0
    deletions = 0
    insertions = 0
    hits = 0

    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_tokens[i - 1] == hyp_tokens[j - 1]:
            hits += 1
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            substitutions += 1
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            deletions += 1
            i -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            insertions += 1
            j -= 1
        else:
            if i > 0 and j > 0:
                i -= 1
                j -= 1
            elif i > 0:
                i -= 1
            else:
                j -= 1

    total_errors = substitutions + deletions + insertions
    wer = round(total_errors / r_len, 4)
    accuracy = round(max(0.0, 1.0 - wer), 4)

    return {
        "wer": wer,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "hits": hits,
        "reference_words": r_len,
        "hypothesis_words": h_len,
        "accuracy": accuracy
    }


def calculate_cer(reference: str, hypothesis: str) -> Dict[str, Any]:
    """Calculate Character Error Rate (CER)."""
    ref_chars = list(re.sub(r"\s+", "", reference.lower()))
    hyp_chars = list(re.sub(r"\s+", "", hypothesis.lower()))

    r_len = len(ref_chars)
    h_len = len(hyp_chars)

    if r_len == 0:
        return {"cer": 0.0 if h_len == 0 else 1.0, "ref_chars": r_len, "hyp_chars": h_len}

    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]
    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            if ref_chars[i - 1] == hyp_chars[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j - 1] + 1, dp[i - 1][j] + 1, dp[i][j - 1] + 1)

    cer = round(dp[r_len][h_len] / r_len, 4)
    return {"cer": cer, "ref_chars": r_len, "hyp_chars": h_len}


def validate_recommendation_schema(data: Any, expected_count: int = 3) -> Tuple[bool, List[str]]:
    """
    Validate that an LLM recommendation response complies strictly with the schema:
    {
        "sentences": [
            {"text": "...", "difficulty": "easy|medium|hard"}
        ]
    }
    """
    errors = []
    if not isinstance(data, dict):
        return False, ["Response root must be a JSON dictionary"]

    sentences = data.get("sentences")
    if sentences is None:
        return False, ["Missing required root key 'sentences'"]

    if not isinstance(sentences, list):
        return False, ["Key 'sentences' must be a list"]

    if len(sentences) != expected_count:
        errors.append(f"Expected exactly {expected_count} sentences, got {len(sentences)}")

    valid_difficulties = {"easy", "medium", "hard"}

    for idx, item in enumerate(sentences):
        if not isinstance(item, dict):
            errors.append(f"Sentence at index {idx} must be a dictionary")
            continue
        text = item.get("text")
        if not text or not isinstance(text, str) or not text.strip():
            errors.append(f"Sentence at index {idx} has missing or empty 'text'")

        difficulty = str(item.get("difficulty", "")).lower()
        if difficulty not in valid_difficulties:
            errors.append(
                f"Sentence at index {idx} has invalid difficulty '{difficulty}'. Expected one of {valid_difficulties}"
            )

    is_valid = len(errors) == 0
    return is_valid, errors
