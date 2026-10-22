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

def load_session_windows(session_entry: Dict[str, Any]) -> List[np.ndarray]:
    """Loads a session's JSON file and slices into non-overlapping [50, 56] windows."""
    json_path = DATASET_DIR / session_entry["json_file"]
    if not json_path.exists():
        # try without prefix or with relative path
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
    return windows

def run_inference_on_windows(
    model: CSIDualBranchFusionNet,
    preprocessor: PhysicsCSIPreprocessor,
    windows: List[np.ndarray],
    device: torch.device
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Runs forward pass through exact production preprocessing and model."""
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

def main():
    print("=" * 80)
    print("PHASE 59 — END-TO-END ACTIVITY DETECTION VALIDATION SCRIPT")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Canonical Manifest Test Split
    canonical_test_sessions = [s for s in manifest["sessions"] if s.get("split") == "test"]
    print(f"\n[1] Canonical Manifest Test Split: {len(canonical_test_sessions)} sessions")
    for s in canonical_test_sessions:
        print(f"    Session {s['session_id']}: {s['activity_label']} (cid={s.get('class_id')}), P={s['participant_id']}, Room={s['room']}, frames={s['packet_count']}, wins={s['packet_count']//50}")

    # 2. Strict Cross-Room Test Split (Phase 34)
    split_gen = ParticipantIndependentSplitGenerator(manifest_path)
    strict_split = split_gen.generate_strict_cross_room_split(output_manifest_path=None)
    strict_test_sessions = [s for s in strict_split["sessions"] if s.get("split") == "test"]
    print(f"\n[2] Strict Cross-Room Test Split (Phase 34): {len(strict_test_sessions)} sessions")
    for s in strict_test_sessions:
        print(f"    Session {s['session_id']}: {s['activity_label']} (cid={s.get('class_id')}), P={s['participant_id']}, Room={s['room']}, frames={s['packet_count']}, wins={s['packet_count']//50}")

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
        print(f"Loaded {name} successfully.")

    # Run evaluations on both test sets
    test_sets = {
        "canonical_test_split (10 sessions, 22 windows)": canonical_test_sessions,
        "strict_cross_room_test_split (5 sessions, 11 windows)": strict_test_sessions
    }

    for test_set_name, test_sessions in test_sets.items():
        print(f"\n{'#' * 80}")
        print(f"EVALUATING TEST SET: {test_set_name}")
        print(f"{'#' * 80}")

        # Assemble windows and ground truths
        all_windows = []
        meta_list = []
        for s in test_sessions:
            wins = load_session_windows(s)
            for w in wins:
                all_windows.append(w)
                meta_list.append({
                    "session_id": s["session_id"],
                    "activity_label": s["activity_label"],
                    "manifest_class_id": s.get("class_id"),
                    "participant_id": s["participant_id"],
                    "room": s["room"]
                })

        print(f"Total extracted windows: {len(all_windows)}")

        # Count activities
        act_counts = {}
        for m in meta_list:
            act_counts[m["activity_label"]] = act_counts.get(m["activity_label"], 0) + 1
        print(f"Activity window counts: {act_counts}")

        for model_name, model in models.items():
            preprocessor = checkpoints[model_name]["preprocessor"]
            preds, probs, fusion_w = run_inference_on_windows(model, preprocessor, all_windows, device)

            print(f"\n--- Model: {model_name} on {test_set_name} ---")
            print(f"Average Fusion Weights: Raw={np.mean(fusion_w[:, 0]):.3f}, Doppler={np.mean(fusion_w[:, 1]):.3f}")

            # Print raw predictions
            print("Per-window predictions:")
            for i, (m, p, prob) in enumerate(zip(meta_list, preds, probs)):
                top1_prob = prob[p]
                lbl_name = LABEL_MAP.get(p, f"Class_{p}")
                print(f"  Win {i:02d} | True: {m['activity_label']:10s} (cid={m['manifest_class_id']}) | Pred: {p:2d} ({lbl_name:25s}) | Conf: {top1_prob:.4f} | Session: {m['session_id']}")

            # Analysis 1: Direct comparison against manifest class_id (the 6-class subset with aliases 6 and 8)
            y_true_alias = np.array([m["manifest_class_id"] for m in meta_list])
            unique_alias = sorted(list(set(y_true_alias)))
            alias_names = [LABEL_MAP.get(c, f"Class_{c}") for c in unique_alias]
            
            # Note: what if model predicted a class not in unique_alias? (e.g. class 1 or 7)
            # Full 12-class confusion matrix:
            cm_12 = confusion_matrix(y_true_alias, preds, labels=list(range(12)))
            acc_alias = np.mean(y_true_alias == preds)

            print(f"\n[Alias Mapping Evaluation (Classes: {unique_alias})]")
            print(f"  Overall Accuracy: {acc_alias:.4f} ({np.sum(y_true_alias == preds)}/{len(y_true_alias)})")
            
            # Filtered classification report on evaluated classes
            rep_alias = classification_report(y_true_alias, preds, labels=unique_alias, target_names=alias_names, output_dict=True, zero_division=0)
            print("  Classification Report (evaluated classes):")
            for c_id, c_name in zip(unique_alias, alias_names):
                sub = rep_alias[c_name]
                print(f"    {c_name:25s} | Prec: {sub['precision']:.4f} | Rec: {sub['recall']:.4f} | F1: {sub['f1-score']:.4f} | Support: {sub['support']}")
            print(f"    Macro F1: {rep_alias['macro avg']['f1-score']:.4f}")

            # Confusion matrix restricted to true classes
            cm_subset = confusion_matrix(y_true_alias, preds, labels=unique_alias)
            print("  Confusion Matrix on true classes (rows=True, cols=Pred):")
            print("    Labels:", alias_names)
            for row, c_name in zip(cm_subset, alias_names):
                print(f"    {c_name:25s}: {row.tolist()}")

            # Check predictions outside true classes
            outside_count = np.sum([p not in unique_alias for p in preds])
            if outside_count > 0:
                print(f"  WARNING: {outside_count} predictions fell outside the evaluated true classes: {[p for p in preds if p not in unique_alias]}")

            # Analysis 2: Strict 3-Class Dynamic Subset (0: push_pull, 2: clap, 11: walk)
            dynamic_mask = np.array([m["activity_label"] in ["push_pull", "clap", "walk"] for m in meta_list])
            if np.any(dynamic_mask):
                y_true_dyn = y_true_alias[dynamic_mask]
                preds_dyn = preds[dynamic_mask]
                dyn_classes = [0, 2, 11]
                dyn_names = [LABEL_MAP[c] for c in dyn_classes]
                acc_dyn = np.mean(y_true_dyn == preds_dyn)
                rep_dyn = classification_report(y_true_dyn, preds_dyn, labels=dyn_classes, target_names=dyn_names, output_dict=True, zero_division=0)
                cm_dyn = confusion_matrix(y_true_dyn, preds_dyn, labels=dyn_classes)
                print(f"\n[Semantically Valid 3-Class Dynamic Subset (push_pull, clap, walk)]")
                print(f"  Windows evaluated: {np.sum(dynamic_mask)}")
                print(f"  3-Class Accuracy: {acc_dyn:.4f} ({np.sum(y_true_dyn == preds_dyn)}/{len(y_true_dyn)})")
                for c_id, c_name in zip(dyn_classes, dyn_names):
                    sub = rep_dyn[c_name]
                    print(f"    {c_name:25s} | Prec: {sub['precision']:.4f} | Rec: {sub['recall']:.4f} | F1: {sub['f1-score']:.4f} | Support: {sub['support']}")
                print(f"    Macro F1: {rep_dyn['macro avg']['f1-score']:.4f}")
                print("  Confusion Matrix (rows=True, cols=Pred):")
                for row, c_name in zip(cm_dyn, dyn_names):
                    print(f"    {c_name:25s}: {row.tolist()}")

if __name__ == '__main__':
    main()
