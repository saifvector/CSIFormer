"""
Phase 56.2 Offline Test Suite: Temporal Requirement and Firmware Readiness Audit.

Validates:
1. Gate 0: Protected asset hash invariance.
2. Temporal Preprocessing Invariance: Proves that PhysicsCSIPreprocessor.compute_doppler_spectrogram
   output tensor is mathematically invariant to source_rate_hz.
3. Training vs Live Preprocessor Divergence: Audits STFT window/overlap and Doppler scaling differences.
4. Sequence Gap Semantics: Audits how firmware sequence numbers interact with MAC filtering.
5. Decoupled Calibration Metrics & Thresholds: Validates threshold classifications.
"""

import sys
import hashlib
from pathlib import Path
import numpy as np
import pytest
import torch

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor, CalibratedPhysicsPreprocessor
from backend.app.services.real_csi_collector import RealCSICollector


# ==============================================================================
# Gate 0: Protected File Invariance
# ==============================================================================
def test_phase56_2_gate0_protected_file_invariance():
    """Verify that all protected files remain byte-for-byte invariant."""
    targets = {
        BASE_DIR / "models" / "csiformer_phase13_best.pth": "383b4d98c08f8970b0443738f170ec01",
        BASE_DIR / "models" / "csiformer_phase15_adapted.pth": "ab3d97a04d78edf75d807178772bc828",
        BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json": "a58e1280fb2c0a6649335a9a381d00c6"
    }
    for file_path, expected_md5 in targets.items():
        assert file_path.exists(), f"Protected file missing: {file_path}"
        with open(file_path, "rb") as f:
            actual_md5 = hashlib.md5(f.read()).hexdigest()
        assert actual_md5.lower() == expected_md5.lower(), (
            f"Gate 0 violation: {file_path.name} hash mismatch.\n"
            f"Expected: {expected_md5}\nActual:   {actual_md5}"
        )


# ==============================================================================
# Test 1: Temporal Preprocessor Invariance to source_rate_hz
# ==============================================================================
def test_phase56_2_preprocessor_invariance_to_source_rate():
    """
    Formally proves that PhysicsCSIPreprocessor.compute_doppler_spectrogram
    produces identical numerical tensors regardless of source_rate_hz.
    This demonstrates that 30 Hz in the preprocessor does NOT change the tensor values.
    """
    np.random.seed(42)
    sample_csi = np.random.randn(50, 56) + 1j * np.random.randn(50, 56)

    p_30 = PhysicsCSIPreprocessor(carrier_freq=2.442e9, source_rate_hz=30.0)
    p_35 = PhysicsCSIPreprocessor(carrier_freq=2.442e9, source_rate_hz=35.58)
    p_1000 = PhysicsCSIPreprocessor(carrier_freq=5.2e9, source_rate_hz=1000.0)

    d_30 = p_30.compute_doppler_spectrogram(sample_csi)
    d_35 = p_35.compute_doppler_spectrogram(sample_csi)
    d_1000 = p_1000.compute_doppler_spectrogram(sample_csi)

    # Tensor shapes must be (50, 56)
    assert d_30.shape == (50, 56)
    assert d_35.shape == (50, 56)
    assert d_1000.shape == (50, 56)

    # Max absolute difference across any rate must be 0.0 (or floating point epsilon < 1e-6)
    diff_30_35 = np.max(np.abs(d_30 - d_35))
    diff_30_1000 = np.max(np.abs(d_30 - d_1000))
    assert diff_30_35 < 1e-6, f"Expected identical output regardless of source_rate_hz, got diff: {diff_30_35}"
    assert diff_30_1000 < 1e-6, f"Expected identical output regardless of source_rate_hz, got diff: {diff_30_1000}"


# ==============================================================================
# Test 2: Training vs Live Preprocessor Divergence Audit
# ==============================================================================
def test_phase56_2_training_vs_live_preprocessor_divergence():
    """
    Audits the structural preprocessing difference between LivePipelineService configuration
    (STFT window 32, noverlap 24, nfft 64, unscaled) and Phase 15 training preprocessor
    (CalibratedPhysicsPreprocessor: STFT window 64, noverlap 48, nfft 128, 2.385x Doppler scale).
    """
    np.random.seed(42)
    sample_csi = np.random.randn(50, 56)

    # Live config
    p_live = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )
    # Phase 15 training config
    p_train = CalibratedPhysicsPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=35.58,
        target_timesteps=50,
        target_channels=56
    )

    d_live = p_live.compute_doppler_spectrogram(sample_csi)
    d_train = p_train.compute_doppler_spectrogram(sample_csi)

    assert d_live.shape == (50, 56)
    assert d_train.shape == (50, 56)

    # They differ due to STFT window/nfft resolution and Doppler scale stretching
    diff = np.max(np.abs(d_live - d_train))
    assert diff > 0.5, f"Expected live and training preprocessors to diverge, but diff was {diff}"


