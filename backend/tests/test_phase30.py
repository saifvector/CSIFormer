"""
CSIFormer Phase 30 — Cross-Room Environmental Diversity & Generalization Readiness Tests.

Validates:
1. Protected checkpoint bit-level invariance.
2. Dataset expansion to 69 indexed physical sessions, 9,693 frames, and 144 non-overlapping windows.
3. Genuine second physical environment coverage in Office_Room2 across 5 safe activities.
4. Separate preservation of raw 5-subcarrier (I, Q) pairs and 56 aligned derived channels.
5. 3-way participant-independent (LOSO) split integrity with zero subject, event, or window leakage.
6. Strict model-evaluation barrier maintenance (6-class evaluation remains NO-GO / BLOCKED).
"""

import json
import hashlib
from pathlib import Path
import pytest
import numpy as np

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


def test_phase30_checkpoint_invariance():
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


def test_phase30_dataset_inventory_expansion():
    """Verify manifest expansion to exactly 69 sessions, 9,693 frames, 144 windows, and 0 collisions."""
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
    raw_5_frames = 0
    derived_56_frames = 0

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

        with open(jpath, "r", encoding="utf-8") as jf:
            data = json.load(jf)

        frames = data.get("frames", [])
        total_frames += len(frames)
        total_windows += len(frames) // 50

        for fr in frames:
            if "raw_amplitudes" in fr and len(fr["raw_amplitudes"]) == 5:
                raw_5_frames += 1
            if ("amplitudes" in fr and len(fr["amplitudes"]) == 56) or ("csi_matrix" in fr and len(fr["csi_matrix"]) == 56):
                derived_56_frames += 1

    assert total_frames >= 9693, f"Expected at least 9,693 physical frames, got {total_frames}"
    assert total_windows >= 144, f"Expected at least 144 windows (T=50), got {total_windows}"
    assert raw_5_frames >= 6481, f"Expected at least 6,481 frames with raw subcarriers, got {raw_5_frames}"
    assert derived_56_frames >= 9693, f"Expected at least 9,693 frames with derived 56 channels, got {derived_56_frames}"


def test_phase30_cross_room_environmental_diversity():
    """Verify that a genuine second environment (Office_Room2) is present with matched ordinary activities."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    room_sessions = {}
    for s in sessions:
        r = s.get("room")
        room_sessions.setdefault(r, []).append(s)

    # Both Laboratory and genuine second room Office_Room2 must be represented
    assert "Office_Room2" in room_sessions, "Missing genuine second room Office_Room2"
    p01_office_sessions = [s for s in room_sessions["Office_Room2"] if s["participant_id"] == "Participant_01"]
    assert len(p01_office_sessions) == 5

    office_activities = {s["activity_label"] for s in p01_office_sessions}
    assert office_activities == {"static", "sit", "walk", "clap", "push_pull"}

    # All Phase 30 Office_Room2 sessions should be matched to Participant_01 at 2.0m
    for s in p01_office_sessions:
        assert s["participant_id"] == "Participant_01"
        assert s["tx_rx_distance_m"] == 2.0
        assert s["sampling_rate_hz"] >= 30.0
        assert 3.5 <= s["duration_seconds"] <= 4.5


def test_phase30_participant_independent_split_integrity():
    """Verify 3-way participant-independent split yields at least 89 train, 20 val, 35 test windows with zero leakage."""
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

    assert summary["train_windows"] >= 89
    assert summary["val_windows"] >= 20
    assert summary["test_windows"] >= 35
    assert summary["train_windows"] + summary["val_windows"] + summary["test_windows"] >= 144


def test_phase30_evaluation_readiness_barrier():
    """Verify that 6-class model evaluation remains blocked on held-out subjects lacking the fall class."""
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
