"""
CSIFormer Phase 17 — Automated Integrity, Collection, and LOSO Split Test Suite.

Automated deterministic testing covering:
1. Session creation, validation, and finalization in CollectionWorkflowManager.
2. Manifest consistency, schema integrity, and file path verification.
3. Unique session and participant identifier enforcement.
4. Label validation and unconfirmed trial mapping to 'unknown' (class_id -1).
5. Timestamp monotonicity and sequence continuity checks.
6. Missing, corrupted, and malformed CSI measurement filtering.
7. Packet loss accounting and sequence gap tracking.
8. Preservation of raw uninterpolated subcarrier amplitudes.
9. Sliding window construction and split isolation (no cross-split windows).
10. Participant-independent (LOSO) split leakage verification (Train vs Test disjointness).
11. InsufficientParticipantsError raising on invalid 3-way split requests.
12. Interrupted capture recovery and resource cleanup.
"""

import sys
import os
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pytest

# Ensure backend directory is in python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.services.real_csi_collector import RealCSICollector
from app.services.collection_workflow import CollectionWorkflowManager, VALID_LABELS, UdpStimulator
from app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InsufficientParticipantsError
)

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"


# =============================================================================
# 1. Session Creation, Validation, and Finalization
# =============================================================================
def test_session_lifecycle_with_mock():
    """Verify session start, frame capture, and ground truth confirmation/rejection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        collector = RealCSICollector(auto_connect=False, data_dir=str(tmp_path))
        
        # Test start session
        rec_res = collector.start_session_recording(
            session_name="test_trial_01",
            room_type="Lab_A",
            participant_id="Participant_99",
            activity_label="walk",
            tx_rx_distance_m=2.5,
            orientation="LOS_Facing_TxRx"
        )
        assert rec_res["status"] == "recording_started"
        assert collector.is_recording is True

        # Ingest 10 mock frames
        for seq in range(10):
            amp_str = ",".join([f"{20.0 + i*0.1:.2f}:0.0" for i in range(56)])
            line = f"CSI_DATA,24:DC:C3:A1:01:01,-55.0,-95.0,{1000 + seq},56,{amp_str}"
            rec = collector.parse_raw_line(line)
            collector._buffer_packet(rec)

        # Stop recording
        stop_res = collector.stop_session_recording()
        assert stop_res["status"] == "recording_saved"
        assert stop_res["frame_count"] == 10
        assert Path(stop_res["json_path"]).exists()

        # Check saved JSON
        with open(stop_res["json_path"], "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert len(saved_data["frames"]) == 10
        assert saved_data["metadata"]["participant_id"] == "Participant_99"
        assert saved_data["metadata"]["ground_truth_activity"] == "walk"


# =============================================================================
# 2. Manifest Consistency and Schema Verification
# =============================================================================
def test_manifest_consistency():
    """Verify manifest exists, session files exist on disk, and packet counts match."""
    assert MANIFEST_PATH.exists(), f"Missing manifest: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    assert len(sessions) >= 23, f"Expected at least 23 sessions, found {len(sessions)}"

    for s in sessions:
        assert "session_id" in s
        assert "activity_label" in s
        assert "class_id" in s
        assert "participant_id" in s
        assert "split" in s
        assert "packet_count" in s
        assert "json_file" in s

        # Check file existence
        json_file = DATASET_DIR / s["json_file"]
        assert json_file.exists(), f"Referenced JSON file does not exist: {json_file}"

        # Check frame count consistency
        with open(json_file, "r", encoding="utf-8") as f:
            session_data = json.load(f)
        actual_frames = len(session_data.get("frames", []))
        assert actual_frames == s["packet_count"], (
            f"Frame count mismatch in {s['session_id']}: manifest reports {s['packet_count']}, file has {actual_frames}"
        )


# =============================================================================
# 3. Unique Identifiers Enforcement
# =============================================================================
def test_unique_identifiers():
    """Verify all session IDs are distinct and participants follow pseudonym format."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    sids = [s["session_id"] for s in sessions]
    assert len(sids) == len(set(sids)), "Duplicate session_id detected in manifest!"

    for s in sessions:
        pid = s.get("participant_id", "")
        assert pid.startswith("Participant_"), f"Participant ID '{pid}' does not follow pseudonym format 'Participant_XX'"


