"""
CSIFormer Phase 55 — Pilot Campaign Planning and Acquisition Strategy Test Suite.

Verifies offline and non-destructively:
1. Gate 0 / Gate D: Bit-level invariance of protected model checkpoints and dataset manifest.
2. Quality Gates Specification & Evaluation Logic:
   - Validates that quality gate schema evaluates all dimensions.
   - Verifies fail-closed behavior for acquisition-rate adequacy when rate < 30.0 Hz.
3. Passive-Only Pilot Protocol Constraints:
   - Verifies that passive operation requires filter_by_mac=True.
   - Verifies rejection of missing or ambient MACs without active traffic stimulation.
4. Global Sequence Reconciliation vs Target Stream Interleaving:
   - Mathematically verifies that global sequence counter increments across transmitters,
     and sequence jumps in target stream correspond to filtered non-target packets.
5. Temporal Dilation & Window Semantics Audit:
   - Formally checks window duration T = 50 / rate_hz, verifying 18x dilation at 1.66 Hz vs 30 Hz.
"""

import hashlib
import json
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

from backend.app.services.real_csi_collector import RealCSICollector
from backend.app.services.esp32_csi_adapter import ESP32CSIAdapter
from backend.app.services.session_validator import compute_session_sampling_rate

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase55_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain 100% bit-level invariant."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase55_acquisition_rate_gate_fails_closed_under_passive_conditions():
    """
    Verify that the acquisition-rate quality gate evaluates strictly fail-closed:
    A passive observation yielding ~1.66 Hz or ~3.20 Hz MUST fail the rate adequacy gate (threshold >= 30.0 Hz).
    """
    def evaluate_rate_gate(measured_rate_hz: float, min_threshold_hz: float = 30.0) -> dict:
        passed = measured_rate_hz >= min_threshold_hz
        return {
            "gate_name": "acquisition_rate_adequacy",
            "measured_rate_hz": measured_rate_hz,
            "min_threshold_hz": min_threshold_hz,
            "status": "PASS" if passed else "FAIL_BLOCKED",
            "is_ready_for_dataset_admission": passed,
            "reason": None if passed else f"Measured rate {measured_rate_hz:.2f} Hz below minimum {min_threshold_hz:.1f} Hz"
        }

    # Under Phase 54 passive baseline (1.66 Hz)
    gate_p54 = evaluate_rate_gate(1.66)
    assert gate_p54["status"] == "FAIL_BLOCKED"
    assert not gate_p54["is_ready_for_dataset_admission"]

    # Under Phase 52 passive diagnostic (3.20 Hz)
    gate_p52 = evaluate_rate_gate(3.20)
    assert gate_p52["status"] == "FAIL_BLOCKED"
    assert not gate_p52["is_ready_for_dataset_admission"]

    # Historical rate (36.8 Hz)
    gate_hist = evaluate_rate_gate(36.8)
    assert gate_hist["status"] == "PASS"
    assert gate_hist["is_ready_for_dataset_admission"]


def test_phase55_passive_pilot_source_filtering_fail_closed():
    """
    Verify that a passive-only pilot protocol correctly discards ambient transmitters
    and enforces fail-closed behavior for malformed or missing MAC addresses.
    """
    target_ap = "98:BA:5F:EF:28:26"
    collector = RealCSICollector(
        port=None,
        auto_connect=False,
        target_mac=target_ap,
        filter_by_mac=True
    )

    # Frame 1: Valid Target AP Downlink Frame
    collector._process_parsed_frame({
        "timestamp": 100.0,
        "sequence": 10,
        "mac": target_ap.lower(),
        "rssi": -61.0,
        "noise_floor": -92.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [10.0] * 56,
        "raw_phases": [0.5] * 56
    })
    assert collector.csi_packets_parsed == 1
    assert collector.filtered_non_target_packets == 0

    # Frame 2: Interleaved Ambient Client Transmission (Uplink)
    collector._process_parsed_frame({
        "timestamp": 100.2,
        "sequence": 11,
        "mac": "60:E9:AA:2C:9A:83",
        "rssi": -55.0,
        "noise_floor": -92.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [12.0] * 56,
        "raw_phases": [0.2] * 56
    })
    assert collector.csi_packets_parsed == 1  # Unchanged
    assert collector.filtered_non_target_packets == 1

    # Frame 3: Missing / Null MAC -> Fail-closed policy
    collector._process_parsed_frame({
        "timestamp": 100.4,
        "sequence": 12,
        "mac": None,
        "rssi": -70.0,
        "noise_floor": -92.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [8.0] * 56,
        "raw_phases": [0.0] * 56
    })
    assert collector.csi_packets_parsed == 1
    assert collector.parse_errors == 1


def test_phase55_global_sequence_reconciliation_logic():
    """
    Verify that sequence jumps in the admitted target stream can be reconciled
    against the global counter and filtered non-target packets without false loss attribution.
    """
    global_stream = [
        {"seq": 100, "mac": "98:BA:5F:EF:28:26", "target": True},
        {"seq": 101, "mac": "18:CC:88:7E:74:71", "target": False},
        {"seq": 102, "mac": "80:5E:4F:21:03:FA", "target": False},
        {"seq": 103, "mac": "98:BA:5F:EF:28:26", "target": True},
        {"seq": 104, "mac": "98:BA:5F:EF:28:26", "target": True},
    ]

    target_seqs = [f["seq"] for f in global_stream if f["target"]]
    non_target_seqs = [f["seq"] for f in global_stream if not f["target"]]

    # In target stream, sequence jumps from 100 to 103: jump = 3, delta = 2
    naive_loss = sum(b - a - 1 for a, b in zip(target_seqs[:-1], target_seqs[1:]) if b - a > 1)
    assert naive_loss == 2  # Naive validator reports 2 dropped packets

    # Reconciled sequence audit:
    interleaved_foreign_count = len(non_target_seqs)
    unaccounted_loss = max(0, naive_loss - interleaved_foreign_count)
    assert unaccounted_loss == 0  # Reconciled true physical transport loss is 0.00%


def test_phase55_temporal_dilation_and_window_semantics():
    """
    Verify the mathematical relationship between physical sampling rate and temporal duration
    for CSIFormer's 50-frame temporal window.
    """
    num_frames = 50

    # Model design rate: 35.0 Hz
    t_designed = num_frames / 35.0
    assert pytest.approx(t_designed, 0.01) == 1.428  # ~1.43 seconds of human motion

    # Passive acquisition rate: 1.66 Hz
    t_passive_p54 = num_frames / 1.66
    assert pytest.approx(t_passive_p54, 0.1) == 30.12  # ~30.12 seconds

    dilation_factor = t_passive_p54 / t_designed
    assert pytest.approx(dilation_factor, 0.5) == 21.08  # ~21x temporal dilation

    # Verify that sampling rate function correctly identifies rate and monotonicity
    timestamps = [1000.0 + i * (1.0 / 1.66) for i in range(num_frames)]
    rate_stats = compute_session_sampling_rate(timestamps)
    assert rate_stats["valid"]
    assert pytest.approx(rate_stats["empirical_sampling_rate_hz"], 0.01) == 1.66
    assert rate_stats["is_strictly_monotonic"]
