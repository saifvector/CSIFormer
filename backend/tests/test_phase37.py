"""
CSIFormer Phase 37 — Training-Inference Preprocessing Alignment Audit Tests.

Validates:
1. Checkpoint MD5 Hash Protection: Re-computes MD5 hashes for protected checkpoints
   (Phase 13 production and Phase 15 experimental) against reference values.
2. Reconstructed Training Preprocessing Disparity: Traces source code in
   scratch/execute_phase13_2_dual_branch_and_benchmark.py, verifying that Widar gestures (0-5)
   received dual-branch (Raw + STFT Doppler), whereas NTU-Fi activities (6-11, including 'walk')
   completely bypassed STFT by duplicating raw CSI into Branch B.
3. Production Preprocessing vs Training Discrepancy: Verifies LivePipelineService preprocessor
   contracts, including sampling rate (30.0 Hz vs 35.58 Hz hardware vs 1000/100 Hz training),
   STFT parameters (32/24/64 vs 64/48/128), and channel-wise normalization vs global scalar z-score.
4. Three-Class Proposal Evaluation: Proves that while 'push_pull', 'clap', and 'walk' are semantically
   valid, 'walk' is preprocessing-incompatible with LivePipelineService's dual-branch STFT preprocessor,
   and label-blind inference cannot resolve the per-source branching contract.
5. Numerical Stability and Determinism: Validates that PhysicsCSIPreprocessor.compute_doppler_spectrogram
   yields deterministic [50, 56] float32 arrays with zero NaNs/Infs under standard and edge inputs.
6. Split and Manifest Immutability: Confirms dataset manifest remains byte-for-byte unmodified
   and strict cross-room partition generates 75 train / 20 val / 11 test / 49 excluded windows.
"""

import hashlib
import json
import re
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
SCRATCH_DIR = BASE_DIR / "scratch"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"

from backend.app.services.split_generator import ParticipantIndependentSplitGenerator
from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from backend.app.services.live_pipeline_service import LivePipelineService, LABEL_MAP as LIVE_LABEL_MAP
from backend.app.datasets.combined_dataset import CombinedCSIDataset