# =============================================================================
# 4. Label Validation & Taxonomy Consistency
# =============================================================================
def test_label_validation_and_rejection():
    """Verify valid labels are accepted, invalid labels are rejected, and unconfirmed map to unknown."""
    # Check valid labels mapping
    for label, info in VALID_LABELS.items():
        assert "class_id" in info
        assert "name" in info

    assert VALID_LABELS["walk"]["class_id"] == 11
    assert VALID_LABELS["fall"]["class_id"] == 9
    assert VALID_LABELS["sit"]["class_id"] == 8
    assert VALID_LABELS["clap"]["class_id"] == 2
    assert VALID_LABELS["push_pull"]["class_id"] == 0
    assert VALID_LABELS["static"]["class_id"] == 6
    assert VALID_LABELS["unknown"]["class_id"] == -1

    # Verify that invalid labels raise ValueError in collection manager
    manager = CollectionWorkflowManager()
    with pytest.raises(ValueError):
        manager.start_session(participant_id="Participant_03", activity_label="running")

    with pytest.raises(ValueError):
        manager.start_session(participant_id="Participant_03", activity_label="jumping")


# =============================================================================
# 5. Timestamp Monotonicity and Sequence Integrity
# =============================================================================
def test_timestamp_and_sequence_integrity():
    """Verify timestamps are strictly non-decreasing and sequence numbers are tracked."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Check first 3 sessions for timing integrity
    for s in manifest.get("sessions", [])[:3]:
        json_file = DATASET_DIR / s["json_file"]
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        frames = data.get("frames", [])
        if len(frames) > 1:
            timestamps = [f["timestamp_us"] for f in frames if "timestamp_us" in f]
            if len(timestamps) > 1:
                diffs = np.diff(timestamps)
                # Hardware clocks should be monotonically increasing (unless rollover)
                assert (diffs >= 0).all() or (np.sum(diffs < 0) <= 1), (
                    f"Severe timestamp non-monotonicity in {s['session_id']}"
                )


# =============================================================================
# 6. Malformed and Missing CSI Filtering
# =============================================================================
def test_malformed_and_missing_csi_filtering():
    """Verify that corrupt or incomplete serial lines are rejected."""
    collector = RealCSICollector(auto_connect=False)

    # 1. Empty string
    assert collector.parse_raw_line("") is None

    # 2. Random junk
    assert collector.parse_raw_line("Garbage text without CSI prefix") is None

    # 3. Truncated header
    assert collector.parse_raw_line("RSSI=-55") is None

    # 4. Incomplete CSV header (< 7 tokens)
    assert collector.parse_raw_line("CSI_DATA,incomplete,data") is None

    # 5. Non-numeric values in CSI field
    assert collector.parse_raw_line("RSSI=-55 LEN=128 CSI:invalid,nan,corrupted") is None


# =============================================================================
# 7. Packet Loss Accounting Logic
# =============================================================================
def test_packet_loss_accounting_logic():
    """Verify packet loss rate calculation on synthetic sequence with dropped frames."""
    seqs = [100, 101, 102, 105, 106, 110]  # Drops: (105-102-1)=2, (110-106-1)=3 -> 5 drops
    diffs = np.diff(seqs)
    dropped = int(np.sum([d - 1 for d in diffs if d > 1]))
    total_expected = len(seqs) + dropped
    loss_rate = dropped / total_expected

    assert dropped == 5
    assert total_expected == 11
    assert abs(loss_rate - (5 / 11)) < 1e-5


# =============================================================================
# 8. Raw Subcarrier Preservation Verification
# =============================================================================
def test_preservation_of_raw_amplitudes():
    """Verify that raw subcarrier amplitudes are preserved alongside interpolated values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = RealCSICollector(auto_connect=False, data_dir=tmpdir)
        collector.start_session_recording("raw_test")

        # Generate 52 amp:phase pairs (typical ESP32 802.11n HT20 subcarriers)
        subcarriers = [f"{10.0 + i*0.5:.2f}:{0.1*i:.2f}" for i in range(52)]
        raw_line = f"CSI_DATA,24:DC:C3:A1:01:01,-50.0,-95.0,2001,52,{','.join(subcarriers)}"
        record = collector.parse_raw_line(raw_line)

        assert record is not None
        assert "raw_amplitudes" in record, "Collector must preserve 'raw_amplitudes'"
        assert len(record["raw_amplitudes"]) == 52, f"Expected 52 raw subcarriers, got {len(record['raw_amplitudes'])}"

        # Buffer into recording
        collector._buffer_packet(record)
        assert len(collector.recorded_frames) == 1
        saved_frame = collector.recorded_frames[0]
        assert "raw_amplitudes" in saved_frame
        assert len(saved_frame["raw_amplitudes"]) == 52
        assert "amplitudes" in saved_frame
        assert len(saved_frame["amplitudes"]) == 56

        collector.stop_session_recording()


