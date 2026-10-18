"""
CSIFormer Phase 16 — Automated Test Suite.

Validates:
1. Dataset manifest integrity and packet count matching.
2. HAR taxonomy and class mapping consistency.
3. Raw CSI preservation in RealCSICollector.
4. Packet loss, sequence continuity, and metadata logging.
5. Sliding window non-overlap and duplicate window detection.
6. Participant split leakage detection.
7. Wilson score confidence interval computation.
8. Calibrated physics preprocessor Doppler scaling.
9. Bit-for-bit checkpoint integrity and forward pass compatibility.
10. Fall recall and false alarm metric calculations.
"""

import sys
import os
import math
import json
import pytest
import numpy as np
import torch
from pathlib import Path

# Ensure backend directory is in python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from app.services.real_csi_collector import RealCSICollector
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor, CalibratedPhysicsPreprocessor

def wilson_score_interval(positives: int, total: int, confidence: float = 0.95):
    if total == 0:
        return 0.0, 0.0
    z = 1.96
    p = positives / total
    denom = 1.0 + (z**2) / total
    center = (p + (z**2) / (2.0 * total)) / denom
    margin = (z * math.sqrt((p * (1.0 - p) / total) + (z**2) / (4.0 * (total**2)))) / denom
    return max(0.0, center - margin), min(1.0, center + margin)

BASE_DIR = ROOT_DIR
DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MODELS_DIR = BASE_DIR / "models"


def test_dataset_manifest_integrity():
    """Verify that all manifest sessions exist on disk and packet counts match."""
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    assert manifest_path.exists(), "dataset_manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) == 23, f"Expected 23 sessions, got {len(sessions)}"

    for s in sessions:
        json_file = DATASET_DIR / s["json_file"]
        assert json_file.exists(), f"Session file {json_file} does not exist"
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = data["frames"]
        assert len(frames) == s["packet_count"], f"Packet count mismatch in {s['session_id']}"


def test_label_mapping_consistency():
    """Verify that all session labels correspond to expected class mappings."""
    valid_classes = {"push_pull": 0, "clap": 2, "static": 6, "sit": 8, "fall": 9, "walk": 11}
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for s in manifest["sessions"]:
        label = s["activity_label"]
        cid = s["class_id"]
        assert label in valid_classes, f"Invalid activity label: {label}"
        assert cid == valid_classes[label], f"Class ID {cid} mismatch for label {label}"


