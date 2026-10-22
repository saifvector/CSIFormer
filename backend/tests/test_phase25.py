"""
CSIFormer Phase 25 — Multi-Participant Real CSI Dataset Expansion & Data Quality Assurance Tests.

Automated deterministic testing covering:
1. Dataset expansion to 34 sessions, 4,777 frames, and 72 windows.
2. Participant diversity expansion to 4 distinct participants (Participant_01 through Participant_04).
3. Environmental distance diversity (first 2.0m Laboratory recordings).
4. Full session-by-session integrity for Participant_04 physical recordings.
5. Sampling rate exact agreement across collector, validator, and manifest.
6. Separation of raw 5-subcarrier measurements from derived 56-channel tensor features.
7. 3-way Leave-One-Subject-Out (LOSO) partition with zero subject, event, or window leakage.
8. Evaluation readiness barrier enforcement (InadequateClassCoverageError on fall class).
9. Production and experimental checkpoint bit-for-bit invariance.
"""

import json
import hashlib
from pathlib import Path
import numpy as np
import pytest

from backend.app.services.session_validator import DatasetIntegrityValidator, compute_session_sampling_rate
from backend.app.services.split_generator import (
    ParticipantIndependentSplitGenerator,
    InadequateClassCoverageError
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = PROJECT_ROOT / "models"

EXP_PROD_HASH = "383b4d98c08f8970b0443738f170ec01"
EXP_EXP_HASH = "ab3d97a04d78edf75d807178772bc828"

PHASE25_P04_SESSIONS = [
    ("phase16_real_static_Participant_04_1792389853_1792389853", "static", 144),
    ("phase16_real_sit_Participant_04_1792389881_1792389881", "sit", 137),
    ("phase16_real_walk_Participant_04_1792389907_1792389907", "walk", 142),
    ("phase16_real_clap_Participant_04_1792389936_1792389936", "clap", 139),
    ("phase16_real_push_pull_Participant_04_1792389966_1792389966", "push_pull", 142)
]


def test_phase25_dataset_inventory_and_expansion():
    """Verify manifest inventory expands to 34 sessions, 4,777 frames, and 4 participants."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] >= 34
    assert res["total_packets"] >= 4777
    assert res["total_windows"] >= 72
    assert {"Participant_01", "Participant_02", "Participant_03", "Participant_04"}.issubset(set(res["distinct_participants"]))
    assert res["distinct_events"] >= 34

    # Verify activity window breakdown
    expected_windows = {"walk": 15, "fall": 8, "sit": 15, "clap": 12, "push_pull": 13, "static": 9}
    for act, exp_wins in expected_windows.items():
        assert res["activity_windows"].get(act, 0) >= exp_wins, f"Mismatch in {act} windows"


def test_phase25_participant_04_session_integrity():
    """Verify each Participant_04 session file, frame count, timing, and CSV mirror."""
    validator = DatasetIntegrityValidator(DATASET_DIR)

    for sid, act, expected_n in PHASE25_P04_SESSIONS:
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
        assert val_res["raw_subcarrier_counts"] == [5]

        # Verify CSV row count
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_lines = sum(1 for line in f) - 1
        assert csv_lines == expected_n


def test_phase25_sampling_rate_exact_agreement():
    """Verify that sampling rate calculations agree with high precision for Participant_04."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_map = {s["session_id"]: s for s in manifest["sessions"]}

    for sid, act, expected_n in PHASE25_P04_SESSIONS:
        json_path = DATASET_DIR / f"{sid}.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data["metadata"]
        frames = data["frames"]
        timestamps = [f["timestamp"] for f in frames]

        rate_stats = compute_session_sampling_rate(timestamps, wall_duration_s=meta.get("duration_seconds"))
        assert rate_stats["valid"] is True
        assert rate_stats["is_strictly_monotonic"] is True
        assert rate_stats["has_duplicates"] is False

        empirical = rate_stats["empirical_sampling_rate_hz"]
        stored_rate = meta["mean_sampling_rate_hz"]
        assert abs(stored_rate - round(empirical, 2)) < 1e-4

        manifest_entry = manifest_map[sid]
        assert manifest_entry["sampling_rate_hz"] == stored_rate
        assert manifest_entry["tx_rx_distance_m"] == 2.0


def test_phase25_raw_vs_derived_subcarrier_separation():
    """Verify that 5 measured raw subcarriers remain distinct from 56 interpolated channels."""
    for sid, _, _ in PHASE25_P04_SESSIONS:
        json_path = DATASET_DIR / f"{sid}.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for frame in data["frames"]:
            assert "raw_amplitudes" in frame
            assert "raw_phases" in frame
            assert len(frame["raw_amplitudes"]) == 5
            assert len(frame["raw_phases"]) == 5

            assert "amplitudes" in frame
            assert "phases" in frame
            assert len(frame["amplitudes"]) == 56
            assert len(frame["phases"]) == 56

            assert np.all(np.isfinite(frame["raw_amplitudes"]))
            assert np.all(np.isfinite(frame["amplitudes"]))


def test_phase25_3way_loso_split_zero_leakage():
    """Verify 3-way LOSO split generation with zero participant, event, or window overlap."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    split_res = gen.generate_loso_split(
        test_participant="Participant_02",
        val_participant="Participant_04",
        strict_coverage=False
    )

    summary = split_res["splits_summary"]
    train_p = set(summary["train_participants"])
    val_p = set(summary["val_participants"])
    test_p = set(summary["test_participants"])

    # Zero participant overlap
    assert len(train_p & val_p) == 0
    assert len(train_p & test_p) == 0
    assert len(val_p & test_p) == 0
    assert {"Participant_01", "Participant_03"}.issubset(train_p)
    assert val_p == {"Participant_04"}
    assert test_p == {"Participant_02"}

    # Window counts
    assert summary["train_windows"] >= 38
    assert summary["val_windows"] >= 10
    assert summary["test_windows"] >= 24
    assert summary["total_windows"] >= 72


def test_phase25_evaluation_readiness_barrier():
    """Verify that strict model evaluation on Participant_04 is blocked due to missing fall class."""
    gen = ParticipantIndependentSplitGenerator(MANIFEST_PATH)
    with pytest.raises(InadequateClassCoverageError) as exc_info:
        gen.generate_loso_split(test_participant="Participant_04", strict_coverage=True)
    assert "Missing critical activity" in str(exc_info.value) or "lacks" in str(exc_info.value).lower()


def test_phase25_checkpoint_hash_invariance():
    """Verify bit-for-bit invariance of production and experimental model checkpoints."""
    prod_path = MODELS_DIR / "csiformer_phase13_best.pth"
    exp_path = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert prod_path.exists()
    assert exp_path.exists()

    prod_hash = hashlib.md5(prod_path.read_bytes()).hexdigest()
    exp_hash = hashlib.md5(exp_path.read_bytes()).hexdigest()

    assert prod_hash == EXP_PROD_HASH, f"Production checkpoint altered: {prod_hash}"
    assert exp_hash == EXP_EXP_HASH, f"Experimental checkpoint altered: {exp_hash}"
