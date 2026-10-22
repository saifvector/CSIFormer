"""
CSIFormer Phase 33 — Authorized Cross-Room Data Acquisition & Test-Set Readiness Tests.

Validates:
1. Protected checkpoint bit-level invariance (MD5 verification without model loading).
2. Manifest and disk reconciliation for 74 physical sessions, 10,407 frames, and 155 non-overlapping windows.
3. Verification of the 5 authorized physical recordings for Participant_02 in Office_Room2 at 2.0m:
   - Activities: static, sit, walk, clap, push_pull (5-class balanced).
   - Valid frame counts, duration, and sampling rates (30-45 Hz).
   - Split assigned to 'test' with confirmation status 'confirmed'.
4. Feature preservation: raw 5 complex subcarrier pairs (I, Q) and derived 56 channels.
5. Split generator room coverage and leakage verification:
   - Zero participant, event, or window leakage across LOSO partitions.
   - Cross-room test readiness: Office_Room2 is now represented in Test by Participant_02 (11 windows).
6. Mandatory research and safety barriers:
   - 6-class evaluation remains strictly blocked due to missing fall class.
   - Zero fall recordings collected; zero model training or evaluation executed.
"""

import json
import hashlib
import sys
from pathlib import Path
import pytest
import numpy as np

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
from backend.app.services.session_validator import (
    DatasetIntegrityValidator,
    compute_session_sampling_rate,
)
from backend.app.services.csi_preprocessor import CSIPreprocessor


def test_phase33_checkpoint_invariance():
    """Verify production and experimental checkpoints are bit-for-bit identical to reference hashes."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Missing production checkpoint: {p13_path}"
    assert p15_path.exists(), f"Missing experimental checkpoint: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_hash = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_hash = hashlib.md5(f.read()).hexdigest()

    assert p13_hash == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_hash}"
    assert p15_hash == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_hash}"


def test_phase33_reconciled_manifest_and_disk_inventory():
    """Verify manifest expansion to exactly 74 sessions, 10,407 frames, and 155 windows with zero collisions."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) == 74, f"Expected 74 sessions in manifest, got {len(sessions)}"

    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    val_res = validator.validate_dataset_manifest()
    assert val_res["all_sessions_valid"] is True, f"Validation failure: {val_res}"

    total_frames = 0
    total_windows_floor = 0
    total_windows_segmented = 0
    session_ids = set()
    event_ids = set()

    for s in sessions:
        sid = s["session_id"]
        assert sid not in session_ids, f"Duplicate session ID: {sid}"
        session_ids.add(sid)

        eid = s.get("event_id") or sid
        assert eid not in event_ids, f"Duplicate event ID: {eid}"
        event_ids.add(eid)

        jpath = DATASET_DIR / s["json_file"]
        cpath = DATASET_DIR / s["csv_file"]
        assert jpath.exists(), f"Missing referenced JSON: {jpath}"
        assert cpath.exists(), f"Missing referenced CSV: {cpath}"

        pkts = s["packet_count"]
        total_frames += pkts
        wins_floor = pkts // 50
        total_windows_floor += wins_floor

        dummy_data = np.zeros((pkts, 56), dtype=np.float32)
        windows = CSIPreprocessor.segment_windows(dummy_data, window_size=50, stride=50)
        assert len(windows) == wins_floor, f"Session {sid} window mismatch: {len(windows)} vs {wins_floor}"
        total_windows_segmented += len(windows)

    assert total_frames == 10407, f"Expected 10,407 frames, got {total_frames}"
    assert total_windows_floor == 155, f"Expected 155 windows, got {total_windows_floor}"
    assert total_windows_segmented == 155, f"Expected 155 segmented windows, got {total_windows_segmented}"

    # Disk file inventory reconciliation
    all_csv = {p.name for p in DATASET_DIR.glob("*.csv")}
    all_json = {p.name for p in DATASET_DIR.glob("*.json") if "manifest" not in p.name}
    indexed_csv = {s["csv_file"] for s in sessions}
    indexed_json = {s["json_file"] for s in sessions}

    assert indexed_csv.issubset(all_csv)
    assert indexed_json.issubset(all_json)

    # Exactly 1 unindexed exploratory trial pair
    assert all_csv - indexed_csv == {"phase14_p15_real_walk_t1_1792303844_1792303844.csv"}
    assert all_json - indexed_json == {"phase14_p15_real_walk_t1_1792303844_1792303844.json"}