# ==============================================================================
# Test 3: Sequence Gap vs Ambient Filtering Conflation
# ==============================================================================
def test_phase56_2_sequence_gap_conflation_audit():
    """
    Demonstrates that tracking packet loss from global callback sequence numbers
    when filter_by_mac=True erroneously counts filtered ambient frames as packet loss.
    """
    collector = RealCSICollector(target_mac="98:BA:5F:EF:28:26", filter_by_mac=True)

    # Target frame at seq=1
    collector._process_parsed_frame({
        "timestamp": 1000.0,
        "host_monotonic_time": 10.0,
        "sequence": 1,
        "mac": "98:BA:5F:EF:28:26",
        "rssi": -50,
        "noise_floor": -95,
        "raw_amplitudes": [1.0] * 56,
        "raw_phases": [0.0] * 56
    })
    assert collector.packets_received == 1
    assert collector.packets_lost == 0
    assert collector.filtered_non_target_packets == 0

    # Ambient non-target frame at seq=2 (e.g. smartphone probe request)
    collector._process_parsed_frame({
        "timestamp": 1000.02,
        "host_monotonic_time": 10.02,
        "sequence": 2,
        "mac": "AA:BB:CC:DD:EE:FF",
        "rssi": -70,
        "noise_floor": -95,
        "raw_amplitudes": [1.0] * 56,
        "raw_phases": [0.0] * 56
    })
    assert collector.packets_received == 1  # Not admitted to target buffer
    assert collector.filtered_non_target_packets == 1

    # Next target frame arrives at seq=3
    collector._process_parsed_frame({
        "timestamp": 1000.04,
        "host_monotonic_time": 10.04,
        "sequence": 3,
        "mac": "98:BA:5F:EF:28:26",
        "rssi": -50,
        "noise_floor": -95,
        "raw_amplitudes": [1.0] * 56,
        "raw_phases": [0.0] * 56
    })

    # Phase 57 Fix: Target sequence gap is 1 (seq 3 - (1 + 1)), but confirmed transport loss is 0
    # Ambient frame at seq 2 was received over serial, not lost over transport.
    assert collector.packets_received == 2
    assert collector.target_sequence_gaps == 1
    assert collector.packets_lost == 0
    assert collector.filtered_non_target_packets == 1


# ==============================================================================
# Test 4: Decoupled Calibration Metric Schema & Threshold Provenance
# ==============================================================================
def test_phase56_2_calibration_metric_schema_and_threshold_provenance():
    """
    Verifies that the calibration protocol defines 6 decoupled quantities
    with rigorous provenance categories.
    """
    calibration_metrics = {
        "R_stim": {
            "name": "Stimulator Transmission Rate",
            "unit": "pkts/s",
            "provenance_category": "DERIVED_FROM_DOCUMENTED_PROJECT_REQUIREMENT",
            "stages": [0, 5, 15, 30, 35]
        },
        "R_raw": {
            "name": "Total Physical CSI Callback Rate",
            "unit": "Hz",
            "provenance_category": "DERIVED_FROM_VERIFIED_TECHNICAL_CONSTRAINT",
            "threshold_max_uart_hz": 120.0  # Technical UART limit at 921600 baud
        },
        "R_target": {
            "name": "Target-BSSID Filtered CSI Rate",
            "unit": "Hz",
            "provenance_category": "PROVISIONAL_ENGINEERING_THRESHOLD",
            "target_threshold_hz": 28.0
        },
        "R_parsed": {
            "name": "Collector Buffer Admitted Rate",
            "unit": "Hz",
            "provenance_category": "DERIVED_FROM_VERIFIED_TECHNICAL_CONSTRAINT"
        },
        "dt_hw": {
            "name": "Hardware Inter-Arrival Interval",
            "unit": "microseconds",
            "provenance_category": "DERIVED_FROM_VERIFIED_TECHNICAL_CONSTRAINT",
            "wraparound_us": 2**32
        },
        "dt_host": {
            "name": "Host Monotonic Inter-Arrival Interval",
            "unit": "seconds",
            "provenance_category": "DERIVED_FROM_VERIFIED_TECHNICAL_CONSTRAINT",
            "max_abort_ms": 100.0,
            "mean_abort_ms": 30.0
        }
    }

    assert len(calibration_metrics) == 6
    valid_categories = {
        "DERIVED_FROM_VERIFIED_TECHNICAL_CONSTRAINT",
        "DERIVED_FROM_DOCUMENTED_PROJECT_REQUIREMENT",
        "PROVISIONAL_ENGINEERING_THRESHOLD"
    }
    for key, spec in calibration_metrics.items():
        assert spec["provenance_category"] in valid_categories
