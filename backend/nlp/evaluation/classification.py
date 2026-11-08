"""Classification metrics shared by language detection and intent classification."""

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


def classification_report(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict:
    """Accuracy, per-class precision/recall/F1 and the confusion matrix.

    `labels` fixes the class order. Predictions outside `labels` (a baseline
    answering with some other language, say) count as errors for the true class.
    """
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    # Extra column for predictions that are not one of the expected labels.
    columns = [*labels, "other"]
    y_pred_binned = [p if p in labels else "other" for p in y_pred]
    matrix = confusion_matrix(y_true, y_pred_binned, labels=columns)[: len(labels)]

    return {
        "n": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1.mean()),
        "per_class": {
            label: {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i, label in enumerate(labels)
        },
        "confusion": {"rows_true": labels, "cols_predicted": columns, "matrix": matrix.tolist()},
    }


def format_report(title: str, report: dict) -> str:
    width = max(len(label) for label in report["per_class"]) + 2
    lines = [
        f"{title}  (n={report['n']})",
        f"  accuracy {report['accuracy']:.3f}   macro-F1 {report['macro_f1']:.3f}",
        f"  {'#':>2} {'class':<{width}}{'precision':>10}{'recall':>8}{'f1':>8}{'n':>6}",
    ]
    for i, (label, m) in enumerate(report["per_class"].items()):
        lines.append(
            f"  {i:>2} {label:<{width}}{m['precision']:>10.3f}{m['recall']:>8.3f}"
            f"{m['f1']:>8.3f}{m['support']:>6}"
        )
    # Columns are numbered like the rows above; the last one counts
    # predictions that are not any of the expected classes.
    confusion = report["confusion"]
    columns = [str(i) for i in range(len(confusion["rows_true"]))] + ["other"]
    lines.append("  confusion (rows = true class, columns = predicted class #)")
    lines.append(f"  {'':>2} {'':<{width}}" + "".join(f"{c:>6}" for c in columns))
    for i, (label, row) in enumerate(zip(confusion["rows_true"], confusion["matrix"])):
        lines.append(f"  {i:>2} {label:<{width}}" + "".join(f"{n:>6}" for n in row))
    return "\n".join(lines)
