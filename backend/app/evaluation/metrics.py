"""
Evaluation Metrics & Visualization Engine for CSIFormer.

Computes multi-class classification and spatial detection metrics:
- Overall Accuracy & Top-K Accuracy
- Precision, Recall, F1 Score (Macro & Weighted)
- Multi-Class ROC AUC (One-vs-Rest)
- Confusion Matrix Computation & Matplotlib Plotting
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    top_k_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix
)


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred_probs: np.ndarray,
    class_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute comprehensive classification metrics for CSIFormer.

    :param y_true: Ground truth class indices [N].
    :param y_pred_probs: Predicted class probability distribution [N, NumClasses].
    :param class_names: Optional list of class string names.
    :return: Dictionary containing calculated metrics.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_pred_probs = np.asarray(y_pred_probs, dtype=float)
    y_pred = np.argmax(y_pred_probs, axis=-1)

    num_classes = y_pred_probs.shape[1]
    unique_true_classes = np.unique(y_true)

    # 1. Accuracies
    top1_acc = float(accuracy_score(y_true, y_pred))
    try:
        top3_acc = float(top_k_accuracy_score(y_true, y_pred_probs, k=min(3, num_classes), labels=list(range(num_classes)))) if num_classes > 3 else top1_acc
    except Exception:
        top3_acc = top1_acc

    # 2. Precision, Recall, F1
    prec_macro = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    prec_weighted = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))

    rec_macro = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    rec_weighted = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))

    f1_macro = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    f1_weighted = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    # 3. Multi-Class ROC AUC (One-vs-Rest)
    roc_auc = None
    try:
        if len(unique_true_classes) > 1 and len(unique_true_classes) == num_classes:
            roc_auc = float(roc_auc_score(y_true, y_pred_probs, multi_class="ovr", average="macro"))
    except Exception:
        roc_auc = None

    # 4. Confusion Matrix
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))

    # Per-class metrics breakdown
    per_class_metrics = {}
    if class_names:
        for idx, name in enumerate(class_names):
            c_true = (y_true == idx)
            c_pred = (y_pred == idx)
            tp = int(np.sum(c_true & c_pred))
            fp = int(np.sum(~c_true & c_pred))
            fn = int(np.sum(c_true & ~c_pred))
            precision_c = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall_c = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_c = 2 * precision_c * recall_c / (precision_c + recall_c) if (precision_c + recall_c) > 0 else 0.0

            per_class_metrics[name] = {
                "support": int(np.sum(c_true)),
                "precision": round(precision_c, 4),
                "recall": round(recall_c, 4),
                "f1_score": round(f1_c, 4)
            }

    return {
        "accuracy": round(top1_acc, 4),
        "top3_accuracy": round(top3_acc, 4),
        "precision_macro": round(prec_macro, 4),
        "precision_weighted": round(prec_weighted, 4),
        "recall_macro": round(rec_macro, 4),
        "recall_weighted": round(rec_weighted, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "roc_auc_macro": round(roc_auc, 4) if roc_auc is not None else "N/A",
        "confusion_matrix": cm.tolist(),
        "per_class_metrics": per_class_metrics
    }


def plot_confusion_matrix(
    cm: Union[np.ndarray, List[List[int]]],
    class_names: List[str],
    save_path: Union[str, Path],
    title: str = "CSIFormer Activity Recognition Confusion Matrix",
    cmap: str = "Blues"
) -> Path:
    """
    Render and save a high-contrast confusion matrix heatmap.

    :param cm: 2D confusion matrix array.
    :param class_names: Class labels.
    :param save_path: Filepath where the PNG should be written.
    :param title: Chart title.
    :param cmap: Matplotlib colormap.
    :return: Path to saved PNG.
    """
    cm_arr = np.array(cm)
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    im = ax.imshow(cm_arr, interpolation="nearest", cmap=cmap)
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel("Sample Counts", rotation=-90, va="bottom", fontsize=10)

    # Axis ticks and labels
    ax.set(
        xticks=np.arange(cm_arr.shape[1]),
        yticks=np.arange(cm_arr.shape[0]),
        xticklabels=class_names,
        yticklabels=class_names,
        title=title,
        ylabel="True Activity Label",
        xlabel="Predicted Activity Label"
    )

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor", fontsize=9)
    plt.setp(ax.get_yticklabels(), fontsize=9)

    # Print numerical counts inside cells
    thresh = cm_arr.max() / 2.0
    for i in range(cm_arr.shape[0]):
        for j in range(cm_arr.shape[1]):
            val = cm_arr[i, j]
            ax.text(
                j, i, format(val, "d"),
                ha="center", va="center",
                color="white" if val > thresh else "black",
                fontsize=8,
                weight="bold" if val > 0 else "normal"
            )

    fig.tight_layout()
    plt.savefig(save_path, bbox_inches="tight")
    plt.close(fig)

    return save_path
