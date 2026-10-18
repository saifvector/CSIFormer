"""
CSIFormer Phase 15 — Baseline Evaluation of Unmodified Phase 13 Model on Real CSI.

Evaluates models/csiformer_phase13_best.pth directly on real hardware captures
from data/real_csi_dataset/ without retraining or adaptation.

Computes:
- Per-class Precision, Recall, F1-Score
- Life-Safety Fall Detection Recall (Class 9)
- Confusion Matrix across true activities
- Performance across Train, Validation, and Held-out Test splits.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

LABEL_MAP = {
    0: "Push&Pull",
    2: "Clap",
    6: "Static/Box",
    8: "Sit/Clean",
    9: "FALL",
    11: "Walk"
}

def load_real_dataset_windows(split: str = "all") -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
    """
    Extracts non-overlapping [50, 56] sliding windows from real session files.
    """
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    if split != "all":
        sessions = [s for s in sessions if s["split"] == split]

    windows = []
    labels = []
    session_ids = []
    participants = []

    for s in sessions:
        json_file = s["json_file"]
        json_path = DATASET_DIR / json_file
        if not json_path.exists():
            continue

        with open(json_path, "r") as f:
            data = json.load(f)

        frames = data["frames"]
        cid = s["class_id"]
        sid = s["session_id"]
        pid = s["participant_id"]

        # Extract frames as [N, 56]
        mat = np.array([fr["amplitudes"] for fr in frames], dtype=np.float32)
        n_frames = len(mat)
        
        # Slicing non-overlapping 50-frame windows
        step = 50
        for start_idx in range(0, n_frames - 50 + 1, step):
            win = mat[start_idx:start_idx + 50, :56]
            if win.shape == (50, 56) and np.isfinite(win).all():
                windows.append(win)
                labels.append(cid)
                session_ids.append(sid)
                participants.append(pid)

    return np.array(windows, dtype=np.float32), np.array(labels, dtype=np.int64), session_ids, participants


def evaluate_model_on_windows(
    model: CSIDualBranchFusionNet,
    windows: np.ndarray,
    labels: np.ndarray,
    device: torch.device,
    preprocessor: PhysicsCSIPreprocessor
) -> Dict[str, Any]:
    """Runs forward passes and computes classification metrics."""
    model.eval()
    y_true = []
    y_pred = []
    y_probs = []
    gate_weights_list = []

    for idx in range(len(windows)):
        win = windows[idx]  # [50, 56]
        
        # Raw Branch: Z-score normalization along temporal axis
        amp_mean = win.mean(axis=0, keepdims=True)
        amp_std = win.std(axis=0, keepdims=True) + 1e-6
        norm_raw = (win - amp_mean) / amp_std
        t_raw = torch.tensor(norm_raw, dtype=torch.float32).unsqueeze(0).to(device)

        # Doppler Branch: STFT
        doppler_mat = preprocessor.compute_doppler_spectrogram(win)
        t_dopp = torch.tensor(doppler_mat, dtype=torch.float32).unsqueeze(0).to(device)

        with torch.no_grad():
            out = model(t_raw, t_dopp)
            logits = out["activity_logits"]
            probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
            pred_class = int(np.argmax(probs))

            gw = out.get("fusion_weights", None)
            if gw is not None:
                gate_weights_list.append([float(gw[0, 0].item()), float(gw[0, 1].item())])
            else:
                gate_weights_list.append([0.5, 0.5])

        y_true.append(int(labels[idx]))
        y_pred.append(pred_class)
        y_probs.append(probs)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    acc = float(np.mean(y_true == y_pred))

    # Unique classes present
    unique_classes = sorted(list(set(y_true)))
    target_names = [LABEL_MAP.get(c, f"Class_{c}") for c in unique_classes]

    # Classification report
    rep = classification_report(y_true, y_pred, labels=unique_classes, target_names=target_names, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=unique_classes).tolist()

    # Fall recall check (class 9)
    fall_recall = rep.get("FALL", {}).get("recall", 0.0) if "FALL" in rep else 0.0

    return {
        "accuracy": round(acc, 4),
        "total_windows": len(y_true),
        "classes_evaluated": unique_classes,
        "class_names": target_names,
        "classification_report": rep,
        "confusion_matrix": cm,
        "fall_recall": round(fall_recall, 4),
        "mean_raw_gate": round(float(np.mean([gw[0] for gw in gate_weights_list])), 3),
        "mean_dopp_gate": round(float(np.mean([gw[1] for gw in gate_weights_list])), 3),
        "y_true": y_true.tolist(),
        "y_pred": y_pred.tolist()
    }


def main():
    print("=" * 80)
    print("PHASE 15 — EVALUATING UNMODIFIED PHASE 13 MODEL ON REAL ESP32-S3 CSI")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Inference Device: {device}")

    # Load Phase 13 Production Checkpoint
    ckpt_path = BASE_DIR / "models" / "csiformer_phase13_best.pth"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Missing Phase 13 checkpoint: {ckpt_path}")

    model = CSIDualBranchFusionNet(
        num_subcarriers=56,
        doppler_bins=56,
        seq_len=50,
        num_classes=12,
        embed_dim=128,
        nhead=8,
        num_layers=3,
        dim_feedforward=512,
        dropout=0.1,
        fusion_mode="gated"
    ).to(device)

    state = torch.load(ckpt_path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.eval()
    print("[Model] Loaded unmodified Phase 13 production model successfully.")

    preprocessor = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )

    # 1. Evaluate on all real windows
    all_wins, all_labs, all_sids, all_pids = load_real_dataset_windows("all")
    print(f"\nTotal Real Hardware Windows Extracted: {len(all_wins)}")
    print(f"Class Distribution: {np.bincount(all_labs, minlength=12)}")

    res_all = evaluate_model_on_windows(model, all_wins, all_labs, device, preprocessor)
    print(f"\n[Unmodified Baseline Overall Performance]")
    print(f"  Accuracy: {res_all['accuracy']*100:.2f}% ({int(res_all['accuracy']*len(all_wins))}/{len(all_wins)} windows)")
    print(f"  Fall Detection Recall: {res_all['fall_recall']*100:.2f}%")
    print(f"  Mean Raw Gate Weight: {res_all['mean_raw_gate']} | Mean Doppler Gate Weight: {res_all['mean_dopp_gate']}")

    # 2. Evaluate by Split (Train, Val, Held-Out Test)
    split_results = {}
    for sp in ["train", "val", "test"]:
        w_sp, l_sp, _, _ = load_real_dataset_windows(sp)
        if len(w_sp) > 0:
            eval_sp = evaluate_model_on_windows(model, w_sp, l_sp, device, preprocessor)
            split_results[sp] = eval_sp
            print(f"  Split [{sp.upper()}]: Accuracy = {eval_sp['accuracy']*100:.2f}% ({len(w_sp)} windows), Fall Recall = {eval_sp['fall_recall']*100:.2f}%")

    # 3. Plot Confusion Matrix
    cm = np.array(res_all["confusion_matrix"])
    classes = res_all["class_names"]

    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Phase 15 Baseline: Unmodified Phase 13 Model on Real ESP32-S3 CSI", fontsize=12, fontweight="bold")
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45, ha="right")
    plt.yticks(tick_marks, classes)

    # Label values in matrix
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], "d"),
                     horizontalalignment="center",
                     color="white" if cm[i, j] > thresh else "black")

    plt.ylabel("True Physical Activity")
    plt.xlabel("Predicted Class")
    plt.tight_layout()

    cm_path = REPORTS_DIR / "phase15_baseline_confusion_matrix.png"
    plt.savefig(cm_path, dpi=300)
    plt.close()
    print(f"\n[Artifact] Saved baseline confusion matrix plot: {cm_path}")

    # Export Baseline Metrics JSON
    baseline_payload = {
        "model_evaluated": "models/csiformer_phase13_best.pth",
        "dataset": "data/real_csi_dataset",
        "total_windows": len(all_wins),
        "overall_metrics": {
            "accuracy": res_all["accuracy"],
            "fall_recall": res_all["fall_recall"],
            "macro_f1": round(res_all["classification_report"]["macro avg"]["f1-score"], 4),
            "weighted_f1": round(res_all["classification_report"]["weighted avg"]["f1-score"], 4),
            "mean_raw_gate": res_all["mean_raw_gate"],
            "mean_dopp_gate": res_all["mean_dopp_gate"]
        },
        "per_class_metrics": {
            cls_name: {
                "precision": round(res_all["classification_report"][cls_name]["precision"], 4),
                "recall": round(res_all["classification_report"][cls_name]["recall"], 4),
                "f1_score": round(res_all["classification_report"][cls_name]["f1-score"], 4),
                "support": int(res_all["classification_report"][cls_name]["support"])
            }
            for cls_name in res_all["class_names"]
        },
        "split_performance": {
            sp: {
                "accuracy": split_results[sp]["accuracy"],
                "fall_recall": split_results[sp]["fall_recall"],
                "total_windows": split_results[sp]["total_windows"]
            }
            for sp in split_results
        },
        "confusion_matrix": {
            "classes": res_all["class_names"],
            "matrix": res_all["confusion_matrix"]
        }
    }

    metrics_path = REPORTS_DIR / "phase15_baseline_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(baseline_payload, f, indent=2)
    print(f"[Artifact] Saved baseline metrics: {metrics_path}")


if __name__ == "__main__":
    main()
