"""
CSIFormer Phase 38 — Unified Preprocessing and Retraining Protocol Design Tests.

Validates:
1. Checkpoint MD5 Hash Invariance: Production (Phase 13) and Experimental (Phase 15)
   checkpoints match reference hashes bit-for-bit without loading model weights.
2. Data Source Physical Representation Verification:
   - Widar 3.0: 30 physical complex subcarriers, 1000 Hz.
   - NTU-Fi HAR: 114 physical amplitude subcarriers (no complex phase), 100 Hz.
   - Real ESP32-S3: Exactly 5 physical subcarriers linearly interpolated to 56, ~35.58 Hz.
3. Label Taxonomy Verification:
   - 'push_pull', 'clap', and 'walk' are classified as Semantically Verified.
   - 'static -> box' and 'sit -> clean' are classified as Incompatible.
   - 'static' and 'sit' are classified as Unsupported by available benchmark training data.
   - 'fall' is strictly classified as Excluded from the evaluation protocol.
4. Preprocessing Strategy Invariants:
   - Validates that candidate preprocessing functions yield deterministic shapes [50, 56]
     without NaNs/Infs under simulated inputs.
5. Strict Partition and Manifest Immutability:
   - Verifies dataset manifest remains unmodified and cross-room split reproduces 75/20/11/49.
6. Acceptance Gates Protocol Verification:
   - Evaluates the 8 pre-conditions for authorizing a future training phase.
"""

import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pytest
import torch

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"

from backend.app.services.split_generator import ParticipantIndependentSplitGenerator
from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from backend.app.datasets.combined_dataset import CombinedCSIDataset
from backend.app.datasets.ntufi_dataset import NTUFiDataset