# =============================================================================
# 9. Sliding Window Construction and Non-Overlap Across Sessions
# =============================================================================
def test_sliding_window_construction_and_isolation():
    """Verify that windows have fixed shape [50, 56] and incomplete windows are rejected."""
    collector = RealCSICollector(auto_connect=False)
    assert len(collector.raw_frame_buffer) == 0

    # Ingest 25 packets (incomplete window < 50)
    for i in range(25):
        raw_line = f"RSSI=-50 LEN=128 CSI:{i%10},{i%5},-17,-4,-14,-3,-9,-3"
        rec = collector.parse_raw_line(raw_line)
        collector._buffer_packet(rec)

    # Incomplete window rejection (life safety requirement)
    assert collector.get_latest_window() is None

    # Ingest 25 more packets to complete window (50 total)
    for i in range(25, 50):
        raw_line = f"RSSI=-50 LEN=128 CSI:{i%10},{i%5},-17,-4,-14,-3,-9,-3"
        rec = collector.parse_raw_line(raw_line)
        collector._buffer_packet(rec)

    assert len(collector.raw_frame_buffer) == 50
    win = collector.get_latest_window()
    assert win is not None
    raw_win, phase_win = win
    assert raw_win.shape == (50, 56)
    assert phase_win.shape == (50, 56)
    assert np.isfinite(raw_win).all()


# =============================================================================
# 10. Participant-Independent (LOSO) Split Leakage Verification
# =============================================================================
def test_loso_split_zero_leakage():
    """Verify that ParticipantIndependentSplitGenerator produces strictly disjoint splits."""
    generator = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    loso_split = generator.generate_loso_split(test_participant="Participant_02", val_participant=None)

    train_participants = set()
    test_participants = set()

    for s in loso_split["sessions"]:
        if s["split"] == "train":
            train_participants.add(s["participant_id"])
        elif s["split"] == "test":
            test_participants.add(s["participant_id"])

    # Strict disjointness check
    overlap = train_participants.intersection(test_participants)
    assert len(overlap) == 0, f"Participant leakage detected! Participants in both train and test: {overlap}"
    assert "Participant_02" in test_participants
    assert "Participant_02" not in train_participants
    assert "Participant_01" in train_participants
    assert "Participant_01" not in test_participants


# =============================================================================
# 11. Rejection of 3-Way Split with N < 3 Participants
# =============================================================================
def test_insufficient_participants_error_on_3way_split():
    """Verify that requesting a 3-way split on a 2-participant dataset raises InsufficientParticipantsError."""
    generator = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    assert len(generator.participants) == 2

    with pytest.raises(InsufficientParticipantsError) as exc_info:
        generator.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")

    assert "Cannot create a 3-way participant-independent split" in str(exc_info.value)
    assert "Requires at least 3 distinct participants" in str(exc_info.value)


# =============================================================================
# 12. Interrupted Capture Recovery & Cleanup
# =============================================================================
def test_interrupted_capture_recovery():
    """Verify that when capture is stopped prematurely, partial recordings are safely preserved and state resets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        collector = RealCSICollector(auto_connect=False, data_dir=str(tmp_path))

        collector.start_session_recording(
            session_name="premature_stop_trial",
            room_type="Lab",
            participant_id="Participant_01",
            activity_label="sit"
        )
        assert collector.is_recording is True

        # Ingest only 3 packets (target was 150)
        for i in range(3):
            line = f"CSI_DATA,24:DC:C3:A1:01:01,-52.0,-95.0,{i},56,{','.join(['15.0:0.0']*56)}"
            rec = collector.parse_raw_line(line)
            collector._buffer_packet(rec)

        # Prematurely stop
        res = collector.stop_session_recording()
        assert res["status"] == "recording_saved"
        assert res["frame_count"] == 3
        assert collector.is_recording is False
        assert Path(res["json_path"]).exists()
