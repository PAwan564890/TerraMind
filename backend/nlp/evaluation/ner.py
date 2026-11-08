"""Entity-level metrics for NER.

An entity counts as correct only if its start, end AND type all match the
label exactly. Token-level accuracy is not reported: most tokens are "O", so
it looks high even for a model that finds no entities.
"""

from backend.nlp.query.enums import EntityType

Span = tuple[int, int, str]


def _prf(correct: int, predicted: int, gold: int) -> dict:
    precision = correct / predicted if predicted else 0.0
    recall = correct / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "correct": correct, "predicted": predicted, "gold": gold}


def entity_report(gold: list[list[Span]], predicted: list[list[Span]]) -> dict:
    """Micro-averaged precision/recall/F1 overall and for each entity type.

    `gold[i]` and `predicted[i]` are the spans of the i-th text.
    """
    types = [entity_type.value for entity_type in EntityType]
    counts = {t: [0, 0, 0] for t in types}  # correct, predicted, gold
    for gold_spans, predicted_spans in zip(gold, predicted):
        gold_set, predicted_set = set(gold_spans), set(predicted_spans)
        for span in predicted_set:
            counts[span[2]][1] += 1
            if span in gold_set:
                counts[span[2]][0] += 1
        for span in gold_set:
            counts[span[2]][2] += 1

    total = [sum(c[i] for c in counts.values()) for i in range(3)]
    exact_texts = sum(set(g) == set(p) for g, p in zip(gold, predicted))
    return {
        "n_texts": len(gold),
        "overall": _prf(*total),
        "per_type": {t: _prf(*counts[t]) for t in types},
        # Share of texts where every entity is right and nothing extra is found.
        "text_exact_match": exact_texts / len(gold) if gold else 0.0,
    }


def format_entity_report(title: str, report: dict) -> str:
    lines = [
        f"{title}  (texts={report['n_texts']}, all entities right in "
        f"{report['text_exact_match']:.1%} of texts)",
        f"  {'type':<14}{'precision':>10}{'recall':>8}{'f1':>8}{'gold':>7}",
    ]
    for name, m in [*report["per_type"].items(), ("ALL", report["overall"])]:
        lines.append(
            f"  {name:<14}{m['precision']:>10.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['gold']:>7}"
        )
    return "\n".join(lines)
