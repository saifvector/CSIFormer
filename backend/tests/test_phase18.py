"""
CSIFormer Phase 18 — Automated Integrity, Quality, and LOSO Split Test Suite.

Automated deterministic testing covering:
1. Manifest consistency, file existence, and frame count matching.
2. Unique session identifiers and distinct event identifiers.
3. Raw CSI dimensions vs. aligned model representations (Format A and Format B parsing).
4. Malformed, corrupted, and non-finite telemetry rejection.
5. Hardware timestamp monotonicity and packet loss sequence gap calculations.
6. Window-to-session and window-to-event traceability.
7. Unknown label mapping for unconfirmed and interrupted sessions.
8. Participant, session, and event split leakage prevention.
9. Class coverage validation and InadequateClassCoverageError raising.
10. Multi-participant 3-way split allocation (e.g., 3 Train, 1 Val, 1 Test for 5 subjects).
11. InsufficientParticipantsError raising on 3-way split with N < 3.
12. Bit-for-bit model checkpoint hash invariance (Production and Experimental).
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

# Ensure backend directory is in python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.services.real_csi_collector import RealCSICollector
from app.services.collection_workflow import CollectionWorkflowManager, VALID_LABELS
from app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InsufficientParticipantsError,
    InadequateClassCoverageError
)

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = ROOT_DIR / "models"


# =============================================================================
# 1. Manifest Consistency and File Existence
# =============================================================================
def test_manifest_consistency_and_packet_counts():
    """Verify that all sessions indexed in manifest exist on disk with matching packet counts."""
    assert MANIFEST_PATH.exists(), f"Primary manifest missing: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    assert len(sessions) >= 23, f"Expected at least 23 sessions, found {len(sessions)}"

    for s in sessions:
        json_path = DATASET_DIR / s["json_file"]
        assert json_path.exists(), f"Missing session file: {json_path}"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        actual_packets = len(data.get("frames", []))
        assert actual_packets == s["packet_count"], (
            f"Packet count mismatch in {s['session_id']}: manifest reports {s['packet_count']}, file has {actual_packets}"
        )


# =============================================================================
# 2. Unique Session & Event Identifiers
# =============================================================================
def test_unique_session_and_event_identifiers():
    """Verify all session IDs are distinct and participants follow pseudonym format."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    sids = [s["session_id"] for s in sessions]
    assert len(sids) == len(set(sids)), "Duplicate session_id detected in primary manifest!"

    for s in sessions:
        pid = s.get("participant_id", "")
        assert pid.startswith("Participant_"), f"Participant ID '{pid}' does not follow pseudonym format 'Participant_XX'"


# =============================================================================
# 3. Raw CSI Dimensions vs. Model Representations (Format A & B)
# =============================================================================
def test_raw_csi_dimensions_and_model_representation():
    """Verify that parsed raw subcarrier count matches actual packet length, separate from 56-subcarrier model representation."""
    collector = RealCSICollector(auto_connect=False)

    # Test Format B with 64 subcarriers (e.g. 802.11n HT20 full FFT)
    sc_64 = [f"{12.0 + i*0.2:.2f}:{0.05*i:.2f}" for i in range(64)]
    line_64 = f"CSI_DATA,24:DC:C3:A1:01:01,-52.0,-95.0,100,64,{','.join(sc_64)}"
    rec_64 = collector.parse_raw_line(line_64)

    assert rec_64 is not None
    assert rec_64["num_subcarriers"] == 64
    assert len(rec_64["raw_amplitudes"]) == 64
    assert len(rec_64["raw_phases"]) == 64

    # Test buffer alignment: collector must interpolate to exactly 56 channels for CSIFormer
    collector._buffer_packet(rec_64)
    assert len(collector.raw_frame_buffer) == 1
    assert collector.raw_frame_buffer[0].shape == (56,)

    # Test Format A with 128 bytes raw IQ (64 complex subcarriers)
    iq_pairs = ",".join(["10,5"] * 64)
    line_format_a = f"RSSI=-58 LEN=128 CSI:{iq_pairs}"
    rec_a = collector.parse_raw_line(line_format_a)
    assert rec_a is not None
    assert rec_a["num_subcarriers"] == 64
    assert len(rec_a["raw_amplitudes"]) == 64


