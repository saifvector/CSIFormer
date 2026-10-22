"""
CSIFormer Phase 26 — Multi-Participant Dataset Expansion & Research Readiness Test Suite.

Verifies:
1. Dataset inventory expansion to 39 sessions, 5,472 frames, and 82 windows (T=50).
2. Multi-participant representation across 5 distinct consenting individuals.
3. Environmental and geometric diversity (10 sessions @ 2.0m across Participant_04 and Participant_05).
4. Physical session data integrity for Participant_05 (100% valid, 0 packet loss, strictly monotonic).
5. Raw (5 subcarriers) vs. derived (56 HT20 channels) feature preservation.
6. Zero participant, event, and window leakage across multi-subject LOSO partitions.
7. Evaluation readiness gate barrier: held-out evaluation strictly blocked on participants lacking fall data.
8. Bit-for-bit invariance of both production and experimental model checkpoints.
"""

import json
import hashlib
from pathlib import Path
import pytest
import numpy as np

from backend.app.services.session_validator import DatasetIntegrityValidator, compute_session_sampling_rate
from backend.app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InadequateClassCoverageError,
    InsufficientParticipantsError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"

PHASE13_CKPT_PATH = PROJECT_ROOT / "models" / "csiformer_phase13_best.pth"
PHASE15_CKPT_PATH = PROJECT_ROOT / "models" / "csiformer_phase15_adapted.pth"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"

PHASE26_P05_SESSIONS = [
    ("phase16_real_static_Participant_05_1792390995_1792390995", "static", 137),
    ("phase16_real_sit_Participant_05_1792391028_1792391028", "sit", 138),
    ("phase16_real_walk_Participant_05_1792391056_1792391056", "walk", 141),
    ("phase16_real_clap_Participant_05_1792391082_1792391082", "clap", 135),
    ("phase16_real_push_pull_Participant_05_1792391109_1792391109", "push_pull", 144),
]


def test_phase26_checkpoint_protection():
    """Verify both production and experimental checkpoints are bit-for-bit unchanged."""
    assert PHASE13_CKPT_PATH.exists(), f"Missing production checkpoint: {PHASE13_CKPT_PATH}"
    assert PHASE15_CKPT_PATH.exists(), f"Missing experimental checkpoint: {PHASE15_CKPT_PATH}"

    p13_hash = hashlib.md5(PHASE13_CKPT_PATH.read_bytes()).hexdigest()
    p15_hash = hashlib.md5(PHASE15_CKPT_PATH.read_bytes()).hexdigest()

    assert p13_hash == EXPECTED_PHASE13_MD5, f"Phase 13 checkpoint modified: {p13_hash}"
    assert p15_hash == EXPECTED_PHASE15_MD5, f"Phase 15 checkpoint modified: {p15_hash}"


