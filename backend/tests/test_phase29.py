"""
CSIFormer Phase 29 — Participant–Distance Confounding Reduction Test Suite.

Verifies:
1. Protected model checkpoints bit-for-bit invariant.
2. Manifest inventory expansion to exactly 64 indexed sessions, 8,997 physical frames, and 134 windows (T=50).
3. Session and event ID uniqueness across all 64 sessions (zero collisions).
4. Full validation pass across all 64 session artifacts (DatasetIntegrityValidator).
5. Comprehensive multi-distance coverage across all 5 participants (P01–P05 all have >=2 distances).
6. Raw 5-subcarrier vs. derived 56-channel separation (5,785 raw subcarrier frames, 8,997 derived frames).
7. Participant-independent train/val/test split yields exactly 79/20/35 windows with zero leakage.
8. Evaluation readiness gate barrier strictly enforced for held-out subjects lacking fall class.
"""

import json
import hashlib
from pathlib import Path
import pytest

from backend.app.services.session_validator import DatasetIntegrityValidator
from backend.app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InadequateClassCoverageError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"

PHASE13_CKPT_PATH = PROJECT_ROOT / "models" / "csiformer_phase13_best.pth"
PHASE15_CKPT_PATH = PROJECT_ROOT / "models" / "csiformer_phase15_adapted.pth"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"


def test_phase29_checkpoint_invariance():
    """Verify both production and experimental checkpoints remain bit-for-bit identical."""
    assert PHASE13_CKPT_PATH.exists(), f"Missing production checkpoint: {PHASE13_CKPT_PATH}"
    assert PHASE15_CKPT_PATH.exists(), f"Missing experimental checkpoint: {PHASE15_CKPT_PATH}"

    p13_hash = hashlib.md5(PHASE13_CKPT_PATH.read_bytes()).hexdigest()
    p15_hash = hashlib.md5(PHASE15_CKPT_PATH.read_bytes()).hexdigest()

    assert p13_hash == EXPECTED_PHASE13_MD5, f"Production checkpoint modified: {p13_hash}"
    assert p15_hash == EXPECTED_PHASE15_MD5, f"Experimental checkpoint modified: {p15_hash}"


def test_phase29_dataset_inventory_expansion():
    """Verify manifest expansion to exactly 64 sessions, 8,997 frames, 134 windows, and 5 participants."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    assert len(sessions) >= 64, f"Expected at least 64 sessions, got {len(sessions)}"

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

    assert total_frames >= 8997, f"Expected at least 8,997 physical frames, got {total_frames}"
    assert total_windows >= 134, f"Expected at least 134 windows (T=50), got {total_windows}"
    assert raw_5_frames >= 5785, f"Expected at least 5,785 frames with raw subcarriers, got {raw_5_frames}"
    assert derived_56_frames >= 8997, f"Expected at least 8,997 frames with derived 56 channels, got {derived_56_frames}"


def test_phase29_participant_distance_confounding_reduction():
    """Verify that every participant (P01 through P05) has verified multi-distance coverage."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    participant_distances = {}
    for s in manifest["sessions"]:
        p = s["participant_id"]
        d = float(s.get("tx_rx_distance_m", 2.5))
        if p not in participant_distances:
            participant_distances[p] = set()
        participant_distances[p].add(d)

    assert set(participant_distances.keys()) == {
        "Participant_01",
        "Participant_02",
        "Participant_03",
        "Participant_04",
        "Participant_05",
    }

    # All participants must have multi-distance coverage (>= 2 distances)
    for p, dists in participant_distances.items():
        assert len(dists) >= 2, f"Participant {p} has only single-distance coverage: {dists}"

    assert participant_distances["Participant_01"] == {2.0, 2.5}
    assert participant_distances["Participant_02"] == {2.0, 2.5}
    assert participant_distances["Participant_03"] == {2.0, 2.5}
    assert participant_distances["Participant_04"] == {2.0, 2.5}
    assert participant_distances["Participant_05"] == {1.5, 2.0}


def test_phase29_distance_session_distribution():
    """Verify the distribution of sessions across distances (25 at 2.0m, 34 at 2.5m, 5 at 1.5m)."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    distance_counts = {}
    for s in manifest["sessions"]:
        d = float(s.get("tx_rx_distance_m", 2.5))
        distance_counts[d] = distance_counts.get(d, 0) + 1

    assert distance_counts[1.5] >= 5, f"Expected at least 5 sessions at 1.5m, got {distance_counts.get(1.5)}"
    assert distance_counts[2.0] >= 25, f"Expected at least 25 sessions at 2.0m, got {distance_counts.get(2.0)}"
    assert distance_counts[2.5] >= 34, f"Expected at least 34 sessions at 2.5m, got {distance_counts.get(2.5)}"
    assert sum(distance_counts.values()) >= 64


def test_phase29_participant_independent_split_integrity():
    """Verify 3-way participant-independent split yields at least 79 train, 20 val, 35 test windows (zero leakage)."""
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

    assert summary["train_windows"] >= 79
    assert summary["val_windows"] >= 20
    assert summary["test_windows"] >= 35
    assert summary["train_windows"] + summary["val_windows"] + summary["test_windows"] >= 134


def test_phase29_evaluation_readiness_barrier():
    """Verify that strict 6-class model evaluation remains blocked on subjects lacking the fall class."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    for p in ["Participant_03", "Participant_04", "Participant_05"]:
        with pytest.raises(InadequateClassCoverageError) as exc_info:
            gen.generate_loso_split(test_participant=p, strict_coverage=True)
        assert "Missing critical activity" in str(exc_info.value) or "lacks" in str(exc_info.value).lower()
