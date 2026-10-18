"""
CSIFormer Phase 19 — Automated Session Validation, Overwrite Protection & Split Readiness Test Suite.

Automated deterministic testing covering:
1. Session validator manifest-to-file consistency and packet accounting.
2. Session validator corruption detection (frame count mismatch).
3. Session validator numerical integrity (NaN/Inf amplitude rejection).
4. Session validator timestamp monotonicity enforcement.
5. Session validator unconfirmed label enforcement (unconfirmed trials must be 'unknown').
6. Non-destructive overwrite protection in RealCSICollector (_v1 suffixing).
7. Quarantine workflow for invalid recordings (moving to quarantine/ and logging).
8. Frozen 5-participant pilot split allocation with zero pairwise leakage.
9. Mathematical barrier: InsufficientParticipantsError on 3-way split with N=2.
10. Bit-for-bit model checkpoint hash invariance.
"""

import sys
import os
import json
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pytest

# Ensure backend and root directory are in python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.services.real_csi_collector import RealCSICollector
from app.services.session_validator import DatasetIntegrityValidator, SessionValidationError
from app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InsufficientParticipantsError,
    InadequateClassCoverageError
)

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = ROOT_DIR / "models"


# =============================================================================
# 1. Dataset Integrity Validator on Primary Manifest
# =============================================================================
def test_session_validator_clean_manifest():
    """Verify that DatasetIntegrityValidator passes on the active physical manifest."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] == 23
    assert res["total_packets"] == 3212
    assert res["total_windows"] == 49
    assert res["distinct_participants"] == ["Participant_01", "Participant_02"]
    assert res["distinct_events"] == 23


# =============================================================================
# 2. Session Validator Frame Count Mismatch Detection
# =============================================================================
def test_session_validator_corrupt_frame_count():
    """Verify that a session declaring more frames than actually exist raises SessionValidationError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        session_file = tmp_path / "corrupt_frame_count.json"
        payload = {
            "metadata": {
                "session_id": "test_corrupt_01",
                "participant_id": "Participant_99",
                "activity_label": "walk",
                "ground_truth_confirmed": True
            },
            "frame_count": 100,  # Declares 100
            "frames": [          # Only provides 1 frame
                {
                    "timestamp": 1000.0,
                    "sequence": 1,
                    "rssi": -55.0,
                    "noise": -95.0,
                    "amplitudes": [1.0] * 56
                }
            ]
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        validator = DatasetIntegrityValidator(tmp_path)
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(session_file)
        assert "Frame count mismatch" in str(exc_info.value)


# =============================================================================
# 3. Session Validator Numerical Integrity (NaN/Inf Rejection)
# =============================================================================
def test_session_validator_non_finite_values():
    """Verify that NaN or Inf values in amplitudes or timestamps are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        session_file = tmp_path / "corrupt_nan.json"
        amps_with_nan = [1.0] * 55 + [float("nan")]
        payload = {
            "metadata": {
                "session_id": "test_nan_01",
                "participant_id": "Participant_99",
                "activity_label": "walk",
                "ground_truth_confirmed": True
            },
            "frame_count": 1,
            "frames": [
                {
                    "timestamp": 1000.0,
                    "sequence": 1,
                    "rssi": -55.0,
                    "noise": -95.0,
                    "amplitudes": amps_with_nan
                }
            ]
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        validator = DatasetIntegrityValidator(tmp_path)
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(session_file)
        assert "Non-finite amplitudes" in str(exc_info.value)


# =============================================================================
# 4. Session Validator Timestamp Monotonicity Enforcement
# =============================================================================
def test_session_validator_timestamp_non_monotonicity():
    """Verify that severe backward timestamp steps trigger SessionValidationError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        session_file = tmp_path / "corrupt_timing.json"
        payload = {
            "metadata": {
                "session_id": "test_timing_01",
                "participant_id": "Participant_99",
                "activity_label": "walk",
                "ground_truth_confirmed": True
            },
            "frame_count": 4,
            "frames": [
                {"timestamp": 100.0, "sequence": 1, "rssi": -55.0, "noise": -95.0, "amplitudes": [1.0]*56},
                {"timestamp": 90.0,  "sequence": 2, "rssi": -55.0, "noise": -95.0, "amplitudes": [1.0]*56}, # jump back 1
                {"timestamp": 105.0, "sequence": 3, "rssi": -55.0, "noise": -95.0, "amplitudes": [1.0]*56},
                {"timestamp": 80.0,  "sequence": 4, "rssi": -55.0, "noise": -95.0, "amplitudes": [1.0]*56}, # jump back 2
            ]
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        validator = DatasetIntegrityValidator(tmp_path)
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(session_file)
        assert "Severe timestamp non-monotonicity" in str(exc_info.value)


# =============================================================================
# 5. Session Validator Label Confirmation Enforcement
# =============================================================================
def test_session_validator_unconfirmed_label_enforcement():
    """Verify that unconfirmed sessions cannot retain active activity labels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        session_file = tmp_path / "unconfirmed_walk.json"
        payload = {
            "metadata": {
                "session_id": "test_unconfirmed_01",
                "participant_id": "Participant_99",
                "activity_label": "walk",
                "ground_truth_confirmed": False  # Unconfirmed but labeled walk!
            },
            "frame_count": 1,
            "frames": [
                {"timestamp": 100.0, "sequence": 1, "rssi": -55.0, "noise": -95.0, "amplitudes": [1.0]*56}
            ]
        }
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        validator = DatasetIntegrityValidator(tmp_path)
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(session_file)
        assert "Unconfirmed session" in str(exc_info.value)
        assert "Must be labeled as 'unknown'" in str(exc_info.value)


# =============================================================================
# 6. RealCSICollector Non-Destructive Overwrite Protection
# =============================================================================
def test_collector_overwrite_protection():
    """Verify that stop_session_recording appends version suffixes if a file already exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = RealCSICollector(auto_connect=False, data_dir=tmpdir)

        # Start recording
        start_res = collector.start_session_recording(
            session_name="test_collision_session",
            participant_id="Participant_01",
            activity_label="walk"
        )
        sid = start_res["session_id"]

        # Pre-create a file with that exact session_id to force collision
        existing_json = Path(tmpdir) / f"{sid}.json"
        with open(existing_json, "w", encoding="utf-8") as f:
            f.write('{"historical_data": "preserved"}')

        # Stop recording, which detects collision and saves as _v1
        stop_res = collector.stop_session_recording()

        assert stop_res["session_id"] == f"{sid}_v1"
        assert Path(stop_res["json_path"]).name == f"{sid}_v1.json"
        assert Path(stop_res["json_path"]).exists()

        # Ensure historical file was not overwritten
        with open(existing_json, "r", encoding="utf-8") as f:
            hist_content = f.read()
        assert "historical_data" in hist_content


# =============================================================================
# 7. Quarantine Workflow for Corrupted Recordings
# =============================================================================
def test_quarantine_workflow():
    """Verify that quarantine_session moves corrupt files to quarantine/ and logs the action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        corrupt_json = tmp_path / "corrupt_payload.json"
        corrupt_csv = tmp_path / "corrupt_payload.csv"
        with open(corrupt_json, "w", encoding="utf-8") as f:
            f.write("NOT_VALID_JSON{;;;")
        with open(corrupt_csv, "w", encoding="utf-8") as f:
            f.write("corrupt,csv,data")

        validator = DatasetIntegrityValidator(tmp_path)
        quarantined = validator.quarantine_session(corrupt_json, reason="Syntax corruption in JSON")

        assert not corrupt_json.exists(), "Original file should have been moved"
        assert not corrupt_csv.exists(), "Original CSV should have been moved"
        assert quarantined.exists(), f"Quarantined file missing: {quarantined}"
        assert quarantined.parent == tmp_path / "quarantine"

        # Check quarantine manifest
        q_manifest = tmp_path / "quarantine" / "quarantine_manifest.json"
        assert q_manifest.exists()
        with open(q_manifest, "r", encoding="utf-8") as f:
            q_log = json.load(f)
        assert len(q_log) == 1
        assert q_log[0]["filename"] == "corrupt_payload.json"
        assert q_log[0]["reason"] == "Syntax corruption in JSON"


# =============================================================================
# 8. Frozen 5-Participant Pilot Split Allocation with Zero Pairwise Leakage
# =============================================================================
def test_5_participant_split_leakage_and_invariance():
    """Verify clean 3-way partition (3 Train, 1 Val, 1 Test) with zero pairwise leakage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_manifest = {
            "dataset_name": "Mock_5_Subjects_Pilot",
            "sessions": [
                {
                    "session_id": f"s_{p}_{act}_{trial}",
                    "event_id": f"evt_{p}_{act}_{trial}",
                    "participant_id": p,
                    "activity_label": act,
                    "packet_count": 100
                }
                for p in ["P01", "P02", "P03", "P04", "P05"]
                for act in ["walk", "fall", "sit"]
                for trial in [1, 2]
            ]
        }
        m_path = Path(tmpdir) / "manifest_5p.json"
        with open(m_path, "w", encoding="utf-8") as f:
            json.dump(mock_manifest, f)

        gen = ParticipantIndependentSplitGenerator(m_path)
        res = gen.generate_loso_split(
            test_participant="P05",
            val_participant="P04",
            strict_coverage=True
        )

        train_p = set(res["splits_summary"]["train_participants"])
        val_p = set(res["splits_summary"]["val_participants"])
        test_p = set(res["splits_summary"]["test_participants"])

        # Pairwise participant zero leakage
        assert train_p == {"P01", "P02", "P03"}
        assert val_p == {"P04"}
        assert test_p == {"P05"}
        assert len(train_p.intersection(val_p)) == 0
        assert len(train_p.intersection(test_p)) == 0
        assert len(val_p.intersection(test_p)) == 0

        # Event-level leakage check
        train_events = set(s["event_id"] for s in res["sessions"] if s["split"] == "train")
        val_events = set(s["event_id"] for s in res["sessions"] if s["split"] == "val")
        test_events = set(s["event_id"] for s in res["sessions"] if s["split"] == "test")

        assert len(train_events.intersection(val_events)) == 0
        assert len(train_events.intersection(test_events)) == 0
        assert len(val_events.intersection(test_events)) == 0


# =============================================================================
# 9. InsufficientParticipantsError on 3-Way Split with N=2
# =============================================================================
def test_insufficient_participants_3way_error_phase19():
    """Verify that requesting a 3-way split on the 2-participant dataset strictly raises InsufficientParticipantsError."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    assert len(gen.participants) == 2
    with pytest.raises(InsufficientParticipantsError) as exc_info:
        gen.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")
    assert "Cannot create a 3-way participant-independent split" in str(exc_info.value)


# =============================================================================
# 10. Bit-for-Bit Checkpoint Hash Invariance
# =============================================================================
def test_phase19_checkpoint_hashes():
    """Verify cryptographic MD5 invariance of production and experimental checkpoints."""
    prod_path = MODELS_DIR / "csiformer_phase13_best.pth"
    exp_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert prod_path.exists(), f"Missing production checkpoint: {prod_path}"
    assert exp_path.exists(), f"Missing experimental checkpoint: {exp_path}"

    prod_hash = hashlib.md5(prod_path.read_bytes()).hexdigest()
    exp_hash = hashlib.md5(exp_path.read_bytes()).hexdigest()

    assert prod_hash == "383b4d98c08f8970b0443738f170ec01", f"Production checkpoint hash changed: {prod_hash}"
    assert exp_hash == "ab3d97a04d78edf75d807178772bc828", f"Experimental checkpoint hash changed: {exp_hash}"
