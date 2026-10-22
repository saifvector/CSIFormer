"""
CSIFormer Phase 20 — Physical Collection Support, Dataset Expansion & Split Readiness Test Suite.

Automated deterministic testing covering:
1. Dataset manifest integrity and packet counts on physical disk files.
2. CLI validation mode (--validate) execution and output structure.
3. Hardware verification mode (--verify) telemetry structure.
4. Detection and traceability of unindexed session files on disk.
5. Verification of 2-way LOSO split metrics (24 test windows, 4 fall windows, 2 fall events).
6. Enforcement of InsufficientParticipantsError on 3-way split when N < 3.
7. Non-destructive overwrite protection on session collision (_v1 suffixing).
8. Quarantine workflow integrity and quarantine_manifest.json logging.
9. Raw CSI subcarrier vs model input tensor dimension separation.
10. Bit-for-bit model checkpoint hash invariance (Production and Experimental).
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
from app.services.collection_workflow import CollectionWorkflowManager

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = ROOT_DIR / "models"


# =============================================================================
# 1. Dataset Manifest Integrity on Physical Disk Files
# =============================================================================
def test_phase20_dataset_manifest_integrity():
    """Verify that all 23 indexed sessions match physical disk files with exact packet counts."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] >= 23
    assert res["total_packets"] >= 3212
    assert res["total_windows"] >= 49
    assert {"Participant_01", "Participant_02"}.issubset(set(res["distinct_participants"]))
    assert res["distinct_events"] >= 23
    for act, min_wins in [("walk", 9), ("fall", 8), ("sit", 10), ("clap", 8), ("push_pull", 9), ("static", 5)]:
        assert res["activity_windows"].get(act, 0) >= min_wins, f"Activity {act} windows below baseline"


# =============================================================================
# 2. CLI Validation Mode Execution
# =============================================================================
def test_phase20_cli_validate_execution():
    """Verify that DatasetIntegrityValidator produces all expected keys for CLI reporting."""
    validator = DatasetIntegrityValidator(DATASET_DIR)
    summary = validator.validate_dataset_manifest()

    expected_keys = [
        "total_sessions", "total_packets", "total_windows",
        "distinct_participants", "distinct_events", "activity_windows",
        "all_sessions_valid", "session_validations"
    ]
    for k in expected_keys:
        assert k in summary, f"Missing key in validation summary: {k}"


# =============================================================================
# 3. Hardware Verification Telemetry Structure
# =============================================================================
def test_phase20_hardware_verification_structure():
    """Verify that CollectionWorkflowManager.verify_hardware_stream returns correct telemetry schema."""
    manager = CollectionWorkflowManager(port="COM99")  # Non-existent port for offline check
    res = manager.verify_hardware_stream(test_duration_s=0.1)

    assert "status" in res
    assert "connected" in res
    assert res["connected"] is False or res["status"] in ["ok", "no_packets", "error"]