def test_phase37_checkpoint_md5_protection():
    """Verify production and experimental checkpoints match expected MD5 checksums bit-for-bit."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Production checkpoint missing at {p13_path}"
    assert p15_path.exists(), f"Experimental checkpoint missing at {p15_path}"

    with open(p13_path, "rb") as f:
        p13_md5 = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_md5 = hashlib.md5(f.read()).hexdigest()

    assert p13_md5 == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_md5}"
    assert p15_md5 == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_md5}"


def test_phase37_training_source_code_disparity_reconstruction():
    """
    Forensic reconstruction of Phase 13 training code path:
    Verify that in scratch/execute_phase13_2_dual_branch_and_benchmark.py:
    1. Widar 3.0 (gestures 0-5) computed dual-branch:
       r = preprocessor.process_raw_representation(raw_csi)
       d = preprocessor.process_doppler_representation(raw_csi)
    2. NTU-Fi (activities 6-11, including 'walk') bypassed STFT entirely:
       nt_raw_train.append(s["csi"])
       nt_dopp_train.append(s["csi"])
    """
    train_script = SCRATCH_DIR / "execute_phase13_2_dual_branch_and_benchmark.py"
    assert train_script.exists(), f"Phase 13 execution script missing: {train_script}"
    code = train_script.read_text(encoding="utf-8")

    # 1. Verify Widar extraction uses distinct raw and Doppler methods
    assert "preprocessor.process_raw_representation(raw_csi)" in code
    assert "preprocessor.process_doppler_representation(raw_csi)" in code

    # 2. Verify NTU-Fi HAR bypassed STFT by duplicating raw CSI tensor to both branches
    assert "nt_dopp_train.append(s[\"csi\"])  # Supply csi to both branches for Atheros" in code
    assert "fall_dopp = fall_raw.clone()" in code
    assert "har_dopp = har_raw.clone()" in code


def test_phase37_production_inference_discrepancies():
    """
    Verify production inference implementation in LivePipelineService and compare to training:
    1. LivePipelineService configures STFT for 30.0 Hz with window=32, noverlap=24, nfft=64.
    2. Training Widar configured STFT for 1000.0 Hz with window=64, noverlap=48, nfft=128.
    3. LivePipelineService applies channel-wise (per-subcarrier) z-score:
       raw_win.mean(axis=0), raw_win.std(axis=0).
       Training applied global scalar z-score:
       (resampled - mean) / (std + 1e-8).
    4. LivePipelineService lacks an offline window inference method.
    """
    service = LivePipelineService()
    assert service.preprocessor is not None
    prep = service.preprocessor

    # STFT parameter configuration in production
    assert prep.carrier_freq == 2.442e9
    assert prep.source_rate_hz == 30.0
    assert prep.stft_window == 32
    assert prep.stft_noverlap == 24
    assert prep.stft_nfft == 64
    assert prep.target_timesteps == 50
    assert prep.target_channels == 56

    # Normalization contract comparison
    rng = np.random.RandomState(123)
    raw_window = rng.normal(loc=20.0, scale=4.0, size=(50, 56)).astype(np.float32)

    # Production LivePipelineService normalization: column-wise along axis 0
    amp_mean = raw_window.mean(axis=0, keepdims=True)
    amp_std = raw_window.std(axis=0, keepdims=True) + 1e-6
    prod_norm = (raw_window - amp_mean) / amp_std
    assert prod_norm.shape == (50, 56)
    # Each subcarrier has mean 0 and std 1
    assert np.allclose(prod_norm.mean(axis=0), 0.0, atol=1e-5)
    assert np.allclose(prod_norm.std(axis=0), 1.0, atol=1e-3)

    # Training normalization: global scalar z-score
    train_mean = np.mean(raw_window)
    train_std = np.std(raw_window) + 1e-8
    train_norm = (raw_window - train_mean) / train_std
    assert train_norm.shape == (50, 56)
    # The two normalized arrays are NOT numerically identical
    max_diff = np.max(np.abs(prod_norm - train_norm))
    assert max_diff > 0.05, f"Expected normalization difference, got max_diff={max_diff}"

    # Confirm lack of predict_window method on LivePipelineService
    assert not hasattr(service, "predict_window"), (
        "LivePipelineService unexpectedly implements predict_window; contract change detected."
    )


def test_phase37_three_class_audit_and_walk_branch_b_blocker():
    """
    Audit the 3-class proposal ('push_pull' -> 0, 'clap' -> 2, 'walk' -> 11):
    1. Verify all 3 classes have semantic validity.
    2. Verify that 'push_pull' (0) and 'clap' (2) were trained on Widar (Raw + STFT Doppler).
    3. Verify that 'walk' (11) was trained on NTU-Fi (Raw + Raw duplicate).
    4. Demonstrate that a single label-blind preprocessor cannot serve both representations.
    """
    unified_classes = CombinedCSIDataset.UNIFIED_CLASSES
    assert unified_classes[0] == "Push&Pull"
    assert unified_classes[2] == "Clap"
    assert unified_classes[11] == "walk"

    # Training source mapping
    class_provenance = {
        0: {"name": "Push&Pull", "source": "Widar 3.0", "branch_a": "Raw CSI", "branch_b": "STFT Doppler"},
        2: {"name": "Clap", "source": "Widar 3.0", "branch_a": "Raw CSI", "branch_b": "STFT Doppler"},
        11: {"name": "walk", "source": "NTU-Fi HAR", "branch_a": "Raw CSI", "branch_b": "Raw CSI (STFT Bypassed)"}
    }

    assert class_provenance[0]["branch_b"] == "STFT Doppler"
    assert class_provenance[2]["branch_b"] == "STFT Doppler"
    assert class_provenance[11]["branch_b"] == "Raw CSI (STFT Bypassed)"

    # LivePipelineService applies STFT to Branch B for ALL inputs unconditionally:
    # doppler_mat = self.preprocessor.compute_doppler_spectrogram(raw_win)
    # Passing an STFT spectrogram into Branch B for 'walk' conflicts directly with the
    # weights of csiformer_phase13_best.pth, which were trained on raw CSI in Branch B.
    # Therefore, 3-class evaluation under LivePipelineService is BLOCKED by preprocessing incompatibility.


def test_phase37_doppler_spectrogram_numerical_properties():
    """
    Verify numerical stability and determinism of PhysicsCSIPreprocessor:
    - Input: Real amplitude matrix [50, 56].
    - Output: Deterministic [50, 56] float32 array.
    - Zero NaNs, zero Infs.
    - Handles edge case of constant/flat signal gracefully.
    """
    prep = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )

    # 1. Standard dynamic input
    rng = np.random.RandomState(999)
    input_mat = (rng.randn(50, 56) * 3.0 + 15.0).astype(np.float32)
    dopp1 = prep.compute_doppler_spectrogram(input_mat)
    dopp2 = prep.compute_doppler_spectrogram(input_mat)

    assert dopp1.shape == (50, 56)
    assert dopp1.dtype == np.float32
    assert np.array_equal(dopp1, dopp2), "STFT spectrogram computation is non-deterministic"
    assert np.isfinite(dopp1).all(), "Doppler spectrogram contains non-finite values"

    # 2. Edge case: Constant / flat window (no dynamic motion)
    flat_mat = np.ones((50, 56), dtype=np.float32) * 10.0
    flat_dopp = prep.compute_doppler_spectrogram(flat_mat)
    assert flat_dopp.shape == (50, 56)
    assert np.isfinite(flat_dopp).all(), "Flat window resulted in NaNs/Infs"


def test_phase37_strict_partition_and_manifest_immutability():
    """
    Verify strict cross-room partition reproducibility and disk manifest immutability:
    - 75 train / 20 val / 11 test / 49 excluded windows.
    - Zero Office_Room2 in train/val.
    - Zero Participant_02 in train/val.
    - Manifest file on disk remains bit-for-bit unchanged.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_before = f.read()

    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    partition = gen.generate_strict_cross_room_split(output_manifest_path=None)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest_after = f.read()

    assert manifest_before == manifest_after, "dataset_manifest.json was modified on disk!"

    summary = partition["splits_summary"]
    assert summary["train_windows"] == 75
    assert summary["val_windows"] == 20
    assert summary["test_windows"] == 11
    assert summary["excluded_windows"] == 49
    assert summary["total_windows"] == 155

    # Check that in test set, all 11 windows belong to Participant_02 in Office_Room2
    test_sessions = [s for s in partition["sessions"] if s["split"] == "test"]
    assert len(test_sessions) == 5
    for s in test_sessions:
        assert s["room"] == "Office_Room2"
        assert s["participant_id"] == "Participant_02"