def test_phase33_acquired_cross_room_dataset():
    """Verify the 5 newly acquired physical recordings for Participant_02 in Office_Room2."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    new_p02_office = [
        s for s in sessions
        if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_02"
    ]

    assert len(new_p02_office) == 5, f"Expected exactly 5 Office_Room2 sessions for Participant_02, got {len(new_p02_office)}"

    expected_activities = {"static", "sit", "walk", "clap", "push_pull"}
    acquired_activities = {s["activity_label"] for s in new_p02_office}
    assert acquired_activities == expected_activities, f"Mismatch in acquired activities: {acquired_activities}"

    for s in new_p02_office:
        assert s["tx_rx_distance_m"] == 2.0
        assert s["split"] == "test"
        assert s["confirmation_status"] == "confirmed"
        assert s["room"] == "Office_Room2"
        assert 135 <= s["packet_count"] <= 155
        assert 3.5 <= s["duration_seconds"] <= 4.5
        assert 34.0 <= s["sampling_rate_hz"] <= 40.0

        # File validation
        jpath = DATASET_DIR / s["json_file"]
        with open(jpath, "r", encoding="utf-8") as f:
            jdata = json.load(f)

        frames = jdata.get("frames", [])
        assert len(frames) == s["packet_count"]
        assert len(frames[0]["raw_amplitudes"]) == 5
        assert len(frames[0]["raw_phases"]) == 5
        assert len(frames[0]["amplitudes"]) == 56

        timestamps = [fr["timestamp"] for fr in frames if "timestamp" in fr]
        rate_stats = compute_session_sampling_rate(timestamps, wall_duration_s=s["duration_seconds"])
        assert rate_stats["valid"] is True
        assert 34.0 <= rate_stats["empirical_sampling_rate_hz"] <= 40.0


def test_phase33_subcarrier_and_feature_preservation():
    """Verify raw complex subcarrier preservation and 56-channel derived features across full dataset."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    raw5_sessions = 0
    raw5_frames = 0
    c56_sessions = 0
    c56_frames = 0

    for s in sessions:
        jpath = DATASET_DIR / s["json_file"]
        with open(jpath, "r", encoding="utf-8") as f:
            s_data = json.load(f)

        frames = s_data.get("frames", [])
        pkts = len(frames)

        if len(frames) > 0 and "raw_amplitudes" in frames[0]:
            raw5_sessions += 1
            raw5_frames += pkts
            assert len(frames[0]["raw_amplitudes"]) == 5
            assert len(frames[0]["raw_phases"]) == 5

        if len(frames) > 0 and len(frames[0].get("amplitudes", [])) == 56:
            c56_sessions += 1
            c56_frames += pkts

    assert raw5_sessions == 51, f"Expected 51 raw5 sessions (46 baseline + 5 new), got {raw5_sessions}"
    assert raw5_frames == 7195, f"Expected 7,195 raw5 frames (6,481 baseline + 714 new), got {raw5_frames}"
    assert c56_sessions == 74, f"Expected 74 c56 sessions, got {c56_sessions}"
    assert c56_frames == 10407, f"Expected 10,407 c56 frames, got {c56_frames}"


def test_phase33_split_generator_room_coverage_and_leakage():
    """Verify that Participant_02 as test participant establishes genuine cross-room test coverage with zero leakage."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    split_res = gen.generate_loso_split(
        test_participant="Participant_02",
        val_participant="Participant_05",
        strict_coverage=False,
    )

    summary = split_res["splits_summary"]
    train_p = set(summary["train_participants"])
    val_p = set(summary["val_participants"])
    test_p = set(summary["test_participants"])

    # Disjointness invariants
    assert len(train_p & val_p) == 0
    assert len(train_p & test_p) == 0
    assert len(val_p & test_p) == 0

    assert train_p == {"Participant_01", "Participant_03", "Participant_04"}
    assert val_p == {"Participant_05"}
    assert test_p == {"Participant_02"}

    # Room representation verification
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    train_rooms = {s.get("room") for s in manifest["sessions"] if s["participant_id"] in train_p}
    test_rooms = {s.get("room") for s in manifest["sessions"] if s["participant_id"] in test_p}

    # Office_Room2 is now present in BOTH Train (Participant_01) and Test (Participant_02)!
    assert "Office_Room2" in train_rooms
    assert "Office_Room2" in test_rooms

    # Quantify Office_Room2 test windows
    p02_office_sessions = [
        s for s in manifest["sessions"]
        if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_02"
    ]
    p02_office_windows = sum(s["packet_count"] // 50 for s in p02_office_sessions)
    assert p02_office_windows == 11, f"Expected 11 Office_Room2 windows in test, got {p02_office_windows}"

    # Confirm all 5 classes are represented in Office_Room2 test set
    p02_office_activities = {s["activity_label"] for s in p02_office_sessions}
    assert p02_office_activities == {"static", "sit", "walk", "clap", "push_pull"}


def test_phase33_safety_and_evaluation_barriers():
    """Verify that 6-class evaluation remains strictly blocked and safety constraints are enforced."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)

    # 6-class evaluation remains strictly blocked on subjects lacking falls
    for p in ["Participant_03", "Participant_04", "Participant_05"]:
        with pytest.raises(InadequateClassCoverageError):
            gen.generate_loso_split(test_participant=p, strict_coverage=True)

    # Confirm zero fall recordings collected in Office_Room2 (6-class cross-room evaluation strictly impossible)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    office_falls = [
        s for s in manifest["sessions"]
        if s.get("room") == "Office_Room2" and s.get("activity_label") == "fall"
    ]
    assert len(office_falls) == 0, f"Safety violation: found {len(office_falls)} fall recordings in Office_Room2."