def test_phase26_dataset_inventory_and_expansion():
    """Verify manifest inventory expands to 39 sessions, 5,472 frames, 82 windows, and 5 participants."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] >= 39
    assert res["total_packets"] >= 5472
    assert res["total_windows"] >= 82
    assert set(res["distinct_participants"]).issuperset({
        "Participant_01",
        "Participant_02",
        "Participant_03",
        "Participant_04",
        "Participant_05",
    })
    assert res["distinct_events"] >= 39

    # Verify activity window breakdown
    expected_windows = {"walk": 17, "fall": 8, "sit": 17, "clap": 14, "push_pull": 15, "static": 11}
    for act, exp_wins in expected_windows.items():
        assert res["activity_windows"].get(act, 0) >= exp_wins, f"Mismatch in {act} windows"


def test_phase26_participant_05_session_integrity():
    """Verify each Participant_05 session file, frame count, timing, and CSV mirror."""
    validator = DatasetIntegrityValidator(DATASET_DIR)

    for sid, act, expected_n in PHASE26_P05_SESSIONS:
        json_path = DATASET_DIR / f"{sid}.json"
        csv_path = DATASET_DIR / f"{sid}.csv"

        assert json_path.exists(), f"Missing JSON: {json_path}"
        assert csv_path.exists(), f"Missing CSV mirror: {csv_path}"

        val_res = validator.validate_session_file(json_path)
        assert val_res["valid"] is True
        assert val_res["packet_count"] == expected_n
        assert val_res["dropped_packets"] == 0
        assert val_res["loss_rate"] == 0.0
        assert val_res["room"] == "Laboratory"
        assert val_res["tx_rx_distance_m"] == 2.0
        assert val_res["has_raw_subcarriers"] is True

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data["metadata"]
        frames = data["frames"]

        assert meta["participant_id"] == "Participant_05"
        assert meta["ground_truth_activity"] == act
        assert meta["ground_truth_confirmed"] is True
        assert meta["tx_rx_distance_meters"] == 2.0
        assert meta["room_type"] == "Laboratory"
        assert meta["packets_lost"] == 0
        assert meta["loss_rate"] == 0.0

        # Timing and rate
        ts = [fr["timestamp"] for fr in frames]
        rate_info = compute_session_sampling_rate(ts, meta.get("duration_seconds"))
        assert rate_info["is_strictly_monotonic"] is True
        assert rate_info["has_duplicates"] is False
        assert rate_info["empirical_sampling_rate_hz"] >= 30.0

        # CSV row match
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_lines = [line.strip() for line in f if line.strip()]
        # header + expected_n data rows
        assert len(csv_lines) == expected_n + 1


def test_phase26_raw_vs_derived_subcarriers():
    """Verify that all Phase 26 recordings preserve 5 raw physical subcarriers alongside 56 derived channels."""
    for sid, act, _ in PHASE26_P05_SESSIONS:
        json_path = DATASET_DIR / f"{sid}.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for frame in data["frames"]:
            raw_amps = frame.get("raw_amplitudes", [])
            raw_phases = frame.get("raw_phases", [])
            aligned_amps = frame.get("amplitudes", [])
            aligned_phases = frame.get("phases", [])

            assert len(raw_amps) == 5, f"Raw subcarrier amplitude count mismatch: {len(raw_amps)}"
            assert len(raw_phases) == 5, f"Raw subcarrier phase count mismatch: {len(raw_phases)}"
            assert len(aligned_amps) == 56, f"Aligned channel count mismatch: {len(aligned_amps)}"
            assert len(aligned_phases) == 56, f"Aligned phase count mismatch: {len(aligned_phases)}"


def test_phase26_environmental_diversity():
    """Verify that the dataset contains substantial geometric distance variation (2.0m vs 2.5m)."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest["sessions"]
    distance_counts = {}
    for s in sessions:
        d = s.get("distance_meters") or s.get("tx_rx_distance_m")
        distance_counts[d] = distance_counts.get(d, 0) + 1

    assert 2.0 in distance_counts, "Distance 2.0m not found in dataset"
    assert 2.5 in distance_counts, "Distance 2.5m not found in dataset"
    assert distance_counts[2.0] >= 10, f"Expected at least 10 sessions at 2.0m, got {distance_counts[2.0]}"
    assert distance_counts[2.5] >= 29, f"Expected at least 29 sessions at 2.5m, got {distance_counts[2.5]}"


def test_phase26_multi_participant_loso_zero_leakage():
    """Verify multi-participant Leave-One-Subject-Out partitioning with 5 participants."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)

    # 3-way split: Train: P1, P3, P4; Val: P5; Test: P2
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

    assert summary["train_windows"] >= 48
    assert summary["val_windows"] >= 10
    assert summary["test_windows"] >= 24
    assert summary["train_windows"] + summary["val_windows"] + summary["test_windows"] >= 82


def test_phase26_evaluation_readiness_barrier():
    """Verify that strict model evaluation on Participant_05 is blocked due to missing fall class."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    with pytest.raises(InadequateClassCoverageError) as exc_info:
        gen.generate_loso_split(test_participant="Participant_05", strict_coverage=True)
    assert "Missing critical activity" in str(exc_info.value) or "lacks" in str(exc_info.value).lower()
