"""
CSIFormer Phase 34 — Independent Cross-Room Split Audit & Evaluation Gate Tests.

Validates:
1. Protected checkpoint bit-level invariance (MD5 verification without model loading).
2. Independent verification of Phase 33 physical recordings on disk and manifest.
3. Audit of collection-time splits vs. LOSO split generator (Participant_01 Office_Room2 in train).
4. Strict five-class room-held-out and participant-held-out partition invariants:
   - Zero Office_Room2 sessions in train or val.
   - Zero Participant_02 sessions in train or val.
   - Test partition contains ONLY Participant_02's Office_Room2 recordings (5 sessions, 11 windows).
   - All 5 safe ordinary classes represented in train, val, and test.
   - Falls strictly excluded from 5-class evaluation protocol.
   - Zero session, event, or window leakage across partitions.
   - Complete 155-window accounting: 75 train + 20 val + 11 test + 49 excluded.
5. Determinism, immutability, and side-effect safety of split generation.
6. Strict failure on insufficient class coverage (no silent data fabrication).
"""

import json
import hashlib
import sys
import copy
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
    InsufficientParticipantsError,
)
from backend.app.services.session_validator import (
    DatasetIntegrityValidator,
    compute_session_sampling_rate,
)
from backend.app.services.csi_preprocessor import CSIPreprocessor


def test_phase34_checkpoint_invariance():
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


def test_phase34_phase33_physical_data_verification():
    """Independently inspect the 5 new Phase 33 recordings on disk and verify complete data integrity."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    p02_office = [
        s for s in sessions
        if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_02"
    ]
    assert len(p02_office) == 5, f"Expected 5 Phase 33 sessions, found {len(p02_office)}"

    expected_activities = {"static", "sit", "walk", "clap", "push_pull"}
    found_activities = set()

    for s in p02_office:
        act = s["activity_label"]
        found_activities.add(act)
        assert s["tx_rx_distance_m"] == 2.0
        assert s["split"] == "test"
        assert s["confirmation_status"] == "confirmed"

        jpath = DATASET_DIR / s["json_file"]
        cpath = DATASET_DIR / s["csv_file"]
        assert jpath.exists(), f"Missing JSON: {jpath}"
        assert cpath.exists(), f"Missing CSV: {cpath}"

        with open(jpath, "r", encoding="utf-8") as jf:
            jdata = json.load(jf)

        frames = jdata.get("frames", [])
        assert len(frames) == s["packet_count"]
        assert 135 <= len(frames) <= 155

        # Raw subcarriers (5 complex pairs)
        assert len(frames[0]["raw_amplitudes"]) == 5
        assert len(frames[0]["raw_phases"]) == 5

        # Derived channels (56 aligned)
        assert len(frames[0]["amplitudes"]) == 56
        assert len(frames[0]["phases"]) == 56

        # CSV parity
        csv_rows = cpath.read_text(encoding="utf-8").strip().split("\n")
        assert len(csv_rows) - 1 == len(frames)

        # Monotonicity and empirical rate
        timestamps = [fr["timestamp"] for fr in frames if "timestamp" in fr]
        assert len(timestamps) == len(frames)
        assert all(t2 > t1 for t1, t2 in zip(timestamps[:-1], timestamps[1:])), "Timestamps non-monotonic"

        rate_stats = compute_session_sampling_rate(timestamps, wall_duration_s=s["duration_seconds"])
        assert rate_stats["valid"] is True
        assert 34.0 <= rate_stats["empirical_sampling_rate_hz"] <= 38.0

    assert found_activities == expected_activities


def test_phase34_manifest_split_audit_and_unseen_room_caveat():
    """Verify that in the raw manifest, Participant_01's Office_Room2 sessions are assigned to train."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    p01_office = [
        s for s in sessions
        if s.get("room") == "Office_Room2" and s.get("participant_id") == "Participant_01"
    ]
    assert len(p01_office) == 5

    # Confirm Participant_01's Office_Room2 sessions are labelled 'train' in real manifest
    for s in p01_office:
        assert s["split"] == "train", f"Expected Participant_01 Office_Room2 split to be train, got {s['split']}"

    # Scientific requirement: A naive split that leaves Participant_01 in train CANNOT be called 'unseen room'
    gen = ParticipantIndependentSplitGenerator(manifest)
    naive_loso = gen.generate_loso_split(test_participant="Participant_02", val_participant="Participant_05")
    train_rooms_naive = {s["room"] for s in naive_loso["sessions"] if s["split"] == "train"}
    assert "Office_Room2" in train_rooms_naive, (
        "In naive LOSO, Office_Room2 is included in training via Participant_01, "
        "precluding the label 'unseen room'."
    )