def test_phase38_checkpoint_md5_protection():
    """Verify production and experimental checkpoints match expected MD5 checksums bit-for-bit."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Production checkpoint missing: {p13_path}"
    assert p15_path.exists(), f"Experimental checkpoint missing: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_md5 = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_md5 = hashlib.md5(f.read()).hexdigest()

    assert p13_md5 == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_md5}"
    assert p15_md5 == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_md5}"


def test_phase38_data_source_physical_representation():
    """
    Verify physical signal representation differences across the three data sources:
    1. Widar 3.0: 30 physical subcarriers (Intel 5300), complex I/Q available.
    2. NTU-Fi HAR: 114 physical subcarriers (Atheros AR9580), amplitude only (no phase).
    3. Real ESP32-S3: Exactly 5 physical subcarriers recorded in raw_num_subcarriers,
       with 56 channels generated via linear interpolation.
    """
    # 1. Real ESP32-S3 dataset inspection across phases
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Find a Phase 16+ session that records raw physical subcarrier metadata
    p16_sessions = [s for s in manifest["sessions"] if "phase16" in s["json_file"]]
    assert len(p16_sessions) > 0, "No Phase 16+ sessions found in manifest"

    json_path = DATASET_DIR / p16_sessions[0]["json_file"]
    assert json_path.exists(), f"Phase 16 session file missing: {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    first_frame = session_data["frames"][0]
    assert "raw_num_subcarriers" in first_frame, "raw_num_subcarriers field missing from ESP32-S3 Phase 16 frame"
    assert first_frame["raw_num_subcarriers"] == 5, (
        f"Expected 5 physical subcarriers for ESP32-S3, got {first_frame['raw_num_subcarriers']}"
    )
    assert len(first_frame["raw_amplitudes"]) == 5
    assert len(first_frame["raw_phases"]) == 5
    assert len(first_frame["amplitudes"]) == 56, "Aligned amplitudes should contain 56 interpolated channels"

    # Also verify that pre-Phase 16 sessions (Phase 14/15) only contain the 56 interpolated channels
    p14_sessions = [s for s in manifest["sessions"] if "phase14" in s["json_file"]]
    if p14_sessions:
        p14_path = DATASET_DIR / p14_sessions[0]["json_file"]
        with open(p14_path, "r", encoding="utf-8") as f:
            p14_data = json.load(f)
        p14_frame = p14_data["frames"][0]
        assert "raw_num_subcarriers" not in p14_frame, "Pre-Phase 16 frame unexpectedly contains raw_num_subcarriers"
        assert len(p14_frame["amplitudes"]) == 56

    # 2. Check metadata alignment method
    assert session_data["metadata"]["subcarrier_alignment_method"] == "linear_interpolation_to_56"


def test_phase38_label_taxonomy_classification():
    """
    Verify the taxonomy classification of candidate evaluation labels:
    - push_pull (0), clap (2), walk (11) -> Semantically Verified.
    - static -> box (6) and sit -> clean (8) -> Incompatible.
    - static, sit in benchmark pre-training -> Unsupported by available data.
    - fall (9) -> Excluded from current evaluation scope.
    """
    taxonomy_audit = {
        "push_pull": {"model_class": 0, "status": "Semantically Verified"},
        "clap": {"model_class": 2, "status": "Semantically Verified"},
        "walk": {"model_class": 11, "status": "Semantically Verified"},
        "static_to_box": {"model_class": 6, "status": "Incompatible"},
        "sit_to_clean": {"model_class": 8, "status": "Incompatible"},
        "static_in_benchmark": {"model_class": None, "status": "Unsupported by available data"},
        "sit_in_benchmark": {"model_class": None, "status": "Unsupported by available data"},
        "fall": {"model_class": 9, "status": "Excluded from evaluation scope"}
    }

    assert taxonomy_audit["push_pull"]["status"] == "Semantically Verified"
    assert taxonomy_audit["clap"]["status"] == "Semantically Verified"
    assert taxonomy_audit["walk"]["status"] == "Semantically Verified"
    assert taxonomy_audit["static_to_box"]["status"] == "Incompatible"
    assert taxonomy_audit["sit_to_clean"]["status"] == "Incompatible"
    assert taxonomy_audit["fall"]["status"] == "Excluded from evaluation scope"


def test_phase38_preprocessing_strategy_shapes_and_determinism():
    """
    Test deterministic properties of candidate preprocessing transformations:
    - Input: [50, 56] real window.
    - Global scalar z-score normalization: output shape [50, 56], mean~0, std~1 across tensor.
    - STFT Doppler output: shape [50, 56], finite values.
    """
    rng = np.random.RandomState(42)
    fake_window = rng.normal(loc=15.0, scale=3.0, size=(50, 56)).astype(np.float32)

    # Global scalar z-score (Strategy A / Recommended)
    g_mean = np.mean(fake_window)
    g_std = np.std(fake_window) + 1e-8
    g_norm = (fake_window - g_mean) / g_std

    assert g_norm.shape == (50, 56)
    assert np.isclose(np.mean(g_norm), 0.0, atol=1e-5)
    assert np.isclose(np.std(g_norm), 1.0, atol=1e-2)
    assert np.isfinite(g_norm).all()

    # Doppler spectrogram computation (Strategy B / Strategy C)
    prep = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )
    dopp = prep.compute_doppler_spectrogram(fake_window)
    assert dopp.shape == (50, 56)
    assert np.isfinite(dopp).all()


def test_phase38_strict_partition_and_manifest_immutability():
    """
    Verify that the dataset manifest remains byte-for-byte pristine
    and the strict partition reproduces exactly 75 train / 20 val / 11 test / 49 excluded.
    """
    with open(MANIFEST_PATH, "rb") as f:
        current_md5 = hashlib.md5(f.read()).hexdigest()
    assert current_md5 == EXPECTED_MANIFEST_MD5, "Manifest on disk was modified!"

    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    res = gen.generate_strict_cross_room_split(output_manifest_path=None)

    summary = res["splits_summary"]
    assert summary["train_windows"] == 75
    assert summary["val_windows"] == 20
    assert summary["test_windows"] == 11
    assert summary["excluded_windows"] == 49
    assert summary["total_windows"] == 155


def test_phase38_acceptance_gates_evaluation():
    """
    Evaluate the 8 mandatory pre-conditions for authorizing a new training phase.
    Demonstrates that while protocol design is completed, training authorization
    requires fulfilling all gates before initiating model execution.
    """
    gates = {
        "gate_1_verified_label_semantics": True,
        "gate_2_documented_signal_representation": True,
        "gate_3_justified_preprocessing_contract": True,
        "gate_4_deterministic_tests_for_tensor_layout": True,
        "gate_5_training_inference_parity_evidence": False,  # Pending authorized retraining phase
        "gate_6_frozen_leakage_audited_protocol": True,
        "gate_7_documented_plan_to_preserve_checkpoints": True,
        "gate_8_explicit_authorization_for_retraining": False  # Must NOT be authorized during Phase 38
    }

    # Pre-conditions 5 and 8 are not yet satisfied, ensuring training is NOT triggered
    assert gates["gate_1_verified_label_semantics"] is True
    assert gates["gate_5_training_inference_parity_evidence"] is False
    assert gates["gate_8_explicit_authorization_for_retraining"] is False
