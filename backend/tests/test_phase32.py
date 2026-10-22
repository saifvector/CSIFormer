"""
CSIFormer Phase 32 — Cross-Room Collection Planning & Evaluation Split Integrity Tests.

Validates:
1. Protected checkpoint bit-level invariance (MD5 verification without model loading).
2. Physical dataset reconciliation (69 sessions, 9,693 frames, 144 non-overlapping windows).
3. Raw 5-subcarrier and derived 56-channel preservation and empirical sampling-rate validity.
4. Identification of the physical data gap: Office_Room2 currently contains only Participant_01;
   Participant_02 has exactly 0 recordings in Office_Room2.
5. Split generator audit: verification of zero participant/event/window leakage, assignment
   of Office_Room2 to Train in existing LOSO split, and zero Office_Room2 presence in Test.
6. Evaluation protocol readiness barriers:
   - 6-class evaluation strictly blocked by missing fall data.
   - Cross-room evaluation protocol blocked until missing Participant_02 Office_Room2 data is acquired.
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


def test_phase32_checkpoint_invariance():
    """Verify both production and experimental checkpoints match immutable reference hashes."""
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


def test_phase32_reconciled_manifest_and_disk_inventory():
    """Verify manifest-to-disk and disk-to-manifest reconciliation, packet counts, and windows."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"][:69]
    assert len(sessions) == 69, f"Expected 69 indexed sessions in Phase 32 baseline, got {len(sessions)}"

    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    val_res = validator.validate_dataset_manifest()
    assert val_res["all_sessions_valid"] is True, f"Validation errors: {val_res}"

    # Disk file audit
    csv_on_disk = sorted([p.name for p in DATASET_DIR.glob("*.csv")])
    json_on_disk = sorted([p.name for p in DATASET_DIR.glob("*.json") if "manifest" not in p.name])

    indexed_csvs = sorted([s["csv_file"] for s in sessions])
    indexed_jsons = sorted([s["json_file"] for s in sessions])

    # 100% manifest-to-disk coverage
    assert set(indexed_csvs).issubset(set(csv_on_disk))
    assert set(indexed_jsons).issubset(set(json_on_disk))

    # Disk-to-manifest: unindexed exploratory session pair
    unindexed_csv = set(csv_on_disk) - set(indexed_csvs)
    unindexed_json = set(json_on_disk) - set(indexed_jsons)
    assert "phase14_p15_real_walk_t1_1792303844_1792303844.csv" in unindexed_csv
    assert "phase14_p15_real_walk_t1_1792303844_1792303844.json" in unindexed_json

    # Frame parity and window count verification
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

        pkts = s["packet_count"]
        total_frames += pkts
        wins_floor = pkts // 50
        total_windows_floor += wins_floor

        # Verify CSIPreprocessor.segment_windows matches floor division exactly
        dummy_data = np.zeros((pkts, 56), dtype=np.float32)
        windows = CSIPreprocessor.segment_windows(dummy_data, window_size=50, stride=50)
        assert len(windows) == wins_floor, f"Session {sid} window mismatch: {len(windows)} vs {wins_floor}"
        total_windows_segmented += len(windows)

    assert total_frames == 9693, f"Expected 9,693 frames, got {total_frames}"
    assert total_windows_floor == 144, f"Expected 144 windows, got {total_windows_floor}"
    assert total_windows_segmented == 144, f"Expected 144 segmented windows, got {total_windows_segmented}"


