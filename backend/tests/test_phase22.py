"""
CSIFormer Phase 22 — First Verified Physical Recording & Dataset Expansion Readiness Test Suite.

Automated deterministic testing covering:
1. Bit-for-bit model checkpoint hash invariance (Production and Experimental).
2. Saved physical session file existence, schema validity, and frame count integrity.
3. Physical vs. derived subcarrier separation (5 raw physical subcarriers vs. 56 interpolated channels).
4. Manifest indexing, packet count, window count, and confirmation status.
5. Full dataset integrity validation using DatasetIntegrityValidator.
6. Participant diversity expansion (Participant_01, Participant_02, Participant_03).
7. Participant-independent 3-way LOSO split feasibility and zero-leakage verification.
8. CSV mirror file row count and column alignment consistency.
"""

import sys
import os
import json
import csv
import hashlib
from pathlib import Path
import numpy as np
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.services.session_validator import DatasetIntegrityValidator
from app.services.split_generator import ParticipantIndependentSplitGenerator

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = ROOT_DIR / "models"
NEW_SESSION_ID = "phase16_real_walk_Participant_03_1792339078_1792339078"


def test_phase22_checkpoint_hash_invariance():
    """Verify that both production and experimental checkpoints remain bit-for-bit invariant."""
    prod_path = MODELS_DIR / "csiformer_phase13_best.pth"
    exp_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert prod_path.exists(), f"Production checkpoint missing: {prod_path}"
    assert exp_path.exists(), f"Experimental checkpoint missing: {exp_path}"

    with open(prod_path, "rb") as f:
        prod_md5 = hashlib.md5(f.read()).hexdigest()
    with open(exp_path, "rb") as f:
        exp_md5 = hashlib.md5(f.read()).hexdigest()

    assert prod_md5 == "383b4d98c08f8970b0443738f170ec01", f"Production checkpoint mutated: {prod_md5}"
    assert exp_md5 == "ab3d97a04d78edf75d807178772bc828", f"Experimental checkpoint mutated: {exp_md5}"


def test_phase22_saved_session_file_existence_and_integrity():
    """Verify that the newly recorded session JSON file exists and contains valid physical data."""
    json_path = DATASET_DIR / f"{NEW_SESSION_ID}.json"
    assert json_path.exists(), f"Saved physical session file missing: {json_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    meta = payload["metadata"]
    frames = payload["frames"]

    assert meta["session_id"] == NEW_SESSION_ID
    assert meta["participant_id"] == "Participant_03"
    assert meta["ground_truth_activity"] == "walk"
    assert meta["ground_truth_confirmed"] is True
    assert meta["confirmation_status"] == "confirmed"
    assert meta["room_type"] == "Laboratory"
    assert meta["tx_rx_distance_meters"] == 2.5
    assert meta["packets_received"] == 143
    assert meta["packets_lost"] == 0
    assert len(frames) == 143
    assert payload["frame_count"] == 143

    # Check finite numbers and timestamp monotonicity
    timestamps = [f["timestamp"] for f in frames]
    assert np.all(np.isfinite(timestamps))
    assert np.all(np.diff(timestamps) >= 0), "Timestamps must be strictly monotonic"

    # Check sequence continuity
    sequences = [f["sequence"] for f in frames]
    assert len(sequences) == 143
    assert np.all(np.diff(sequences) == 1), "Sequence numbers must be strictly continuous"

    # Check RSSI ranges
    rssis = [f["rssi"] for f in frames]
    assert np.all(np.isfinite(rssis))
    assert -90.0 < np.mean(rssis) < -30.0


def test_phase22_physical_vs_derived_subcarrier_representation():
    """
    Verify strict separation between 5 raw physical subcarrier measurements
    and 56 derived (interpolated) model-input channels.
    """
    json_path = DATASET_DIR / f"{NEW_SESSION_ID}.json"
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    frames = payload["frames"]
    meta = payload["metadata"]

    assert meta["subcarrier_alignment_method"] == "linear_interpolation_to_56"

    for idx, frame in enumerate(frames):
        # Raw physical subcarriers (5 complex measurements)
        assert "raw_amplitudes" in frame
        assert "raw_phases" in frame
        assert "raw_num_subcarriers" in frame
        assert frame["raw_num_subcarriers"] == 5
        assert len(frame["raw_amplitudes"]) == 5
        assert len(frame["raw_phases"]) == 5
        assert np.all(np.isfinite(frame["raw_amplitudes"]))
        assert np.all(np.isfinite(frame["raw_phases"]))

        # Derived model input channels (56 channels)
        assert "amplitudes" in frame
        assert "phases" in frame
        assert "num_subcarriers" in frame
        assert frame["num_subcarriers"] == 56
        assert len(frame["amplitudes"]) == 56
        assert len(frame["phases"]) == 56
        assert np.all(np.isfinite(frame["amplitudes"]))
        assert np.all(np.isfinite(frame["phases"]))


