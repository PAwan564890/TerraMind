"""Retrieval and out-of-domain metrics."""

import numpy as np
from sklearn.metrics import roc_auc_score


def retrieval_metrics(similarities: np.ndarray, correct: list[int]) -> dict:
    """Recall@1, Recall@5 and MRR.

    `similarities[i, j]` is the score of candidate j for query i, and
    `correct[i]` is the index of the right candidate for query i.

    Recall@k: share of queries whose right answer is in the top k.
    MRR (mean reciprocal rank): mean of 1/rank of the right answer, so rank 1
    scores 1.0, rank 2 scores 0.5, and so on.
    """
    correct_scores = similarities[np.arange(len(correct)), correct]
    # Rank = 1 + number of candidates scoring strictly higher than the right one.
    ranks = 1 + (similarities > correct_scores[:, None]).sum(axis=1)
    return {
        "n": len(correct),
        "recall_at_1": float((ranks <= 1).mean()),
        "recall_at_5": float((ranks <= 5).mean()),
        "mrr": float((1.0 / ranks).mean()),
    }


def separation_metrics(in_domain_scores: np.ndarray, out_scores: np.ndarray) -> dict:
    """How well a score separates in-domain from out-of-domain queries.
    Higher scores must mean "more in-domain".

    AUROC: probability that a random in-domain query scores higher than a
    random out-of-domain one (0.5 = useless, 1.0 = perfect).
    FPR at 95% TPR: set the threshold so 95% of in-domain queries are
    accepted; this is the share of out-of-domain queries that also get in.
    """
    labels = np.concatenate([np.ones(len(in_domain_scores)), np.zeros(len(out_scores))])
    scores = np.concatenate([in_domain_scores, out_scores])
    threshold = float(np.percentile(in_domain_scores, 5))
    return {
        "n_in_domain": int(len(in_domain_scores)),
        "n_out_of_domain": int(len(out_scores)),
        "auroc": float(roc_auc_score(labels, scores)),
        "fpr_at_95_tpr": float((out_scores >= threshold).mean()),
        "threshold_at_95_tpr": threshold,
    }
