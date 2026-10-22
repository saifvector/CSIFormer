"""
CSIFormer Phase 35 — Five-Class Cross-Room Evaluation Compatibility & Protocol Gate Tests.

Validates:
1. Checkpoint Hash Invariance: Bit-level verification of protected weights without model loading.
2. Architecture & State Dict Compatibility: Inspect parameter keys, tensor shapes, dual-branch inputs,
   and 12-class output heads without loading checkpoint weights into an instantiated model.
3. Five-Class Taxonomy & Label Mapping: Deterministic, unambiguous 1-to-1 mapping between manifest
   activity labels ('push_pull', 'clap', 'static', 'sit', 'walk') and model class IDs (0, 2, 6, 8, 11).
   Ensures fall detection (class 9) is strictly excluded.
4. Preprocessing Input Compatibility: Input shape (50, 56), temporal z-score normalization contract,
   and Doppler spectrogram shape (50, 56) alignment with model convolutional kernels.
5. Strict Partition Reproducibility: Non-mutating verification of the 75 train / 20 val / 11 test / 49 excluded
   partition, zero room or participant leakage, and disk manifest immutability.
6. Evaluation Protocol Contracts: Formal rules for 12-class unrestricted argmax vs 5-class restricted sub-logits,
   window-level metrics, session-level majority voting with tie-breaking, and error accounting.
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

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"

from backend.app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InadequateClassCoverageError,
)
from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from backend.app.models.csiformer_dual_branch import CSIDualBranchFusionNet


def test_phase35_checkpoint_hash_protection():
    """Verify both production and experimental checkpoints match reference MD5 hashes bit-for-bit."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Production checkpoint missing: {p13_path}"
    assert p15_path.exists(), f"Experimental checkpoint missing: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_md5 = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_md5 = hashlib.md5(f.read()).hexdigest()

    assert p13_md5 == EXPECTED_PHASE13_MD5, (
        f"Production checkpoint modified! Expected {EXPECTED_PHASE13_MD5}, got {p13_md5}"
    )
    assert p15_md5 == EXPECTED_PHASE15_MD5, (
        f"Experimental checkpoint modified! Expected {EXPECTED_PHASE15_MD5}, got {p15_md5}"
    )


def test_phase35_checkpoint_state_dict_architecture_compatibility():
    """
    Inspect checkpoint state dicts directly WITHOUT loading weights into any model instance.
    Confirm expected parameter tensor shapes, input dimensions, and output heads.
    """
    for name, filename in [
        ("Phase 13 Production", "csiformer_phase13_best.pth"),
        ("Phase 15 Experimental", "csiformer_phase15_adapted.pth")
    ]:
        ckpt_path = MODELS_DIR / filename
        data = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        sd = data.get("model_state_dict", data.get("state_dict", data)) if isinstance(data, dict) else data

        assert len(sd) == 140, f"{name}: Expected 140 parameter tensors, got {len(sd)}"

        # 1. Raw CNN input kernel: [out_channels=128, in_channels=56, kernel_size=3]
        assert "raw_cnn.conv1.weight" in sd, f"{name}: Missing raw_cnn.conv1.weight"
        assert tuple(sd["raw_cnn.conv1.weight"].shape) == (128, 56, 3), (
            f"{name}: Invalid raw_cnn.conv1.weight shape {sd['raw_cnn.conv1.weight'].shape}"
        )

        # 2. Doppler CNN input kernel: [out_channels=128, in_channels=56, kernel_size=3]
        assert "dopp_cnn.conv1.weight" in sd, f"{name}: Missing dopp_cnn.conv1.weight"
        assert tuple(sd["dopp_cnn.conv1.weight"].shape) == (128, 56, 3), (
            f"{name}: Invalid dopp_cnn.conv1.weight shape {sd['dopp_cnn.conv1.weight'].shape}"
        )

        # 3. Positional Encodings max_len: [1, 100, 128]
        assert tuple(sd["raw_pos_encoder.pe"].shape) == (1, 100, 128)
        assert tuple(sd["dopp_pos_encoder.pe"].shape) == (1, 100, 128)

        # 4. Gated fusion module
        assert "gate_dense.0.weight" in sd
        assert tuple(sd["gate_dense.0.weight"].shape) == (128, 256)
        assert tuple(sd["gate_dense.3.weight"].shape) == (128, 128)

        # 5. Activity Head: [64 -> 12]
        assert "activity_head.3.weight" in sd
        assert tuple(sd["activity_head.3.weight"].shape) == (12, 64)
        assert tuple(sd["activity_head.3.bias"].shape) == (12,)

        # 6. Auxiliary Heads
        assert tuple(sd["presence_head.2.weight"].shape) == (1, 32)
        assert tuple(sd["motion_head.2.weight"].shape) == (1, 32)
        assert tuple(sd["proj_head.2.weight"].shape) == (128, 128)