def test_raw_csi_preservation_in_collector(tmp_path):
    """Verify that RealCSICollector preserves raw uninterpolated CSI in recorded frames."""
    collector = RealCSICollector(data_dir=str(tmp_path))
    collector.start_session_recording(
        session_name="test_raw_preservation",
        room_type="Laboratory",
        participant_id="P_Test",
        activity_label="walk",
        orientation="LOS_0deg",
        ground_truth_confirmed=True
    )

    # Ingest a raw frame with 5 subcarriers
    fake_frame = {
        "timestamp": 1000.0,
        "sequence": 1,
        "mac": "ESP32-S3-TEST",
        "rssi": -55.0,
        "noise_floor": -95.0,
        "num_subcarriers": 5,
        "raw_amplitudes": [10.0, 12.0, 15.0, 14.0, 11.0],
        "raw_phases": [0.1, 0.2, 0.3, 0.2, 0.1]
    }
    collector._process_parsed_frame(fake_frame)
    res = collector.stop_session_recording()

    with open(res["json_path"], "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    frame = saved_data["frames"][0]
    assert "raw_amplitudes" in frame, "raw_amplitudes must be preserved in recorded frame"
    assert frame["raw_num_subcarriers"] == 5, "raw_num_subcarriers must be 5"
    assert len(frame["raw_amplitudes"]) == 5, "raw_amplitudes length must be 5"
    assert len(frame["amplitudes"]) == 56, "interpolated amplitudes must be 56"


def test_metadata_packet_loss_tracking(tmp_path):
    """Verify that RealCSICollector tracks session packet loss and duration in metadata."""
    collector = RealCSICollector(data_dir=str(tmp_path))
    collector.packets_lost = 5
    collector.start_session_recording(
        session_name="test_loss_tracking",
        room_type="Bedroom",
        participant_id="P_Test",
        activity_label="fall"
    )

    # Simulate 2 lost packets during session
    collector.packets_lost += 2
    collector.recorded_frames.append({
        "timestamp": 1001.0, "sequence": 10, "rssi": -60.0, "noise": -90.0,
        "amplitudes": [1.0] * 56, "phases": [0.0] * 56
    })

    res = collector.stop_session_recording()
    with open(res["json_path"], "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    assert meta["packets_lost"] == 2, f"Expected 2 lost packets in session, got {meta['packets_lost']}"
    assert "duration_seconds" in meta, "duration_seconds must be logged in metadata"
    assert "loss_rate" in meta, "loss_rate must be logged in metadata"


def _load_real_dataset_windows(split: str = "all"):
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    if split != "all":
        sessions = [s for s in sessions if s["split"] == split]

    windows, labels, session_ids, participants = [], [], [], []
    for s in sessions:
        json_path = DATASET_DIR / s["json_file"]
        if not json_path.exists():
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = data["frames"]
        cid = s["class_id"]
        sid = s["session_id"]
        pid = s["participant_id"]
        mat = np.array([fr["amplitudes"] for fr in frames], dtype=np.float32)
        for start_idx in range(0, len(mat) - 50 + 1, 50):
            win = mat[start_idx:start_idx + 50, :56]
            if win.shape == (50, 56) and np.isfinite(win).all():
                windows.append(win)
                labels.append(cid)
                session_ids.append(sid)
                participants.append(pid)
    return np.array(windows, dtype=np.float32), np.array(labels, dtype=np.int64), session_ids, participants


def test_sliding_window_non_overlap():
    """Verify that window extraction produces strictly non-overlapping windows."""
    windows, labels, sessions, participants = _load_real_dataset_windows("all")
    assert len(windows) == 49, f"Expected 49 non-overlapping windows, got {len(windows)}"

    # Check window shape and values
    for w in windows:
        assert w.shape == (50, 56), f"Unexpected window shape: {w.shape}"
        assert np.isfinite(w).all(), "Window must contain only finite numbers"

    # Check hash uniqueness (no exact duplicate windows across sessions)
    hashes = set(hash(w.tobytes()) for w in windows)
    assert len(hashes) == 49, "Duplicate window detected across dataset"


def test_participant_split_leakage_detection():
    """Verify that participant distribution across splits correctly flags seen-subject overlap."""
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    train_pids = set(s["participant_id"] for s in manifest["sessions"] if s["split"] == "train")
    test_pids = set(s["participant_id"] for s in manifest["sessions"] if s["split"] == "test")

    # In Phase 15 dataset, Participant_02 was in both train and test
    overlap = train_pids.intersection(test_pids)
    assert "Participant_02" in overlap, "Expected Participant_02 overlap to be detected"


def test_wilson_score_interval():
    """Verify Wilson score confidence interval computation."""
    low, high = wilson_score_interval(positives=1, total=2, confidence=0.95)
    assert 0.09 < low < 0.10, f"Expected lower bound ~0.095, got {low}"
    assert 0.90 < high < 0.91, f"Expected upper bound ~0.905, got {high}"

    # Edge cases
    assert wilson_score_interval(0, 0) == (0.0, 0.0)
    low_0, high_0 = wilson_score_interval(0, 2)
    assert low_0 == 0.0
    assert 0.65 < high_0 < 0.66


def test_calibrated_physics_preprocessor():
    """Verify that CalibratedPhysicsPreprocessor correctly scales Doppler frequency axis."""
    prep = CalibratedPhysicsPreprocessor(carrier_freq=2.442e9, source_rate_hz=35.58, target_timesteps=50, target_channels=56)
    assert abs(prep.doppler_scale - (5.825 / 2.442)) < 1e-4

    fake_csi = np.ones((50, 56), dtype=np.float32) * 15.0
    dopp = prep.compute_doppler_spectrogram(fake_csi)
    assert dopp.shape == (50, 56)
    assert np.isfinite(dopp).all()


def test_model_checkpoints_bit_integrity():
    """Verify bit-for-bit hashes of both production and adapted checkpoints."""
    import hashlib
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), "Production checkpoint models/csiformer_phase13_best.pth must exist"
    assert p15_path.exists(), "Adapted checkpoint models/csiformer_phase15_adapted.pth must exist"

    p13_hash = hashlib.md5(p13_path.read_bytes()).hexdigest()
    p15_hash = hashlib.md5(p15_path.read_bytes()).hexdigest()

    assert p13_hash == "383b4d98c08f8970b0443738f170ec01", f"Production checkpoint hash corrupted: {p13_hash}"
    assert p15_hash == "ab3d97a04d78edf75d807178772bc828", f"Adapted checkpoint hash corrupted: {p15_hash}"

    # Forward pass test
    device = torch.device("cpu")
    m = CSIDualBranchFusionNet(num_subcarriers=56, doppler_bins=56, seq_len=50, num_classes=12)
    m.load_state_dict(torch.load(p13_path, map_location=device, weights_only=True))
    m.eval()

    dummy_raw = torch.randn(1, 50, 56)
    dummy_dopp = torch.randn(1, 50, 56)
    with torch.no_grad():
        out = m(dummy_raw, dummy_dopp)
    assert "activity_logits" in out
    assert out["activity_logits"].shape == (1, 12)


def test_fall_detection_metrics_calculation():
    """Verify calculation of fall sensitivity, specificity, and false alarms."""
    y_true = np.array([9, 9, 0, 2, 11])  # 2 falls, 3 non-falls
    y_pred = np.array([9, 0, 0, 2, 9])   # 1 TP, 1 FN, 1 FP, 2 TN

    is_fall_true = (y_true == 9)
    is_fall_pred = (y_pred == 9)

    tp = np.sum(is_fall_true & is_fall_pred)
    fn = np.sum(is_fall_true & (~is_fall_pred))
    fp = np.sum((~is_fall_true) & is_fall_pred)
    tn = np.sum((~is_fall_true) & (~is_fall_pred))

    assert tp == 1
    assert fn == 1
    assert fp == 1
    assert tn == 2

    recall = tp / (tp + fn)
    specificity = tn / (tn + fp)
    assert recall == 0.5
    assert abs(specificity - (2.0 / 3.0)) < 1e-4
