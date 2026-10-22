"""
CSIFormer Phase 59.1 — Evaluation Integrity & Metric Reconciliation Audit

Performs authoritative, independent re-computation of all Phase 59 metrics:
1. Canonical Test Split (10 sessions, 22 physical windows)
2. Strict Cross-Room Split (5 sessions, 11 physical windows)
For both checkpoints:
- models/csiformer_phase13_best.pth
- models/csiformer_phase15_adapted.pth
Verifies confusion matrix sums, per-class supports, and out-of-vocabulary predictions.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "backend"))

from app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor, CalibratedPhysicsPreprocessor
from app.services.live_pipeline_service import LivePipelineService, LABEL_MAP
from app.services.split_generator import ParticipantIndependentSplitGenerator

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"

def get_session_windows(session_entry: Dict[str, Any]) -> Tuple[List[np.ndarray], int]:
    json_path = DATASET_DIR / session_entry["json_file"]
    if not json_path.exists():
        json_path = DATASET_DIR / Path(session_entry["json_file"]).name
    if not json_path.exists():
        raise FileNotFoundError(f"Missing file: {session_entry['json_file']}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    frames = data["frames"]
    mat = np.array([fr["amplitudes"] for fr in frames], dtype=np.float32)
    n_frames = len(mat)

    windows = []
    step = 50
    for start in range(0, n_frames - 50 + 1, step):
        win = mat[start:start + 50, :56]
        if win.shape == (50, 56) and np.isfinite(win).all():
            windows.append(win)
    return windows, n_frames

def run_authoritative_inference(
    model: CSIDualBranchFusionNet,
    preprocessor: PhysicsCSIPreprocessor,
    windows: List[np.ndarray],
    device: torch.device
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    preds = []
    probs_list = []
    fusion_weights = []

    with torch.no_grad():
        for win in windows:
            # Branch A: Per-subcarrier temporal z-score normalization
            amp_mean = win.mean(axis=0, keepdims=True)
            amp_std = win.std(axis=0, keepdims=True) + 1e-6
            norm_raw = (win - amp_mean) / amp_std
            t_raw = torch.tensor(norm_raw, dtype=torch.float32).unsqueeze(0).to(device)

            # Branch B: STFT Doppler Spectrogram
            dopp_mat = preprocessor.compute_doppler_spectrogram(win)
            t_dopp = torch.tensor(dopp_mat, dtype=torch.float32).unsqueeze(0).to(device)

            out = model(t_raw, t_dopp)
            logits = out["activity_logits"]
            probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()
            pred_class = int(np.argmax(probs))

            preds.append(pred_class)
            probs_list.append(probs)
            gw = out.get("fusion_weights")
            if gw is not None:
                fusion_weights.append([float(gw[0, 0].item()), float(gw[0, 1].item())])
            else:
                fusion_weights.append([0.5, 0.5])

    return np.array(preds), np.array(probs_list), np.array(fusion_weights)

def audit():
    print("=" * 80)
    print("CSIFORMER PHASE 59.1 — EVALUATION INTEGRITY & AUDIT SCRIPT")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Authoritative Execution Device: {device}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Canonical Manifest Test Split
    canonical_test_sessions = [s for s in manifest["sessions"] if s.get("split") == "test"]
    print(f"\n[Audit Target 1] Canonical Manifest Test Split: {len(canonical_test_sessions)} sessions")
    can_windows = []
    can_meta = []
    for s in canonical_test_sessions:
        wins, n_frames = get_session_windows(s)
        print(f"  Session {s['session_id'][:35]:35s} | Act: {s['activity_label']:10s} | CID: {s.get('class_id'):2d} | JSON Frames: {n_frames:3d} | Wins: {len(wins)}")
        for w in wins:
            can_windows.append(w)
            can_meta.append({
                "session_id": s["session_id"],
                "activity_label": s["activity_label"],
                "class_id": s.get("class_id"),
                "participant_id": s["participant_id"],
                "room": s["room"]
            })
    print(f"  -> Total Canonical Physical Windows: {len(can_windows)}")
    assert len(can_windows) == 22, f"Expected 22 canonical windows, got {len(can_windows)}"

    # 2. Strict Cross-Room Test Split (Phase 34)
    split_gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    strict_split = split_gen.generate_strict_cross_room_split(output_manifest_path=None)
    strict_test_sessions = [s for s in strict_split["sessions"] if s.get("split") == "test"]
    print(f"\n[Audit Target 2] Strict Cross-Room Test Split: {len(strict_test_sessions)} sessions")
    strict_windows = []
    strict_meta = []
    for s in strict_test_sessions:
        wins, n_frames = get_session_windows(s)
        print(f"  Session {s['session_id'][:35]:35s} | Act: {s['activity_label']:10s} | CID: {s.get('class_id'):2d} | JSON Frames: {n_frames:3d} | Wins: {len(wins)}")
        for w in wins:
            strict_windows.append(w)
            strict_meta.append({
                "session_id": s["session_id"],
                "activity_label": s["activity_label"],
                "class_id": s.get("class_id"),
                "participant_id": s["participant_id"],
                "room": s["room"]
            })
    print(f"  -> Total Strict Cross-Room Physical Windows: {len(strict_windows)}")
    assert len(strict_windows) == 11, f"Expected 11 strict windows, got {len(strict_windows)}"

    # Load Models
    checkpoints = {
        "phase13_best": {
            "path": BASE_DIR / "models" / "csiformer_phase13_best.pth",
            "preprocessor": PhysicsCSIPreprocessor(
                carrier_freq=2.442e9,
                source_rate_hz=30.0,
                target_timesteps=50,
                target_channels=56,
                stft_window=32,
                stft_noverlap=24,
                stft_nfft=64
            )
        },
        "phase15_adapted": {
            "path": BASE_DIR / "models" / "csiformer_phase15_adapted.pth",
            "preprocessor": CalibratedPhysicsPreprocessor(
                carrier_freq=2.442e9,
                source_rate_hz=35.58,
                target_timesteps=50,
                target_channels=56,
                stft_window=64,
                stft_noverlap=48,
                stft_nfft=128
            )
        }
    }

    models = {}
    for name, cfg in checkpoints.items():
        m = CSIDualBranchFusionNet(
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
        sd = torch.load(cfg["path"], map_location=device, weights_only=True)
        m.load_state_dict(sd)
        m.eval()
        models[name] = m

    eval_splits = {
        "canonical_test_split": (can_windows, can_meta, 22),
        "strict_cross_room_test_split": (strict_windows, strict_meta, 11)
    }

    results = {}

    for split_name, (wins, meta, expected_total) in eval_splits.items():
        print(f"\n{'=' * 80}")
        print(f"AUDITING SPLIT: {split_name} (Expected Total: {expected_total})")
        print(f"{'=' * 80}")
        y_true = np.array([m["class_id"] for m in meta])
        unique_classes = sorted(list(set(y_true)))
        class_names = [LABEL_MAP[c] for c in unique_classes]

        # Activity breakdown
        act_counts = {}
        for m in meta:
            act_counts[m["activity_label"]] = act_counts.get(m["activity_label"], 0) + 1
        print(f"Ground Truth Activity Window Counts: {act_counts}")

        results[split_name] = {}

        for m_name, model in models.items():
            prep = checkpoints[m_name]["preprocessor"]
            preds, probs, f_w = run_authoritative_inference(model, prep, wins, device)

            # Verification 1: Array lengths
            assert len(preds) == expected_total, f"Length mismatch: {len(preds)} != {expected_total}"
            correct_count = int(np.sum(y_true == preds))
            accuracy = correct_count / expected_total

            # Verification 2: Full 12-class confusion matrix (contains all 12 classes)
            cm_12 = confusion_matrix(y_true, preds, labels=list(range(12)))
            cm_12_sum = int(np.sum(cm_12))
            assert cm_12_sum == expected_total, f"CM 12 sum {cm_12_sum} != {expected_total}"

            # Verification 3: Complete Confusion Matrix with Explicit Outside Column
            # Build an augmented table where cols = unique_classes + ['Outside']
            # This guarantees that each row sums to EXACTLY its true class support,
            # and the total of the table equals EXACTLY expected_total!
            table_rows = []
            support_list = []
            for cid in unique_classes:
                idx_mask = (y_true == cid)
                c_support = int(np.sum(idx_mask))
                support_list.append(c_support)
                c_preds = preds[idx_mask]
                
                in_class_counts = [int(np.sum(c_preds == target_c)) for target_c in unique_classes]
                outside_count_row = int(np.sum([p not in unique_classes for p in c_preds]))
                table_rows.append(in_class_counts + [outside_count_row])

            table_rows = np.array(table_rows)
            table_row_sums = table_rows.sum(axis=1).tolist()
            assert table_row_sums == support_list, f"Row sums {table_row_sums} != supports {support_list}"
            assert sum(table_row_sums) == expected_total, f"Total table sum {sum(table_row_sums)} != {expected_total}"

            # Outside predictions across all classes
            outside_preds = [int(p) for p in preds if p not in unique_classes]
            outside_total = len(outside_preds)

            rep = classification_report(y_true, preds, labels=unique_classes, target_names=class_names, output_dict=True, zero_division=0)

            print(f"\n--- Checkpoint: {m_name} ---")
            print(f"  Overall Accuracy: {accuracy:.4f} ({correct_count}/{expected_total})")
            print(f"  Macro-Precision:  {rep['macro avg']['precision']:.4f}")
            print(f"  Macro-Recall:     {rep['macro avg']['recall']:.4f}")
            print(f"  Macro-F1:         {rep['macro avg']['f1-score']:.4f}")
            print(f"  Average Fusion Weights: Raw={np.mean(f_w[:, 0]):.3f}, Doppler={np.mean(f_w[:, 1]):.3f}")
            print(f"  Full 12-Class Confusion Matrix Sum: {cm_12_sum} (EQUAL to evaluated windows)")
            print(f"  Augmented Table Total Sum:          {int(table_rows.sum())} (EQUAL to evaluated windows)")
            print(f"  Per-class Support Sum:              {sum(support_list)} (EQUAL to evaluated windows)")
            print(f"  Outside Predictions Count:          {outside_total} ({outside_preds})")

            print("  Per-Class Metrics & Supports:")
            for cid, cname, sup in zip(unique_classes, class_names, support_list):
                sub = rep[cname]
                print(f"    {cname:25s} (cid={cid:2d}) | Prec: {sub['precision']:.4f} | Rec: {sub['recall']:.4f} | F1: {sub['f1-score']:.4f} | Support: {sup}")

            print("  Reconciled Confusion Matrix (Rows=True, Cols=Evaluated Classes + [Outside]):")
            col_headers = [c[:8] for c in class_names] + ["[Outside]"]
            print(f"    {'True Activity':25s} | {' | '.join(f'{h:>9s}' for h in col_headers)} | Total Support")
            for cname, row, sup in zip(class_names, table_rows, support_list):
                row_str = ' | '.join(f'{val:9d}' for val in row)
                print(f"    {cname:25s} | {row_str} | {sup:9d}")

            # Dynamic 3-class subset (push_pull: 0, clap: 2, walk: 11)
            dyn_mask = np.array([m["activity_label"] in ["push_pull", "clap", "walk"] for m in meta])
            y_dyn = y_true[dyn_mask]
            p_dyn = preds[dyn_mask]
            dyn_classes = [0, 2, 11]
            dyn_names = [LABEL_MAP[c] for c in dyn_classes]
            rep_dyn = classification_report(y_dyn, p_dyn, labels=dyn_classes, target_names=dyn_names, output_dict=True, zero_division=0)
            cm_dyn = confusion_matrix(y_dyn, p_dyn, labels=dyn_classes)
            acc_dyn = np.mean(y_dyn == p_dyn)

            print(f"  Semantically Valid 3-Class Dynamic Subset (N={len(y_dyn)}):")
            print(f"    3-Class Accuracy: {acc_dyn:.4f} ({int(np.sum(y_dyn == p_dyn))}/{len(y_dyn)})")
            print(f"    3-Class Macro-F1: {rep_dyn['macro avg']['f1-score']:.4f}")

            results[split_name][m_name] = {
                "accuracy": accuracy,
                "correct": correct_count,
                "total": expected_total,
                "macro_precision": rep['macro avg']['precision'],
                "macro_recall": rep['macro avg']['recall'],
                "macro_f1": rep['macro avg']['f1-score'],
                "table_rows": table_rows.tolist(),
                "support_list": support_list,
                "outside_count": outside_total,
                "outside_preds": outside_preds,
                "dyn_accuracy": float(acc_dyn),
                "dyn_f1": float(rep_dyn['macro avg']['f1-score']),
                "dyn_total": int(len(y_dyn))
            }

    print("\n" + "=" * 80)
    print("AUDIT SUMMARY MATRIX:")
    print("=" * 80)
    for s_name, s_res in results.items():
        print(f"\nSplit: {s_name}")
        for m_name, m_res in s_res.items():
            print(f"  Model {m_name:18s}: Acc = {m_res['accuracy']*100:.2f}% ({m_res['correct']}/{m_res['total']}), Macro-F1 = {m_res['macro_f1']:.4f}, Dyn-Acc = {m_res['dyn_accuracy']*100:.2f}% (N={m_res['dyn_total']})")

if __name__ == "__main__":
    audit()
