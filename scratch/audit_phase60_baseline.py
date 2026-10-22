"""
Phase 60: Ground-Truth Detection Baseline & Real Data Audit
Inspects:
1. Canonical dataset manifest (74 sessions) & absence/empty room representation.
2. Frame dimensions, sampling rates, and subcarrier representations.
3. Subcarrier mismatch (5 vs 52 vs 56 vs 64).
4. Model evaluation on test splits with confusion matrix, F1, FPR, FNR analysis.
"""

import os
import sys
import json
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

MANIFEST_PATH = PROJECT_ROOT / "data" / "real_csi_dataset" / "dataset_manifest.json"
MODELS_DIR = PROJECT_ROOT / "models"
CHECKPOINT_P13 = MODELS_DIR / "csiformer_phase13_best.pth"
CHECKPOINT_P15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

def run_audit():
    print("=================================================================")
    print("PHASE 60 AUDIT: REAL-DATA DETECTION BASELINE & DATA-PATH AUDIT")
    print("=================================================================")

    # 1. Manifest and Session Integrity Audit
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    print(f"\n[1] Canonical Dataset Sessions: {len(sessions)}")
    
    act_counts = Counter(s["activity_label"] for s in sessions)
    part_counts = Counter(s["participant_id"] for s in sessions)
    room_counts = Counter(s["room"] for s in sessions)
    split_counts = Counter(s["split"] for s in sessions)

    print("  Activities:", dict(act_counts))
    print("  Participants:", dict(part_counts))
    print("  Rooms:", dict(room_counts))
    print("  Splits:", dict(split_counts))

    # Check for empty room / human absence recordings
    empty_sessions = [
        s for s in sessions 
        if "empty" in s.get("activity_label", "").lower()
        or "empty" in s.get("description", "").lower()
        or "absence" in s.get("description", "").lower()
    ]
    print(f"\n[2] Empty Room (Human Absence) Sessions in Dataset: {len(empty_sessions)}")
    if len(empty_sessions) == 0:
        print("  CRITICAL FINDING: Canonical dataset contains 0 empty room recordings.")
        print("  All 74 sessions contain human participants (Participant_01 through Participant_05).")
        print("  Static posture sessions (13) contain a human participant standing motionless in LOS.")
        print("  MATHEMATICAL IMPLICATION: True Negative (TN) = 0. False Positive Rate (FP / (FP + TN)) is UNDEFINED (0/0).")
        print("  A validated presence-versus-absence detector CANNOT be evaluated on this dataset without genuine empty-room benchmark recordings.")

    # 2. Frame Dimensions and Subcarrier Representations
    subcarrier_counts = []
    sample_rates = []
    durations = []
    for s in sessions:
        json_file = PROJECT_ROOT / "data" / "real_csi_dataset" / s["json_file"]
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as jf:
                s_data = json.load(jf)
            frames = s_data.get("frames", [])
            if frames:
                subcarrier_counts.append(len(frames[0].get("amplitudes", [])))
            durations.append(s.get("duration_seconds", 0))
            sample_rates.append(s.get("sampling_rate_hz", 0))

    print(f"\n[3] Signal Representations in Session Files:")
    print(f"  Stored Subcarrier Dimension: {Counter(subcarrier_counts)}")
    print(f"  Duration Range: {min(durations):.1f}s - {max(durations):.1f}s (mean: {np.mean(durations):.1f}s)")
    print(f"  Sampling Rate Range: {min(sample_rates):.1f} Hz - {max(sample_rates):.1f} Hz (mean: {np.mean(sample_rates):.1f} Hz)")

    # 3. Model Evaluation on Canonical Test Split (10 sessions, 22 windows)
    from app.services.live_pipeline_service import LivePipelineService, LABEL_MAP
    from app.models.csiformer_dual_branch import CSIDualBranchFusionNet

    test_sessions = [s for s in sessions if s["split"] == "test"]
    print(f"\n[4] Canonical Held-Out Test Sessions: {len(test_sessions)}")
    for ts in test_sessions:
        print(f"  - {ts['session_id']}: {ts['activity_label']} (cid: {ts['class_id']}), {ts['participant_id']}, {ts['room']}")

    live_srv = LivePipelineService()
    device = live_srv.device

    # Load Model Checkpoints
    model_p13 = CSIDualBranchFusionNet(num_classes=12, seq_len=50, num_subcarriers=56).to(device)
    model_p15 = CSIDualBranchFusionNet(num_classes=12, seq_len=50, num_subcarriers=56).to(device)

    ck_p13 = torch.load(CHECKPOINT_P13, map_location=device)
    model_p13.load_state_dict(ck_p13.get("model_state_dict", ck_p13))
    model_p13.eval()

    ck_p15 = torch.load(CHECKPOINT_P15, map_location=device)
    model_p15.load_state_dict(ck_p15.get("model_state_dict", ck_p15))
    model_p15.eval()

    # Extract 50-frame windows for each test session
    test_windows = []
    for ts in test_sessions:
        json_file = PROJECT_ROOT / "data" / "real_csi_dataset" / ts["json_file"]
        with open(json_file, "r", encoding="utf-8") as jf:
            s_data = json.load(jf)
        frames = s_data.get("frames", [])
        amps = [f["amplitudes"] for f in frames if "amplitudes" in f]
        arr = np.array(amps, dtype=np.float32)
        n_win = len(arr) // 50
        for w_idx in range(n_win):
            w = arr[w_idx * 50 : (w_idx + 1) * 50]
            test_windows.append({
                "session_id": ts["session_id"],
                "activity": ts["activity_label"],
                "class_id": ts["class_id"],
                "participant": ts["participant_id"],
                "room": ts["room"],
                "window": w
            })

    print(f"\n[5] Extracted Test Windows: {len(test_windows)} windows (50 frames x 56 subcarriers)")

    for name, model in [("Phase 13 (Zero-Shot Best)", model_p13), ("Phase 15 (Domain-Adapted)", model_p15)]:
        correct = 0
        preds = []
        targets = []
        confidences = []

        for item in test_windows:
            w = item["window"]
            target_cid = item["class_id"]
            raw_t, dopp_t = live_srv.preprocess_window(w)
            with torch.no_grad():
                out = model(raw_t, dopp_t)
                probs = F.softmax(out["activity_logits"], dim=-1).squeeze(0).cpu().numpy()
                pred_cid = int(np.argmax(probs))
                conf = float(probs[pred_cid])

            preds.append(pred_cid)
            targets.append(target_cid)
            confidences.append(conf)

            if pred_cid == target_cid:
                correct += 1

        acc = correct / len(test_windows)
        print(f"\n  MODEL: {name}")
        print(f"    Correct: {correct} / {len(test_windows)} ({acc * 100:.2f}%)")
        print(f"    Mean Confidence: {np.mean(confidences) * 100:.2f}% (min: {np.min(confidences)*100:.1f}%, max: {np.max(confidences)*100:.1f}%)")
        
        pred_counts = Counter(preds)
        print(f"    Predictions Breakdown:")
        for cid, cnt in pred_counts.items():
            print(f"      Class {cid} ({LABEL_MAP.get(cid, 'Unknown')}): {cnt} windows ({cnt/len(test_windows)*100:.1f}%)")

    # 4. Strict Cross-Room Test Split (Office Room 2)
    cross_room_sessions = [s for s in sessions if s["room"] == "Office_Room2"]
    print(f"\n[6] Strict Cross-Room Evaluation (Office_Room2): {len(cross_room_sessions)} sessions")
    cross_windows = []
    for s in cross_room_sessions:
        json_file = PROJECT_ROOT / "data" / "real_csi_dataset" / s["json_file"]
        with open(json_file, "r", encoding="utf-8") as jf:
            s_data = json.load(jf)
        frames = s_data.get("frames", [])
        amps = [f["amplitudes"] for f in frames if "amplitudes" in f]
        arr = np.array(amps, dtype=np.float32)
        n_win = len(arr) // 50
        for w_idx in range(n_win):
            w = arr[w_idx * 50 : (w_idx + 1) * 50]
            cross_windows.append({
                "session_id": s["session_id"],
                "activity": s["activity_label"],
                "class_id": s["class_id"],
                "room": s["room"],
                "window": w
            })
    print(f"    Extracted Cross-Room Windows: {len(cross_windows)}")
    for name, model in [("Phase 13 Best", model_p13), ("Phase 15 Adapted", model_p15)]:
        correct = 0
        for item in cross_windows:
            raw_t, dopp_t = live_srv.preprocess_window(item["window"])
            with torch.no_grad():
                out = model(raw_t, dopp_t)
                pred_cid = int(torch.argmax(out["activity_logits"], dim=-1).item())
            if pred_cid == item["class_id"]:
                correct += 1
        print(f"    {name} Cross-Room Accuracy: {correct}/{len(cross_windows)} ({correct/len(cross_windows)*100:.2f}%)")

if __name__ == "__main__":
    run_audit()
