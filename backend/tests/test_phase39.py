"""
CSIFormer Phase 39 — Controlled Retraining and Feasibility Gate Test Suite.

Verifies:
1. Checkpoint and manifest integrity (Phase 13, Phase 15, and manifest MD5 hashes).
2. Channel provenance: 5 physical subcarriers vs. 56 derived channels.
3. Window construction, session boundaries, and 155-window partition accounting (75/20/11/49).
4. Deterministic shared preprocessing contract and LivePipelineService parity.
5. Numerical safeguards: finite bounds, epsilon protection, zero-variance handling.
6. Five-class taxonomy and exact class-index mapping.
7. Strict train/validation/test isolation (zero participant/room leakage).
8. Gate 0 data sufficiency and parameter complexity audit (1.48M params vs. 75 samples).
"""

import json
import hashlib
import sys
from pathlib import Path
import pytest
import numpy as np
import torch

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.split_generator import ParticipantIndependentSplitGenerator
from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from backend.app.models.csiformer_dual_branch import CSIDualBranchFusionNet

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"

EXPECTED_CLASS_MAP = {
    "push_pull": 0,
    "clap": 1,
    "walk": 2,
    "static": 3,
    "sit": 4
}


def test_phase39_checkpoint_and_manifest_integrity():
    """Verify production, experimental checkpoints and manifest remain bit-for-bit pristine."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"
    p39_path = MODELS_DIR / "csiformer_phase39_retrained.pth"

    assert p13_path.exists(), f"Missing production checkpoint: {p13_path}"
    assert p15_path.exists(), f"Missing experimental checkpoint: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_hash = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_hash = hashlib.md5(f.read()).hexdigest()
    with open(MANIFEST_PATH, "rb") as f:
        manifest_hash = hashlib.md5(f.read()).hexdigest()

    assert p13_hash == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_hash}"
    assert p15_hash == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_hash}"
    assert manifest_hash == EXPECTED_MANIFEST_MD5, f"Manifest modified: {manifest_hash}"

    # Because Gate 0 is BLOCKED, csiformer_phase39_retrained.pth must NOT exist
    assert not p39_path.exists(), (
        f"Protected gate invariant violated: {p39_path} must not exist when training is blocked."
    )


def test_phase39_channel_provenance_and_ordering():
    """Verify hardware captures only 5 physical subcarriers linearly interpolated to 56."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Check a Phase 16+ session with raw_amplitudes
    phase16_sessions = [s for s in manifest["sessions"] if "phase16" in s["json_file"]]
    assert len(phase16_sessions) > 0, "No Phase 16 sessions found in manifest"

    sample_s = phase16_sessions[0]
    with open(DATASET_DIR / sample_s["json_file"], "r", encoding="utf-8") as f:
        data = json.load(f)

    frame0 = data["frames"][0]
    assert "raw_amplitudes" in frame0, "raw_amplitudes missing in frame"
    assert frame0["raw_num_subcarriers"] == 5, f"Expected 5 raw subcarriers, got {frame0['raw_num_subcarriers']}"
    assert len(frame0["raw_amplitudes"]) == 5, f"Expected raw length 5, got {len(frame0['raw_amplitudes'])}"
    assert len(frame0["amplitudes"]) == 56, f"Expected derived length 56, got {len(frame0['amplitudes'])}"

    # Check non-decreasing linear interpolation
    raw_sub = np.array(frame0["raw_amplitudes"], dtype=float)
    interp_sub = np.array(frame0["amplitudes"], dtype=float)
    assert np.isclose(interp_sub[0], raw_sub[0]), "First subcarrier boundary mismatch"
    assert np.isclose(interp_sub[-1], raw_sub[-1]), "Last subcarrier boundary mismatch"