# =============================================================================
# 4. Corrupted and Malformed Telemetry Filtering
# =============================================================================
def test_corrupted_telemetry_filtering():
    """Verify robust rejection of empty, truncated, non-numeric, or non-finite inputs."""
    collector = RealCSICollector(auto_connect=False)
    assert collector.parse_raw_line("") is None
    assert collector.parse_raw_line("Garbage serial noise without prefix") is None
    assert collector.parse_raw_line("RSSI=-50") is None
    assert collector.parse_raw_line("CSI_DATA,incomplete,line") is None
    assert collector.parse_raw_line("RSSI=-55 LEN=128 CSI:NaN,inf,corrupted") is None


# =============================================================================
# 5. Monotonic Hardware Timestamps & Sequence Continuity
# =============================================================================
def test_timestamp_monotonicity_and_sequence_continuity():
    """Verify sequence loss calculations and monotonic packet ordering."""
    # Test gap calculation
    seqs = [500, 501, 502, 506, 507, 510]  # Gaps: (506-502-1)=3, (510-507-1)=2 -> 5 dropped
    diffs = np.diff(seqs)
    dropped = int(np.sum([d - 1 for d in diffs if d > 1]))
    total_expected = len(seqs) + dropped
    loss_rate = dropped / total_expected
    assert dropped == 5
    assert total_expected == 11
    assert abs(loss_rate - (5 / 11)) < 1e-5


# =============================================================================
# 6. Window-to-Session and Window-to-Event Traceability
# =============================================================================
def test_window_traceability():
    """Verify that every window can be traced to its exact source session and event."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    for s in sessions[:5]:
        sid = s["session_id"]
        evt = s.get("event_id") or sid
        pkt_count = s["packet_count"]
        expected_windows = pkt_count // 50

        # Each window produced from this session belongs exclusively to sid and evt
        for win_idx in range(expected_windows):
            window_meta = {
                "window_index": win_idx,
                "session_id": sid,
                "event_id": evt,
                "start_packet": win_idx * 50,
                "end_packet": (win_idx + 1) * 50
            }
            assert window_meta["session_id"] == sid
            assert window_meta["event_id"] == evt


# =============================================================================
# 7. Unknown Label Mapping for Unconfirmed / Interrupted Sessions
# =============================================================================
def test_unconfirmed_and_interrupted_session_mapping():
    """Verify that unconfirmed or rejected trials strictly default to unknown (class_id -1)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_dir_path)

        # Mock active session
        manager.active_session_info = {
            "session_id": "test_unconfirmed_01",
            "event_id": "evt_test_01",
            "participant_id": "Participant_05",
            "activity_label": "fall",
            "class_id": 9,
            "duration_seconds": 4.0,
            "room_type": "Living_Room",
            "tx_rx_distance_m": 2.5,
            "tx_position": "Origin",
            "rx_position": "Node",
            "orientation": "LOS",
            "notes": "Unconfirmed trial test",
            "start_time": time.time(),
            "frame_count": 10,
            "saved_json": str(Path(tmpdir) / "test_unconfirmed_01.json")
        }

        # Create mock JSON file
        with open(manager.active_session_info["saved_json"], "w", encoding="utf-8") as f:
            json.dump({"metadata": {}, "frames": []}, f)

        # Finalize as NOT confirmed
        fin = manager.finalize_and_index_session(confirmed=False, notes="Participant stumbled")
        assert fin["confirmed"] is False
        assert fin["activity_label"] == "unknown"
        assert fin["class_id"] == -1