def test_phase34_strict_cross_room_split_invariants():
    """Verify all 8 invariants of the strict room-held-out and subject-held-out five-class partition."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    split_res = gen.generate_strict_cross_room_split(
        test_room="Office_Room2",
        test_participant="Participant_02",
        val_participant="Participant_05",
        train_participants=["Participant_01", "Participant_03", "Participant_04"],
        classes=["static", "sit", "walk", "clap", "push_pull"]
    )

    summary = split_res["splits_summary"]
    sessions = split_res["sessions"]

    # Invariant 1: Training contains NO sessions from Office_Room2
    train_sessions = [s for s in sessions if s["split"] == "train"]
    train_rooms = {s.get("room") for s in train_sessions}
    assert "Office_Room2" not in train_rooms
    assert train_rooms == {"Laboratory", "Laboratory_Room1"}

    # Invariant 2: Validation contains NO sessions from Office_Room2
    val_sessions = [s for s in sessions if s["split"] == "val"]
    val_rooms = {s.get("room") for s in val_sessions}
    assert "Office_Room2" not in val_rooms
    assert val_rooms == {"Laboratory"}

    # Invariant 3: Test contains ONLY Participant_02 sessions in Office_Room2
    test_sessions = [s for s in sessions if s["split"] == "test"]
    assert len(test_sessions) == 5
    for s in test_sessions:
        assert s["participant_id"] == "Participant_02"
        assert s["room"] == "Office_Room2"

    # Invariant 4: Participant_02 has NO sessions in training or validation
    assert all(s["participant_id"] != "Participant_02" for s in train_sessions)
    assert all(s["participant_id"] != "Participant_02" for s in val_sessions)

    # Invariant 5: Zero session, event, or overlapping window leakage
    train_sids = {s["session_id"] for s in train_sessions}
    val_sids = {s["session_id"] for s in val_sessions}
    test_sids = {s["session_id"] for s in test_sessions}
    train_eids = {s.get("event_id") or s["session_id"] for s in train_sessions}
    val_eids = {s.get("event_id") or s["session_id"] for s in val_sessions}
    test_eids = {s.get("event_id") or s["session_id"] for s in test_sessions}

    assert len(train_sids & val_sids) == 0
    assert len(train_sids & test_sids) == 0
    assert len(val_sids & test_sids) == 0
    assert len(train_eids & val_eids) == 0
    assert len(train_eids & test_eids) == 0
    assert len(val_eids & test_eids) == 0

    # Invariant 6: All five safe ordinary activity classes represented in test
    expected_classes = {"static", "sit", "walk", "clap", "push_pull"}
    test_classes = {s["activity_label"] for s in test_sessions}
    train_classes = {s["activity_label"] for s in train_sessions}
    val_classes = {s["activity_label"] for s in val_sessions}

    assert test_classes == expected_classes
    assert train_classes == expected_classes
    assert val_classes == expected_classes

    # Invariant 7: Window counts and exact accounting
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

    # Check window counts using floor division
    assert sum(s["packet_count"] // 50 for s in train_sessions) == 75
    assert sum(s["packet_count"] // 50 for s in val_sessions) == 20
    assert sum(s["packet_count"] // 50 for s in test_sessions) == 11

    # Invariant 8: Fall detection is 100% excluded
    active_sessions = train_sessions + val_sessions + test_sessions
    assert all(s["activity_label"] != "fall" for s in active_sessions)


def test_phase34_split_generator_determinism_and_immutability(tmp_path):
    """Verify split generation is deterministic, does not mutate input, and only writes when requested."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        original_manifest_text = f.read()
    original_manifest_dict = json.loads(original_manifest_text)

    gen = ParticipantIndependentSplitGenerator(original_manifest_dict)

    # In-memory generation without output_manifest_path
    split1 = gen.generate_strict_cross_room_split()
    split2 = gen.generate_strict_cross_room_split()

    assert split1 == split2, "Split generation must be strictly deterministic."

    # Verify input dict was not mutated
    assert gen.manifest == original_manifest_dict

    # Verify real manifest on disk was not modified
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        current_manifest_text = f.read()
    assert current_manifest_text == original_manifest_text, "Manifest on disk must not be modified by in-memory split generation."

    # Test file output using temporary fixture
    out_file = tmp_path / "strict_cross_room_manifest.json"
    written_manifest = gen.generate_strict_cross_room_split(output_manifest_path=out_file)
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        loaded_written = json.load(f)
    assert loaded_written == written_manifest


def test_phase34_insufficient_class_coverage_enforcement():
    """Verify that InadequateClassCoverageError is raised if a partition lacks required classes."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Filter out 'clap' from manifest to simulate missing class
    tampered_sessions = [s for s in manifest["sessions"] if s.get("activity_label") != "clap"]
    tampered_manifest = dict(manifest, sessions=tampered_sessions)

    gen = ParticipantIndependentSplitGenerator(tampered_manifest)

    # Should raise InadequateClassCoverageError because 'clap' is missing
    with pytest.raises(InadequateClassCoverageError) as exc_info:
        gen.generate_strict_cross_room_split(classes=["static", "sit", "walk", "clap", "push_pull"])
    assert "clap" in str(exc_info.value)