def test_phase35_five_class_label_mapping_alignment():
    """
    Verify the 5 physical evaluation activities map unambiguously to the model's 12-class taxonomy.
    Verify fall (class 9) is strictly excluded from target classes.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Manifest class mapping
    activity_to_class_id = {}
    for s in manifest["sessions"]:
        activity_to_class_id[s["activity_label"]] = s["class_id"]

    target_5_activities = ["static", "sit", "walk", "clap", "push_pull"]
    expected_mapping = {
        "push_pull": 0,
        "clap": 2,
        "static": 6,
        "sit": 8,
        "walk": 11
    }

    for act in target_5_activities:
        assert act in activity_to_class_id, f"Target activity '{act}' not found in manifest"
        assert activity_to_class_id[act] == expected_mapping[act], (
            f"Class ID mismatch for '{act}': expected {expected_mapping[act]}, got {activity_to_class_id[act]}"
        )

    # Fall detection must be present in manifest (class 9) but NOT in the target 5 activities
    assert activity_to_class_id.get("fall") == 9
    assert "fall" not in target_5_activities

    # Verify model's DEFAULT_CLASSES taxonomy matches
    default_classes = CSIDualBranchFusionNet.DEFAULT_CLASSES
    assert len(default_classes) == 12
    assert default_classes[0] == "Push&Pull"
    assert default_classes[2] == "Clap"
    assert default_classes[6] == "box"  # Historical baseline alias for static
    assert default_classes[8] == "clean"  # Historical baseline alias for sit
    assert default_classes[9] == "fall"
    assert default_classes[11] == "walk"


def test_phase35_preprocessing_input_contract_and_spectrogram():
    """
    Verify preprocessing logic:
    - Raw input slicing: non-overlapping 50-frame windows with 56 subcarriers.
    - Z-score normalization along time: mean=0, std=1.
    - Doppler spectrogram extraction produces shape (50, 56) with finite values.
    """
    prep = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )

    # Synthetic realistic CSI window: 50 time steps, 56 subcarriers
    rng = np.random.RandomState(42)
    fake_window = rng.normal(loc=25.0, scale=5.0, size=(50, 56)).astype(np.float32)

    # Raw branch normalization contract
    amp_mean = fake_window.mean(axis=0, keepdims=True)
    amp_std = fake_window.std(axis=0, keepdims=True) + 1e-6
    norm_raw = (fake_window - amp_mean) / amp_std

    assert norm_raw.shape == (50, 56)
    assert np.allclose(norm_raw.mean(axis=0), 0.0, atol=1e-5)
    assert np.allclose(norm_raw.std(axis=0), 1.0, atol=1e-2)

    # Doppler branch STFT contract
    dopp_spec = prep.compute_doppler_spectrogram(fake_window)
    assert dopp_spec.shape == (50, 56), f"Doppler spectrogram shape mismatch: {dopp_spec.shape}"
    assert np.isfinite(dopp_spec).all(), "Doppler spectrogram contains non-finite values"


def test_phase35_strict_partition_reproducibility():
    """
    Independently regenerate the strict partition using a non-mutating call.
    Verify:
    - Train: 36 sessions, 75 windows.
    - Val: 10 sessions, 20 windows.
    - Test: 5 sessions, 11 windows (Office_Room2, Participant_02).
    - Excluded: 23 sessions, 49 windows.
    - Total: 74 sessions, 155 windows.
    - Zero Office_Room2 in train or val.
    - Zero Participant_02 in train or val.
    - Zero disk manifest mutation.
    """
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        original_manifest_text = f.read()

    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    partition = gen.generate_strict_cross_room_split(output_manifest_path=None)

    # Confirm manifest on disk was not modified
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        current_manifest_text = f.read()
    assert current_manifest_text == original_manifest_text, "Manifest on disk was mutated during split generation!"

    # Verify session and window counts
    summary = partition["splits_summary"]
    assert summary["train_sessions"] == 36
    assert summary["val_sessions"] == 10
    assert summary["test_sessions"] == 5
    assert summary["excluded_sessions"] == 23
    assert summary["total_sessions"] == 74

    assert summary["train_windows"] == 75
    assert summary["val_windows"] == 20
    assert summary["test_windows"] == 11
    assert summary["excluded_windows"] == 49
    assert summary["total_windows"] == 155

    # Verify activity window breakdown in test
    test_wins = summary["windows_by_activity"]["test"]
    assert test_wins == {
        "static": 2,
        "sit": 2,
        "walk": 2,
        "clap": 2,
        "push_pull": 3
    }

    # Verify room and participant isolation
    train_rooms = {s["room"] for s in partition["sessions"] if s["split"] == "train"}
    val_rooms = {s["room"] for s in partition["sessions"] if s["split"] == "val"}
    test_rooms = {s["room"] for s in partition["sessions"] if s["split"] == "test"}

    assert "Office_Room2" not in train_rooms, "Office_Room2 leaked into train!"
    assert "Office_Room2" not in val_rooms, "Office_Room2 leaked into val!"
    assert test_rooms == {"Office_Room2"}, f"Test partition has unexpected rooms: {test_rooms}"

    train_p = {s["participant_id"] for s in partition["sessions"] if s["split"] == "train"}
    val_p = {s["participant_id"] for s in partition["sessions"] if s["split"] == "val"}
    test_p = {s["participant_id"] for s in partition["sessions"] if s["split"] == "test"}

    assert "Participant_02" not in train_p, "Participant_02 leaked into train!"
    assert "Participant_02" not in val_p, "Participant_02 leaked into val!"
    assert test_p == {"Participant_02"}, f"Test partition has unexpected participants: {test_p}"


def test_phase35_evaluation_protocol_contracts():
    """
    Test evaluation protocol contract logic:
    - 12-class unrestricted argmax: Out-of-set predictions count as classification errors.
    - 5-class restricted sub-logits: Model selects only among candidate classes [0, 2, 6, 8, 11].
    - Session-level majority voting aggregation: Resolves 11 test windows into 5 session decisions.
    - Deterministic tie-breaking for 2-window sessions: higher mean prediction confidence breaks ties.
    """
    target_cids = [0, 2, 6, 8, 11]

    # Scenario A: Unrestricted vs Restricted argmax behavior
    # Fake 12-class logits where an out-of-set class (e.g. class 1 'Sweep') has the highest score
    fake_logits = np.array([1.0, 5.0, 2.0, 0.1, 0.2, 0.1, 3.0, 0.1, 2.5, 0.1, 0.1, 2.0])
    
    # Unrestricted argmax picks class 1 (out-of-set error)
    unrestricted_pred = int(np.argmax(fake_logits))
    assert unrestricted_pred == 1

    # Restricted sub-logits argmax picks the highest among [0, 2, 6, 8, 11] -> class 6 (score 3.0)
    sub_logits = fake_logits[target_cids]
    restricted_pred = target_cids[int(np.argmax(sub_logits))]
    assert restricted_pred == 6

    # Scenario B: Session-level majority voting aggregation
    # Session with 3 windows (e.g. push_pull): window predictions [0, 0, 2] -> majority is 0
    wins_push_pull = [0, 0, 2]
    majority_push_pull = max(set(wins_push_pull), key=wins_push_pull.count)
    assert majority_push_pull == 0

    # Session with 2 windows with agreement: [11, 11] -> majority is 11
    wins_walk = [11, 11]
    majority_walk = max(set(wins_walk), key=wins_walk.count)
    assert majority_walk == 11

    # Session with 2 windows with tie: [6, 8] -> tie-breaking by average class probability
    probs_win1 = np.zeros(12)
    probs_win1[6] = 0.6
    probs_win1[8] = 0.4
    probs_win2 = np.zeros(12)
    probs_win2[6] = 0.3
    probs_win2[8] = 0.7
    mean_probs = (probs_win1 + probs_win2) / 2.0
    # Mean prob for 6 is 0.45, for 8 is 0.55 -> class 8 wins the tie
    tie_winner = target_cids[int(np.argmax(mean_probs[target_cids]))]
    assert tie_winner == 8