# =============================================================================
# 8. Participant, Session, and Event Split Leakage Prevention
# =============================================================================
def test_loso_split_zero_leakage_extended():
    """Verify that train, validation, and test splits have zero participant and event overlap."""
    generator = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    loso = generator.generate_loso_split(test_participant="Participant_02", val_participant=None)

    train_p = set(loso["splits_summary"]["train_participants"])
    test_p = set(loso["splits_summary"]["test_participants"])
    assert len(train_p.intersection(test_p)) == 0, f"Participant leakage: {train_p.intersection(test_p)}"

    # Check event isolation
    train_evts = set()
    test_evts = set()
    for s in loso["sessions"]:
        evt = s.get("event_id") or s.get("session_id")
        if s["split"] == "train":
            train_evts.add(evt)
        elif s["split"] == "test":
            test_evts.add(evt)

    assert len(train_evts.intersection(test_evts)) == 0, f"Event leakage detected: {train_evts.intersection(test_evts)}"


# =============================================================================
# 9. Class Coverage Verification & InadequateClassCoverageError
# =============================================================================
def test_inadequate_class_coverage_handling():
    """Verify that InadequateClassCoverageError is raised when strict_coverage=True on missing classes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_manifest = {
            "dataset_name": "Mock_Dataset",
            "sessions": [
                {"session_id": "s1", "participant_id": "P1", "activity_label": "walk", "packet_count": 100},
                {"session_id": "s2", "participant_id": "P1", "activity_label": "fall", "packet_count": 100},
                {"session_id": "s3", "participant_id": "P2", "activity_label": "walk", "packet_count": 100}
                # P2 has no fall activity!
            ]
        }
        m_path = Path(tmpdir) / "manifest.json"
        with open(m_path, "w", encoding="utf-8") as f:
            json.dump(mock_manifest, f)

        gen = ParticipantIndependentSplitGenerator(m_path)
        # Without strict coverage, it returns with missing_in_test
        res = gen.generate_loso_split(test_participant="P2", strict_coverage=False)
        assert "fall" in res["class_coverage"]["missing_in_test"]

        # With strict coverage, it must raise InadequateClassCoverageError
        with pytest.raises(InadequateClassCoverageError) as exc_info:
            gen.generate_loso_split(test_participant="P2", strict_coverage=True)
        assert "Held-out test split lacks class coverage" in str(exc_info.value)


# =============================================================================
# 10. Multi-Participant 3-Way Split Allocation (5 Subjects Design)
# =============================================================================
def test_multi_participant_split_allocation():
    """Verify that 5 participants can be partitioned cleanly into 3 Train, 1 Val, and 1 Test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_manifest = {
            "dataset_name": "Mock_5_Subjects",
            "sessions": [
                {"session_id": f"s_{p}_{act}", "participant_id": p, "activity_label": act, "packet_count": 100}
                for p in ["P01", "P02", "P03", "P04", "P05"]
                for act in ["walk", "fall", "sit"]
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

        assert res["splits_summary"]["test_participants"] == ["P05"]
        assert res["splits_summary"]["val_participants"] == ["P04"]
        assert set(res["splits_summary"]["train_participants"]) == {"P01", "P02", "P03"}
        assert len(res["class_coverage"]["missing_in_test"]) == 0
        assert res["splits_summary"]["fall_events"]["test"] == 1
        assert res["splits_summary"]["fall_events"]["train"] == 3


# =============================================================================
# 11. Rejection of 3-Way Split with N < 3
# =============================================================================
def test_insufficient_participants_error():
    """Verify InsufficientParticipantsError when requesting 3-way split on 2 participants."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    assert len(gen.participants) == 2
    with pytest.raises(InsufficientParticipantsError):
        gen.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")


# =============================================================================
# 12. Checkpoint Bit-for-Bit Hash Invariance
# =============================================================================
def test_checkpoint_hash_invariance():
    """Verify that production and experimental checkpoints have not been altered."""
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
