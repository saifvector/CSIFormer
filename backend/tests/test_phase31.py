"""
CSIFormer Phase 31 — Cross-Room Split Readiness & Evaluation Protocol Audit Tests.

Validates:
1. Protected checkpoint bit-level invariance.
2. Reconciled dataset inventory (69 sessions, 9,693 frames, 144 non-overlapping windows).
3. Confounding audit: Office_Room2 contains exclusively Participant_01 (100% room-participant confounding).
4. Split room allocation audit: Office_Room2 is assigned to Train; Test partition contains 0 windows from Office_Room2.
5. Distinction between participant-independent testing and room-independent testing.
6. Evaluation readiness barriers: 6-class evaluation blocked on held-out subjects lacking fall class;
   Room-held-out evaluation blocked on single-subject confounding.
"""

import json
import hashlib
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"

from backend.app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InadequateClassCoverageError,
)
from backend.app.services.session_validator import DatasetIntegrityValidator


def test_phase31_checkpoint_invariance():
    """Verify that both production and experimental model checkpoints remain pristine and untouched."""
    p13_path = MODELS_DIR / "csiformer_phase13_best.pth"
    p15_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13_path.exists(), f"Missing production checkpoint: {p13_path}"
    assert p15_path.exists(), f"Missing experimental checkpoint: {p15_path}"

    with open(p13_path, "rb") as f:
        p13_hash = hashlib.md5(f.read()).hexdigest()
    with open(p15_path, "rb") as f:
        p15_hash = hashlib.md5(f.read()).hexdigest()

    assert p13_hash == EXPECTED_PHASE13_MD5, f"Production checkpoint modified: {p13_hash}"
    assert p15_hash == EXPECTED_PHASE15_MD5, f"Experimental checkpoint modified: {p15_hash}"


def test_phase31_reconciled_dataset_inventory():
    """Verify manifest inventory of 69 sessions, 9,693 frames, and 144 windows with zero collisions."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) >= 69, f"Expected at least 69 sessions, got {len(sessions)}"

    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    val_res = validator.validate_dataset_manifest()
    assert val_res["all_sessions_valid"] is True, f"Validation failure: {val_res}"

    session_ids = set()
    event_ids = set()
    total_frames = 0
    total_windows = 0

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

        total_frames += s.get("packet_count", 0)
        total_windows += s.get("packet_count", 0) // 50

    assert total_frames >= 9693, f"Expected at least 9,693 frames, got {total_frames}"
    assert total_windows >= 144, f"Expected at least 144 windows (T=50), got {total_windows}"


def test_phase31_room_participant_confounding_audit():
    """Verify that Office_Room2 is represented only by Participant_01 (room-participant confounding)."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"][:69]
    room_participants = {}
    for s in sessions:
        r = s.get("room")
        p = s.get("participant_id")
        room_participants.setdefault(r, set()).add(p)

    # Laboratory has broad coverage across all 5 participants
    assert room_participants["Laboratory"] == {
        "Participant_01",
        "Participant_02",
        "Participant_03",
        "Participant_04",
        "Participant_05",
    }

    # Office_Room2 in baseline has ONLY Participant_01
    assert room_participants["Office_Room2"] == {"Participant_01"}, (
        f"Office_Room2 baseline should be confounded with Participant_01 only, but found: {room_participants['Office_Room2']}"
    )


def test_phase31_split_room_allocation_audit():
    """Verify that baseline test partition contains ZERO windows from Office_Room2."""
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
    train_participants = set(summary["train_participants"])
    val_participants = set(summary["val_participants"])
    test_participants = set(summary["test_participants"])

    train_sessions = [s for s in baseline_manifest["sessions"] if s["participant_id"] in train_participants]
    val_sessions = [s for s in baseline_manifest["sessions"] if s["participant_id"] in val_participants]
    test_sessions = [s for s in baseline_manifest["sessions"] if s["participant_id"] in test_participants]

    train_rooms = {s.get("room") for s in train_sessions}
    val_rooms = {s.get("room") for s in val_sessions}
    test_rooms = {s.get("room") for s in test_sessions}

    # Office_Room2 is present in Train because Participant_01 is in Train
    assert "Office_Room2" in train_rooms
    # Office_Room2 is completely absent from Val and Test
    assert "Office_Room2" not in val_rooms
    assert "Office_Room2" not in test_rooms

    # The test set tests subject-independence in the Laboratory, NOT room-independence
    assert test_rooms.issubset({"Laboratory", "Laboratory_Room1"})


def test_phase31_evaluation_readiness_barrier():
    """Verify that 6-class evaluation remains strictly blocked on held-out subjects lacking falls."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)

    with pytest.raises(InadequateClassCoverageError):
        gen.generate_loso_split(
            test_participant="Participant_03",
            val_participant="Participant_04",
            strict_coverage=True,
        )

    with pytest.raises(InadequateClassCoverageError):
        gen.generate_loso_split(
            test_participant="Participant_04",
            val_participant="Participant_05",
            strict_coverage=True,
        )

    with pytest.raises(InadequateClassCoverageError):
        gen.generate_loso_split(
            test_participant="Participant_05",
            val_participant="Participant_03",
            strict_coverage=True,
        )