def test_phase32_subcarrier_and_rate_integrity():
    """Verify raw complex subcarriers preservation, 56-channel alignment, and valid sampling rates."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"][:69]
    raw5_sessions = 0
    raw5_frames = 0
    c56_sessions = 0
    c56_frames = 0
    sampling_rates = []

    for s in sessions:
        jpath = DATASET_DIR / s["json_file"]
        with open(jpath, "r", encoding="utf-8") as f:
            s_data = json.load(f)

        frames = s_data.get("frames", [])
        pkts = len(frames)
        assert pkts == s["packet_count"]

        if len(frames) > 0 and "raw_amplitudes" in frames[0]:
            raw5_sessions += 1
            raw5_frames += pkts
            assert len(frames[0]["raw_amplitudes"]) == 5
            assert len(frames[0]["raw_phases"]) == 5

        if len(frames) > 0 and len(frames[0].get("amplitudes", [])) == 56:
            c56_sessions += 1
            c56_frames += pkts

        ts = [fr["timestamp"] for fr in frames if "timestamp" in fr]
        meta = s_data.get("metadata", {})
        rate_stats = compute_session_sampling_rate(ts, wall_duration_s=meta.get("duration_seconds"))
        assert rate_stats["valid"] is True
        rate = rate_stats["empirical_sampling_rate_hz"]
        assert 30.0 <= rate <= 45.0, f"Session {s['session_id']} rate out of spec: {rate} Hz"
        sampling_rates.append(rate)

    assert raw5_sessions == 46, f"Expected 46 sessions with raw subcarriers, got {raw5_sessions}"
    assert raw5_frames == 6481, f"Expected 6,481 frames with raw subcarriers, got {raw5_frames}"
    assert c56_sessions == 69, f"Expected 69 sessions with 56 channels, got {c56_sessions}"
    assert c56_frames == 9693, f"Expected 9,693 frames with 56 channels, got {c56_frames}"


def test_phase32_cross_room_gap_audit():
    """Audit existing Office_Room2 sessions and confirm the physical data gap for Participant_02."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"][:69]
    office_sessions = [s for s in sessions if s.get("room") == "Office_Room2"]

    # Exactly 5 sessions currently in Office_Room2
    assert len(office_sessions) == 5, f"Expected 5 Office_Room2 sessions, got {len(office_sessions)}"

    # All 5 belong to Participant_01
    office_participants = {s["participant_id"] for s in office_sessions}
    assert office_participants == {"Participant_01"}

    # Participant_02 has zero recordings in Office_Room2
    p02_office = [s for s in office_sessions if s["participant_id"] == "Participant_02"]
    assert len(p02_office) == 0, "Participant_02 should have 0 sessions in Office_Room2 currently."

    # Identify the exact 5-class missing gap
    existing_activities = {s["activity_label"] for s in office_sessions}
    required_activities = {"static", "sit", "walk", "clap", "push_pull"}
    assert existing_activities == required_activities


def test_phase32_split_generator_room_allocation_and_leakage():
    """Verify split generator leakage constraints and quantify room allocation in Phase 32 baseline splits."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    baseline_manifest = dict(manifest, sessions=manifest["sessions"][:69])
    gen = ParticipantIndependentSplitGenerator(baseline_manifest)
    split_res = gen.generate_loso_split(
        test_participant="Participant_02",
        val_participant="Participant_05",
        strict_coverage=False,
    )

    summary = split_res["splits_summary"]
    train_p = set(summary["train_participants"])
    val_p = set(summary["val_participants"])
    test_p = set(summary["test_participants"])

    # Invariant: Disjoint participants
    assert len(train_p & val_p) == 0
    assert len(train_p & test_p) == 0
    assert len(val_p & test_p) == 0

    # Room allocation verification in baseline
    train_rooms = {s.get("room") for s in baseline_manifest["sessions"] if s["participant_id"] in train_p}
    test_rooms = {s.get("room") for s in baseline_manifest["sessions"] if s["participant_id"] in test_p}

    # Office_Room2 in baseline is assigned to Train, 0 windows in Test
    assert "Office_Room2" in train_rooms
    assert "Office_Room2" not in test_rooms


def test_phase32_protocol_readiness_barrier():
    """Verify that both 6-class and cross-room evaluations were properly gated in Phase 32 baseline."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    baseline_manifest = dict(manifest, sessions=manifest["sessions"][:69])
    gen = ParticipantIndependentSplitGenerator(baseline_manifest)

    # 6-class evaluation remains strictly blocked on participants lacking falls
    for p in ["Participant_03", "Participant_04", "Participant_05"]:
        with pytest.raises(InadequateClassCoverageError):
            gen.generate_loso_split(test_participant=p, strict_coverage=True)

    # Cross-room protocol barrier in baseline: cannot evaluate Participant_02 in Office_Room2 without data
    p02_office_windows = sum(
        s["packet_count"] // 50
        for s in baseline_manifest["sessions"]
        if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_02"
    )
    assert p02_office_windows == 0, "Phase 32 baseline evaluation barrier invalidated: unrecorded test data found."