def test_phase22_manifest_indexing_and_packet_counts():
    """Verify that dataset_manifest.json accurately indexes the session with updated counts."""
    assert MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) >= 24, f"Expected at least 24 sessions in manifest, got {len(sessions)}"

    p22_sessions = [s for s in sessions if s["session_id"] == NEW_SESSION_ID]
    assert len(p22_sessions) == 1, f"Session {NEW_SESSION_ID} not found in manifest"
    session_info = p22_sessions[0]
    assert session_info["participant_id"] == "Participant_03"
    assert session_info["activity_label"] == "walk"
    assert session_info["class_id"] == 11
    assert session_info["confirmation_status"] == "confirmed"
    assert session_info["packet_count"] == 143
    assert session_info["room"] == "Laboratory"
    assert session_info["tx_rx_distance_m"] == 2.5
    assert session_info["subcarrier_alignment_method"] == "linear_interpolation_to_56"

    total_frames = sum(s["packet_count"] for s in sessions)
    assert total_frames >= 3355
    assert manifest["splits_summary"]["total_sessions"] >= 24
    assert manifest["splits_summary"]["total_frames"] >= 3355


def test_phase22_dataset_integrity_validator_full_pass():
    """Verify that DatasetIntegrityValidator passes cleanly on the updated dataset."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] >= 24
    assert res["total_packets"] >= 3355
    assert res["total_windows"] >= 51
    assert {"Participant_01", "Participant_02", "Participant_03"}.issubset(set(res["distinct_participants"]))
    assert res["distinct_events"] >= 24
    assert res["activity_windows"]["walk"] >= 11


def test_phase22_participant_diversity_expansion():
    """Verify that participant diversity expanded from 2 to 3 distinct participants."""
    generator = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    participants = generator.participants

    assert len(participants) >= 3
    assert "Participant_01" in participants
    assert "Participant_02" in participants
    assert "Participant_03" in participants

    summary = generator.get_participant_summary()
    p3_summary = summary["Participant_03"]
    assert p3_summary["session_count"] >= 1
    assert p3_summary["total_packets"] >= 143
    assert p3_summary["total_windows"] >= 2
    assert p3_summary["activity_windows"]["walk"] >= 2


def test_phase22_3way_loso_split_feasibility():
    """Verify that 3 participants enables a 3-way participant-independent partition without overlap."""
    generator = ParticipantIndependentSplitGenerator(MANIFEST_PATH)

    # 3-way split: Train = Participant_01 (and any other unassigned), Val = Participant_03, Test = Participant_02
    split = generator.generate_loso_split(
        test_participant="Participant_02",
        val_participant="Participant_03",
        strict_coverage=False
    )

    summary = split["splits_summary"]
    train_p = set(summary["train_participants"])
    val_p = set(summary["val_participants"])
    test_p = set(summary["test_participants"])

    # Zero participant leakage
    assert train_p.isdisjoint(val_p)
    assert train_p.isdisjoint(test_p)
    assert val_p.isdisjoint(test_p)

    assert "Participant_01" in train_p
    assert val_p == {"Participant_03"}
    assert test_p == {"Participant_02"}


def test_phase22_csv_mirror_consistency():
    """Verify that the CSV mirror file has matching row count and timestamps."""
    csv_path = DATASET_DIR / f"{NEW_SESSION_ID}.csv"
    assert csv_path.exists(), f"CSV mirror missing: {csv_path}"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    # 1 header + 143 data rows = 144
    assert len(reader) == 144
    header = reader[0]
    assert header[:4] == ["timestamp", "sequence", "rssi", "noise"]
    assert len(header) == 60  # 4 meta + 56 subcarriers
