"""Confidence calibration for the intent classifier.

A classifier's probability is CALIBRATED if, among all predictions made with
confidence 0.8, about 80% are correct. Fine-tuned networks usually are not:
their numbers are systematically too high or too low, so a threshold on the
raw number means little.

TEMPERATURE SCALING fixes this with a single number T, learned on validation
data. Every probability p becomes p^(1/T), renormalised:
    T > 1  flattens the distribution (cures over-confidence)
    T < 1  sharpens it              (cures under-confidence)
The most likely class never changes, so accuracy is untouched; only the
confidence attached to it moves.
"""

import numpy as np
from scipy.optimize import minimize_scalar


def apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    """Rescale probabilities. Raising p to 1/T is the same as dividing the
    logits by T, because softmax(logits / T) is proportional to p^(1/T)."""
    scaled = np.power(np.clip(probabilities, 1e-12, 1.0), 1.0 / temperature)
    return scaled / scaled.sum(axis=-1, keepdims=True)


def negative_log_likelihood(probabilities: np.ndarray, labels: np.ndarray) -> float:
    picked = probabilities[np.arange(len(labels)), labels]
    return float(-np.log(np.clip(picked, 1e-12, 1.0)).mean())


def fit_temperature(probabilities: np.ndarray, labels: np.ndarray) -> float:
    """The T that makes the true labels most likely on this data."""
    result = minimize_scalar(
        lambda t: negative_log_likelihood(apply_temperature(probabilities, t), labels),
        bounds=(0.05, 10.0), method="bounded",
    )
    return float(result.x)


def calibration_report(probabilities: np.ndarray, labels: np.ndarray, bins: int = 10) -> dict:
    """Expected calibration error (ECE) and the reliability table behind it.

    Predictions are grouped by confidence. In each group the average
    confidence is compared with the actual accuracy; ECE is the average gap,
    weighted by group size. 0 is perfect.
    """
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == labels
    edges = np.linspace(0.0, 1.0, bins + 1)
    table, ece = [], 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        inside = (confidence > low) & (confidence <= high)
        if not inside.any():
            continue
        gap = abs(confidence[inside].mean() - correct[inside].mean())
        ece += gap * inside.mean()
        table.append({
            "range": f"{low:.1f}-{high:.1f}", "n": int(inside.sum()),
            "mean_confidence": float(confidence[inside].mean()),
            "accuracy": float(correct[inside].mean()),
        })
    return {"ece": float(ece), "mean_confidence": float(confidence.mean()),
            "accuracy": float(correct.mean()), "bins": table}


def coverage_curve(confidence: np.ndarray, correct: np.ndarray,
                   thresholds: np.ndarray) -> list[dict]:
    """For each threshold: how many queries would be answered, and how many
    of those answers would be wrong."""
    rows = []
    for threshold in thresholds:
        answered = confidence >= threshold
        rows.append({
            "threshold": float(threshold),
            "coverage": float(answered.mean()),
            "answered_error": float(1.0 - correct[answered].mean()) if answered.any() else 0.0,
        })
    return rows


def add_clustered_bound(
    curve: list[dict], confidence: np.ndarray, correct: np.ndarray, groups: list[str],
    quantile: float, resamples: int, seed: int,
) -> list[dict]:
    """Add `answered_error_upper` to each row of a coverage curve.

    WHY. Rows generated from one template family are near-copies of each
    other: the model gets the whole family right or the whole family wrong.
    Six hundred rows from eighteen families carry about eighteen independent
    pieces of evidence, not six hundred. An error rate computed over rows
    looks precise and is not, and a threshold chosen to "just meet" a target
    on it is too permissive on any other data.

    HOW. A cluster bootstrap: resample whole families with replacement many
    times, recompute the error rate each time, and take a high quantile as an
    upper bound on what the error rate could plausibly be.
    """
    rng = np.random.default_rng(seed)
    names = sorted(set(groups))
    members = {name: np.flatnonzero(np.array(groups) == name) for name in names}
    samples = np.zeros((resamples, len(curve)))
    for b in range(resamples):
        chosen = rng.choice(len(names), size=len(names), replace=True)
        index = np.concatenate([members[names[i]] for i in chosen])
        conf, ok = confidence[index], correct[index]
        for j, row in enumerate(curve):
            answered = conf >= row["threshold"]
            samples[b, j] = 1.0 - ok[answered].mean() if answered.any() else 0.0
    upper = np.quantile(samples, quantile, axis=0)
    return [{**row, "answered_error_upper": float(u)} for row, u in zip(curve, upper)]


def select_threshold(curve: list[dict], target_error: float,
                     key: str = "answered_error") -> dict:
    """The lowest threshold whose error (by `key`) meets the target, which is
    also the one that answers the most queries. If none meets it, the row
    with the lowest error."""
    meeting = [row for row in curve if row[key] <= target_error]
    if meeting:
        return min(meeting, key=lambda row: row["threshold"])
    return min(curve, key=lambda row: (row[key], row["threshold"]))