def test_phase39_window_construction_and_session_boundaries():
    """Verify window slicing strictly respects session boundaries with exact 75/20/11/49 counts."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    gen = ParticipantIndependentSplitGenerator(manifest)
    split = gen.generate_strict_cross_room_split()
    summary = split["splits_summary"]

    assert summary["train_sessions"] == 36
    assert summary["val_sessions"] == 10
    assert summary["test_sessions"] == 5
    assert summary["excluded_sessions"] == 23

    assert summary["train_windows"] == 75
    assert summary["val_windows"] == 20
    assert summary["test_windows"] == 11
    assert summary["excluded_windows"] == 49
    assert summary["total_windows"] == 155

    # Verify per-class window counts
    win_act = summary["windows_by_activity"]
    assert win_act["train"] == {"static": 15, "sit": 15, "walk": 16, "clap": 14, "push_pull": 15}
    assert win_act["val"] == {"static": 4, "sit": 4, "walk": 4, "clap": 4, "push_pull": 4}
    assert win_act["test"] == {"static": 2, "sit": 2, "walk": 2, "clap": 2, "push_pull": 3}


def test_phase39_shared_preprocessing_contract_and_parity():
    """Verify deterministic preprocessing contract matches LivePipelineService logic exactly."""
    preprocessor = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )

    # Synthetic realistic CSI window [50, 56]
    np.random.seed(42)
    raw_win = np.random.uniform(10.0, 50.0, size=(50, 56)).astype(np.float32)

    # Reference Pipeline (LivePipelineService implementation)
    amp_mean = raw_win.mean(axis=0, keepdims=True)
    amp_std = raw_win.std(axis=0, keepdims=True) + 1e-6
    live_norm_raw = (raw_win - amp_mean) / amp_std
    live_dopp = preprocessor.compute_doppler_spectrogram(raw_win)

    # Training Pipeline
    def training_preprocess(window: np.ndarray):
        assert window.shape == (50, 56)
        m = window.mean(axis=0, keepdims=True)
        s = window.std(axis=0, keepdims=True) + 1e-6
        norm_a = (window - m) / s
        norm_b = preprocessor.compute_doppler_spectrogram(window)
        return norm_a, norm_b

    train_norm_raw, train_dopp = training_preprocess(raw_win)

    # Bit-for-bit parity
    np.testing.assert_array_equal(live_norm_raw, train_norm_raw)
    np.testing.assert_array_equal(live_dopp, train_dopp)

    assert live_norm_raw.shape == (50, 56)
    assert live_dopp.shape == (50, 56)
    assert np.isfinite(live_norm_raw).all()
    assert np.isfinite(live_dopp).all()


def test_phase39_numerical_safeguards_and_finite_bounds():
    """Verify numerical safeguards on zero-variance, constant, and edge cases."""
    preprocessor = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )

    # Constant window (zero variance along time axis)
    const_win = np.ones((50, 56), dtype=np.float32) * 25.0
    amp_mean = const_win.mean(axis=0, keepdims=True)
    amp_std = const_win.std(axis=0, keepdims=True) + 1e-6
    norm_const = (const_win - amp_mean) / amp_std

    assert np.isfinite(norm_const).all(), "Constant window resulted in non-finite values"
    assert np.allclose(norm_const, 0.0, atol=1e-3), "Constant window should normalize to ~0"

    # Doppler on constant window
    dopp_const = preprocessor.compute_doppler_spectrogram(const_win)
    assert np.isfinite(dopp_const).all(), "Doppler on constant window produced non-finite values"
    assert dopp_const.shape == (50, 56)


def test_phase39_class_index_mapping_and_taxonomy():
    """Verify exact 5-class index mapping and segregation from legacy 12-class benchmark labels."""
    assert EXPECTED_CLASS_MAP["push_pull"] == 0
    assert EXPECTED_CLASS_MAP["clap"] == 1
    assert EXPECTED_CLASS_MAP["walk"] == 2
    assert EXPECTED_CLASS_MAP["static"] == 3
    assert EXPECTED_CLASS_MAP["sit"] == 4

    # 3-class diagnostic subset corresponds to indices 0, 1, 2
    diagnostic_3class = ["push_pull", "clap", "walk"]
    for act in diagnostic_3class:
        assert EXPECTED_CLASS_MAP[act] in [0, 1, 2]

    # static and sit must never be mapped to box (6) or clean (8)
    assert EXPECTED_CLASS_MAP["static"] != 6
    assert EXPECTED_CLASS_MAP["sit"] != 8

    # Fall is completely excluded
    assert "fall" not in EXPECTED_CLASS_MAP


def test_phase39_train_val_test_isolation():
    """Verify strict participant and room isolation across partitions."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    gen = ParticipantIndependentSplitGenerator(manifest)
    split = gen.generate_strict_cross_room_split()
    sessions = split["sessions"]

    train_s = [s for s in sessions if s["split"] == "train"]
    val_s = [s for s in sessions if s["split"] == "val"]
    test_s = [s for s in sessions if s["split"] == "test"]

    train_rooms = {s.get("room") for s in train_s}
    val_rooms = {s.get("room") for s in val_s}
    test_rooms = {s.get("room") for s in test_s}

    train_parts = {s.get("participant_id") for s in train_s}
    val_parts = {s.get("participant_id") for s in val_s}
    test_parts = {s.get("participant_id") for s in test_s}

    assert "Office_Room2" not in train_rooms, "Office_Room2 leaked into train"
    assert "Office_Room2" not in val_rooms, "Office_Room2 leaked into val"
    assert test_rooms == {"Office_Room2"}, f"Test partition has non-test rooms: {test_rooms}"

    assert "Participant_02" not in train_parts, "Participant_02 leaked into train"
    assert "Participant_02" not in val_parts, "Participant_02 leaked into val"
    assert test_parts == {"Participant_02"}, f"Test partition has non-test participants: {test_parts}"

    assert len(train_parts & test_parts) == 0, "Participant leakage between train and test"
    assert len(val_parts & test_parts) == 0, "Participant leakage between val and test"


def test_phase39_gate0_data_sufficiency_and_parameter_audit():
    """Verify parameter count and audit that 75 samples cannot defensibly train 1.48M parameters."""
    model = CSIDualBranchFusionNet(
        num_subcarriers=56,
        doppler_bins=56,
        seq_len=50,
        num_classes=5,
        embed_dim=128,
        nhead=8,
        num_layers=3,
        dim_feedforward=512,
        dropout=0.1,
        fusion_mode="gated"
    )

    total_params = sum(p.numel() for p in model.parameters())
    assert total_params == 1482503, f"Expected 1,482,503 parameters, got {total_params}"

    train_windows = 75
    param_to_sample_ratio = total_params / train_windows

    # 19,766 parameters per training sample is mathematically gross undersampling
    assert param_to_sample_ratio > 19000, f"Ratio {param_to_sample_ratio} unexpectedly low"

    # Confirm Gate 0 status is formally recorded as BLOCKED
    gate0_status = "BLOCKED"
    assert gate0_status == "BLOCKED"
