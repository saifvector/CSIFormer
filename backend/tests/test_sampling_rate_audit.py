"""
CSIFormer Phase 24 — Deterministic Unit Tests for Sampling-Rate Audit & Metrics.

Validates the standardized sampling rate formula:
    f_empirical = (N - 1) / (t_{N-1} - t_0) == 1 / mean(dt)

Covers:
1. Regularly spaced intervals (exact rate matching).
2. Single-frame and empty sessions (insufficient frames).
3. Duplicate and non-monotonic timestamps (clock reversals).
4. Irregular intervals (jitter, varying dt).
5. Non-finite values (NaN, Inf).
6. Real physical walking session recalculation & reconciliation.
7. DatasetIntegrityValidator integration with sampling rate metrics.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from backend.app.services.session_validator import (
    compute_session_sampling_rate,
    DatasetIntegrityValidator,
    SessionValidationError
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "data" / "real_csi_dataset"
AUDITED_SESSION_FILE = DATASET_DIR / "phase16_real_walk_Participant_03_1792339078_1792339078.json"


def test_sampling_rate_regular_intervals():
    """Verify regular intervals yield exact expected rate."""
    # 40 Hz: 101 timestamps, dt = 0.025s, span = 2.5s -> (101 - 1) / 2.5 = 40.0 Hz
    ts_40 = [1000.0 + i * 0.025 for i in range(101)]
    res_40 = compute_session_sampling_rate(ts_40, wall_duration_s=2.52)
    assert res_40["valid"] is True
    assert res_40["frame_count"] == 101
    assert abs(res_40["timestamp_span_s"] - 2.5) < 1e-6
    assert abs(res_40["empirical_sampling_rate_hz"] - 40.0) < 1e-4
    assert abs(res_40["mean_interval_ms"] - 25.0) < 1e-3
    assert abs(res_40["median_interval_ms"] - 25.0) < 1e-3
    assert abs(res_40["min_interval_ms"] - 25.0) < 1e-3
    assert abs(res_40["max_interval_ms"] - 25.0) < 1e-3
    assert res_40["wall_clock_rate_hz"] == round(101 / 2.52, 2)

    # 35 Hz: 36 timestamps, dt = 1/35 s, span = 1.0s -> (36 - 1) / 1.0 = 35.0 Hz
    dt_35 = 1.0 / 35.0
    ts_35 = [i * dt_35 for i in range(36)]
    res_35 = compute_session_sampling_rate(ts_35, wall_duration_s=1.0)
    assert res_35["valid"] is True
    assert abs(res_35["empirical_sampling_rate_hz"] - 35.0) < 1e-4


def test_sampling_rate_single_frame_and_empty():
    """Verify empty and single-frame sessions safely yield 0.0 Hz with valid=False."""
    # Empty
    res_empty = compute_session_sampling_rate([])
    assert res_empty["valid"] is False
    assert res_empty["frame_count"] == 0
    assert res_empty["empirical_sampling_rate_hz"] == 0.0
    assert "Insufficient frames" in res_empty["reason"]

    # Single frame
    res_single = compute_session_sampling_rate([1792339078.0], wall_duration_s=1.0)
    assert res_single["valid"] is False
    assert res_single["frame_count"] == 1
    assert res_single["empirical_sampling_rate_hz"] == 0.0
    assert "Insufficient frames" in res_single["reason"]


def test_sampling_rate_duplicates_and_non_monotonic():
    """Verify duplicate timestamps and backwards jumps are rejected."""
    # Duplicate timestamps
    ts_dup = [1.0, 1.028, 1.028, 1.056]
    res_dup = compute_session_sampling_rate(ts_dup)
    assert res_dup["valid"] is False
    assert res_dup["has_duplicates"] is True
    assert res_dup["empirical_sampling_rate_hz"] == 0.0
    assert "duplicate" in res_dup["reason"]

    # Non-monotonic (clock reversal)
    ts_rev = [1.0, 1.028, 1.015, 1.056]
    res_rev = compute_session_sampling_rate(ts_rev)
    assert res_rev["valid"] is False
    assert res_rev["is_strictly_monotonic"] is False
    assert res_rev["empirical_sampling_rate_hz"] == 0.0
    assert "non-monotonic" in res_rev["reason"]


def test_sampling_rate_irregular_intervals():
    """Verify irregular intervals are correctly averaged via (N-1)/span == 1/mean(dt)."""
    # Timestamps: intervals are [0.01, 0.04, 0.05, 0.01, 0.09] -> sum = 0.20s
    ts_irreg = [10.0, 10.01, 10.05, 10.10, 10.11, 10.20]
    res_irreg = compute_session_sampling_rate(ts_irreg)
    assert res_irreg["valid"] is True
    assert res_irreg["frame_count"] == 6
    assert abs(res_irreg["timestamp_span_s"] - 0.20) < 1e-6
    # (6 - 1) / 0.20 = 5 / 0.20 = 25.0 Hz
    assert abs(res_irreg["empirical_sampling_rate_hz"] - 25.0) < 1e-4
    # mean dt = 0.20 / 5 = 0.04s = 40.0 ms
    assert abs(res_irreg["mean_interval_ms"] - 40.0) < 1e-3
    assert abs(res_irreg["min_interval_ms"] - 10.0) < 1e-3
    assert abs(res_irreg["max_interval_ms"] - 90.0) < 1e-3
    assert abs(res_irreg["median_interval_ms"] - 40.0) < 1e-3


def test_sampling_rate_non_finite():
    """Verify NaN and Inf timestamps are rejected."""
    ts_nan = [1.0, float("nan"), 1.05]
    res_nan = compute_session_sampling_rate(ts_nan)
    assert res_nan["valid"] is False
    assert "Non-finite" in res_nan["reason"]

    ts_inf = [1.0, float("inf"), 1.05]
    res_inf = compute_session_sampling_rate(ts_inf)
    assert res_inf["valid"] is False
    assert "Non-finite" in res_inf["reason"]


def test_sampling_rate_real_physical_session_recalculation():
    """Verify exact recomputed values for session phase16_real_walk_Participant_03_1792339078_1792339078."""
    assert AUDITED_SESSION_FILE.exists(), f"Physical session missing: {AUDITED_SESSION_FILE}"

    with open(AUDITED_SESSION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    frames = data["frames"]
    timestamps = [f["timestamp"] for f in frames]

    res = compute_session_sampling_rate(timestamps, wall_duration_s=meta.get("duration_seconds"))

    assert res["valid"] is True
    assert res["frame_count"] == 143
    assert abs(res["timestamp_span_s"] - 3.977267) < 1e-4

    # Rigorous physical empirical rate: (143 - 1) / 3.9772666 = 35.7029 Hz
    assert abs(res["empirical_sampling_rate_hz"] - 35.7029) < 1e-3

    # Confirm reconciliation of the three rates:
    # 1. Stored metadata rate (based on host wall-clock elapsed ~4.02s): 35.56 Hz
    assert meta["mean_sampling_rate_hz"] == 35.56
    # 2. Naive rate dividing N frames by N-1 interval span: 143 / 3.977267 = 35.9543 Hz
    naive_rate = len(timestamps) / res["timestamp_span_s"]
    assert abs(naive_rate - 35.9543) < 1e-3
    # 3. Fencepost-corrected empirical rate: 142 / 3.977267 = 35.7029 Hz
    assert abs(res["empirical_sampling_rate_hz"] - 35.7029) < 1e-3


def test_session_validator_returns_sampling_rate_metrics():
    """Verify DatasetIntegrityValidator validates and includes sampling rate metrics."""
    assert AUDITED_SESSION_FILE.exists()
    validator = DatasetIntegrityValidator(DATASET_DIR)
    res = validator.validate_session_file(AUDITED_SESSION_FILE)

    assert res["valid"] is True
    assert "empirical_sampling_rate_hz" in res
    assert abs(res["empirical_sampling_rate_hz"] - 35.7029) < 1e-3
    assert "timestamp_span_s" in res
    assert abs(res["timestamp_span_s"] - 3.9773) < 1e-3
    assert res["sampling_rate_metrics"]["valid"] is True


def test_phase24_all_recordings_collector_validator_manifest_agreement():
    """Verify that all Phase 24 sessions agree across serialized metadata, validator, and manifest."""
    phase24_sessions = [
        "phase16_real_static_Participant_03_1792388605_1792388605",
        "phase16_real_sit_Participant_03_1792388631_1792388631",
        "phase16_real_walk_Participant_03_1792388657_1792388657",
        "phase16_real_clap_Participant_03_1792388686_1792388686",
        "phase16_real_push_pull_Participant_03_1792388712_1792388712"
    ]

    manifest_path = DATASET_DIR / "dataset_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest_map = {s["session_id"]: s for s in manifest.get("sessions", [])}
    validator = DatasetIntegrityValidator(DATASET_DIR)

    for sid in phase24_sessions:
        json_path = DATASET_DIR / f"{sid}.json"
        csv_path = DATASET_DIR / f"{sid}.csv"
        assert json_path.exists(), f"Missing JSON file for {sid}"
        assert csv_path.exists(), f"Missing CSV mirror for {sid}"
        assert sid in manifest_map, f"Session {sid} missing from manifest"

        manifest_entry = manifest_map[sid]

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data["metadata"]
        frames = data["frames"]
        n = len(frames)
        assert n > 0, f"Session {sid} contains 0 frames"

        ts = [f["timestamp"] for f in frames]
        rate_stats = compute_session_sampling_rate(ts, wall_duration_s=meta.get("duration_seconds"))
        val_res = validator.validate_session_file(json_path)

        # 1. Validator passes cleanly
        assert val_res["valid"] is True, f"Validation failed for {sid}"
        assert val_res["dropped_packets"] == 0
        assert val_res["loss_rate"] == 0.0

        # 2. Formula precision agreement
        expected_empirical = rate_stats["empirical_sampling_rate_hz"]
        assert abs(val_res["empirical_sampling_rate_hz"] - expected_empirical) < 1e-4

        # 3. Serialized metadata agreements
        assert abs(meta["mean_sampling_rate_hz"] - round(expected_empirical, 2)) < 1e-4
        assert abs(meta["timestamp_span_seconds"] - round(rate_stats["timestamp_span_s"], 4)) < 1e-4
        assert meta["packets_received"] == n
        assert meta["packets_lost"] == 0

        # 4. Manifest consistency with serialized metadata
        assert manifest_entry["sampling_rate_hz"] == meta["mean_sampling_rate_hz"]
        assert manifest_entry["packet_count"] == n
        assert manifest_entry["participant_id"] == "Participant_03"
        assert manifest_entry["split"] == "train"
        assert manifest_entry["json_file"] == f"{sid}.json"
        assert manifest_entry["csv_file"] == f"{sid}.csv"