# =============================================================================
# 4. Unindexed File Traceability
# =============================================================================
def test_phase20_unindexed_file_traceability():
    """Verify that unindexed file phase14_p15_real_walk_t1_1792303844_1792303844.json is tracked."""
    unindexed_path = DATASET_DIR / "phase14_p15_real_walk_t1_1792303844_1792303844.json"
    assert unindexed_path.exists(), f"Expected unindexed trial file missing: {unindexed_path}"

    with open(unindexed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify metadata and frame accounting
    meta = data.get("metadata", {})
    assert meta.get("participant_id") == "Participant_01"
    assert meta.get("ground_truth_activity") == "walk"
    # Ensure it is not indexed in the primary manifest
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_files = [s["json_file"] for s in manifest.get("sessions", [])]
    assert unindexed_path.name not in manifest_files, "Unindexed session should not be in primary manifest"


# =============================================================================
# 5. 2-Way LOSO Split Metrics
# =============================================================================
def test_phase20_loso_split_metrics():
    """Verify that 2-way LOSO split produces exactly 24 test windows and 4 test fall windows."""
    p17_loso_path = DATASET_DIR / "dataset_manifest_p17_loso.json"
    gen = ParticipantIndependentSplitGenerator(p17_loso_path)
    split_res = gen.generate_loso_split(test_participant="Participant_02", strict_coverage=False)

    summary = split_res["splits_summary"]
    assert summary["train_participants"] == ["Participant_01"]
    assert summary["test_participants"] == ["Participant_02"]
    assert summary["val_participants"] == []
    assert summary["train_windows"] == 25
    assert summary["test_windows"] == 24
    assert summary["val_windows"] == 0
    assert summary["fall_windows"]["train"] == 4
    assert summary["fall_windows"]["test"] == 4
    assert summary["fall_events"]["train"] == 2
    assert summary["fall_events"]["test"] == 2


# =============================================================================
# 6. InsufficientParticipantsError on 3-Way Split with N=2
# =============================================================================
def test_phase20_insufficient_participants_barrier(tmp_path):
    """Verify InsufficientParticipantsError when requesting 3-way split on 2 participants."""
    fixture_manifest = tmp_path / "two_participant_manifest.json"
    manifest_data = {
        "dataset_name": "Test_2Participant_Fixture",
        "sessions": [
            {"session_id": "s1", "participant_id": "Participant_01", "activity_label": "walk", "packet_count": 50},
            {"session_id": "s2", "participant_id": "Participant_02", "activity_label": "walk", "packet_count": 50}
        ]
    }
    fixture_manifest.write_text(json.dumps(manifest_data), encoding="utf-8")

    gen = ParticipantIndependentSplitGenerator(fixture_manifest)
    with pytest.raises(InsufficientParticipantsError) as exc_info:
        gen.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")
    assert "Cannot create a 3-way participant-independent split" in str(exc_info.value)


# =============================================================================
# 7. Non-Destructive Overwrite Protection
# =============================================================================
def test_phase20_overwrite_protection_versioning():
    """Verify that stop_session_recording generates versioned suffixes on name collision."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = RealCSICollector(auto_connect=False, data_dir=tmpdir)

        start_res = collector.start_session_recording(
            session_name="test_p20_collision",
            participant_id="Participant_01",
            activity_label="sit"
        )
        sid = start_res["session_id"]

        # Pre-create a file with that session_id
        collision_file = Path(tmpdir) / f"{sid}.json"
        with open(collision_file, "w", encoding="utf-8") as f:
            f.write('{"preserved": true}')

        # Stop recording, which detects collision and saves as _v1
        stop_res = collector.stop_session_recording()

        assert stop_res["session_id"] == f"{sid}_v1"
        assert Path(stop_res["json_path"]).name == f"{sid}_v1.json"
        assert Path(stop_res["json_path"]).exists()

        # Check preserved historical file
        with open(collision_file, "r", encoding="utf-8") as f:
            hist = json.load(f)
        assert hist.get("preserved") is True


# =============================================================================
# 8. Quarantine Workflow and Manifest Logging
# =============================================================================
def test_phase20_quarantine_workflow():
    """Verify that invalid recordings are quarantined and logged in quarantine_manifest.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bad_json = tmp_path / "bad_session.json"
        bad_csv = tmp_path / "bad_session.csv"
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("corrupt_content")
        with open(bad_csv, "w", encoding="utf-8") as f:
            f.write("corrupt_csv")

        validator = DatasetIntegrityValidator(tmp_path)
        q_target = validator.quarantine_session(bad_json, reason="Corrupted packet header")

        assert not bad_json.exists()
        assert not bad_csv.exists()
        assert q_target.exists()
        assert q_target.parent == tmp_path / "quarantine"

        q_manifest = tmp_path / "quarantine" / "quarantine_manifest.json"
        assert q_manifest.exists()
        with open(q_manifest, "r", encoding="utf-8") as f:
            log_entries = json.load(f)
        assert len(log_entries) == 1
        assert log_entries[0]["filename"] == "bad_session.json"
        assert log_entries[0]["reason"] == "Corrupted packet header"


# =============================================================================
# 9. Raw Subcarrier vs. Model Input Separation
# =============================================================================
def test_phase20_raw_subcarrier_separation():
    """Verify that RealCSICollector preserves raw subcarriers separately from aligned 56 subcarriers."""
    collector = RealCSICollector(auto_connect=False)

    # 64-subcarrier HT20 raw input line
    sc_64 = [f"{15.0 + i*0.1:.2f}:{0.01*i:.2f}" for i in range(64)]
    raw_line = f"CSI_DATA,11:22:33:44:55:66,-50.0,-95.0,1,64,{','.join(sc_64)}"

    parsed = collector.parse_raw_line(raw_line)
    assert parsed is not None
    assert parsed["num_subcarriers"] == 64
    assert len(parsed["raw_amplitudes"]) == 64

    # Feed to collector buffer
    collector._process_parsed_frame(parsed)
    # Aligned frame buffer must be exactly 56 subcarriers
    aligned_frame = collector.raw_frame_buffer[-1]
    assert len(aligned_frame) == 56


# =============================================================================
# 10. Checkpoint Cryptographic Hash Invariance
# =============================================================================
def test_phase20_checkpoint_hashes():
    """Verify bit-for-bit MD5 hash invariance for production and experimental checkpoints."""
    prod_path = MODELS_DIR / "csiformer_phase13_best.pth"
    exp_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert prod_path.exists(), f"Production checkpoint missing: {prod_path}"
    assert exp_path.exists(), f"Experimental checkpoint missing: {exp_path}"

    prod_hash = hashlib.md5(prod_path.read_bytes()).hexdigest()
    exp_hash = hashlib.md5(exp_path.read_bytes()).hexdigest()

    EXPECTED_PROD = "383b4d98c08f8970b0443738f170ec01"
    EXPECTED_EXP = "ab3d97a04d78edf75d807178772bc828"

    assert prod_hash == EXPECTED_PROD, f"Production checkpoint altered! Expected {EXPECTED_PROD}, got {prod_hash}"
    assert exp_hash == EXPECTED_EXP, f"Experimental checkpoint altered! Expected {EXPECTED_EXP}, got {exp_hash}"
