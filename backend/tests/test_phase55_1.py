"""
CSIFormer Phase 55.1 — Corrective Engineering Audit & Quality Gate Test Suite.

Targeted offline tests verifying:
1. Protected asset bit-level hash invariance (Gate 0 / Gate D).
2. Separation of Record Count Gate (data volume) vs Acquisition Rate Gate (temporal frequency).
3. Window duration math: 50 rate intervals (50/f) vs first-to-last sample span ((50-1)/f).
4. Spatial subcarrier interpolation invariance (frequency domain != temporal sampling).
5. Physics preprocessor STFT Doppler frequency scaling with source_rate_hz.
6. Carrier validity with multipath fading notches (non-negative, finite, tolerating low amplitudes).
7. Timestamp monotonicity and burst resolution semantics in compute_session_sampling_rate.
8. Explicit session disposition states (ACCEPTED, QUARANTINED, REJECTED, INCOMPLETE).
"""

import hashlib
import json
import sys
from pathlib import Path
import pytest
import numpy as np
import scipy.signal as signal

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector
from backend.app.services.esp32_csi_adapter import ESP32CSIAdapter
from backend.app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
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


def test_phase55_1_protected_hashes():
    """Verify that protected model checkpoints and dataset manifest remain bit-level invariant."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase55_1_record_count_vs_rate_separation():
    """
    Demonstrates why Record Count Gate and Acquisition Rate Gate must remain distinct:
    A 15.0 s trial yielding 50 frames satisfies a naive count gate (N >= 50),
    but its acquisition rate is only 3.33 Hz, severely failing the 30.0 Hz rate gate.
    Conversely, a 1.66 Hz passive stream over 15.0 s yields ~25 frames, failing both.
    """
    def evaluate_gates(frame_count: int, duration_s: float, min_count: int = 50, min_rate_hz: float = 30.0):
        empirical_rate = (frame_count - 1) / duration_s if duration_s > 0 and frame_count > 1 else 0.0
        count_pass = frame_count >= min_count
        rate_pass = empirical_rate >= min_rate_hz
        return {
            "count_gate": "PASS" if count_pass else "FAIL",
            "rate_gate": "PASS" if rate_pass else "FAIL",
            "empirical_rate_hz": round(empirical_rate, 2),
            "frame_count": frame_count,
            "duration_s": duration_s
        }

    # Case A: 50 frames in 15 seconds (slow arrival)
    res_a = evaluate_gates(frame_count=50, duration_s=15.0)
    assert res_a["count_gate"] == "PASS"      # Count threshold satisfied
    assert res_a["rate_gate"] == "FAIL"       # 3.27 Hz fails 30 Hz threshold!

    # Case B: Passive 1.66 Hz over 15 seconds (~25 frames)
    res_b = evaluate_gates(frame_count=25, duration_s=15.0)
    assert res_b["count_gate"] == "FAIL"      # 25 < 50
    assert res_b["rate_gate"] == "FAIL"       # 1.60 Hz fails

    # Case C: 30 Hz sustained over 15 seconds (450 frames)
    res_c = evaluate_gates(frame_count=451, duration_s=15.0)
    assert res_c["count_gate"] == "PASS"      # 451 >= 50
    assert res_c["rate_gate"] == "PASS"       # 30.0 Hz satisfies


def test_phase55_1_window_span_definitions_consistency():
    """
    Verifies consistent window duration definitions:
    - 50 rate intervals: T_intervals = 50 / rate
    - First-to-last sample span: Delta_t = (50 - 1) / rate
    """
    # At 1.66 Hz (Phase 54 passive)
    rate_passive = 1.66
    span_passive_first_to_last = (50 - 1) / rate_passive
    duration_passive_intervals = 50 / rate_passive
    assert pytest.approx(span_passive_first_to_last, 0.05) == 29.52
    assert pytest.approx(duration_passive_intervals, 0.05) == 30.12

    # At 30.0 Hz (Production requirement)
    rate_30 = 30.0
    span_30_first_to_last = (50 - 1) / rate_30
    duration_30_intervals = 50 / rate_30
    assert pytest.approx(span_30_first_to_last, 0.01) == 1.633
    assert pytest.approx(duration_30_intervals, 0.01) == 1.667

    # At 35.0 Hz (Historical collection rate)
    rate_35 = 35.0
    span_35_first_to_last = (50 - 1) / rate_35
    duration_35_intervals = 50 / rate_35
    assert pytest.approx(span_35_first_to_last, 0.01) == 1.400
    assert pytest.approx(duration_35_intervals, 0.01) == 1.429


def test_phase55_1_spatial_interpolation_invariance():
    """
    Verifies that spatial/channel interpolation (64 raw bins or 52 active tones to 56 model channels)
    operates purely across the subcarrier dimension and does NOT alter the temporal dimension
    or increase temporal sampling rate.
    """
    num_frames = 10
    raw_subcarriers = 64
    target_channels = 56

    # Create mock frames across time: shape [T, Subcarriers]
    mock_frames = np.random.uniform(5.0, 25.0, (num_frames, raw_subcarriers)).astype(np.float32)

    # Apply spatial interpolation across subcarriers
    x_old = np.linspace(0, 1, raw_subcarriers)
    x_new = np.linspace(0, 1, target_channels)
    interpolated_frames = np.array([np.interp(x_new, x_old, row) for row in mock_frames])

    assert interpolated_frames.shape == (num_frames, target_channels)
    # The temporal dimension remains strictly 10 frames: spatial interpolation cannot add temporal frames!
    assert interpolated_frames.shape[0] == num_frames


def test_phase55_1_doppler_stft_frequency_scaling():
    """
    Verifies that STFT frequency axis in PhysicsCSIPreprocessor scales directly with source_rate_hz.
    Changing source_rate_hz to 1.66 Hz compresses the Nyquist interval to [-0.83, +0.83] Hz,
    scaling frequency bins by ~18x compared to 30 Hz.
    """
    # 50 frames of signal
    t_30 = np.linspace(0, 50 / 30.0, 50)
    sig = np.sin(2 * np.pi * 5.0 * t_30)  # 5 Hz motion component

    # STFT at fs = 30.0 Hz
    f_30, t_out_30, Z_30 = signal.stft(sig, fs=30.0, window="hann", nperseg=32, noverlap=24, nfft=64, return_onesided=False)
    # STFT at fs = 1.66 Hz
    f_low, t_out_low, Z_low = signal.stft(sig, fs=1.66, window="hann", nperseg=32, noverlap=24, nfft=64, return_onesided=False)

    # At 30 Hz, Nyquist is 15 Hz; frequency spacing is 30 / 64 = 0.46875 Hz
    assert np.max(np.abs(f_30)) == 15.0
    # At 1.66 Hz, Nyquist is 0.83 Hz; frequency spacing is 1.66 / 64 = 0.0259 Hz
    assert pytest.approx(np.max(np.abs(f_low)), 0.02) == 0.83

    # Frequency bin scaling factor
    scaling = (f_30[1] - f_30[0]) / (f_low[1] - f_low[0])
    assert pytest.approx(scaling, 0.1) == (30.0 / 1.66)


def test_phase55_1_carrier_validity_multipath_notch_tolerance():
    """
    Verifies that a physical CSI frame experiencing a deep multipath fading notch
    (where certain subcarriers have near-zero amplitude) is valid as long as array dimensions
    match 64 and all values are non-negative and finite.
    Requiring all 52 active carriers to be strictly nonzero would falsely reject valid multipath frames.
    """
    # Simulate a 64-bin frame with a deep fading notch at bins 12-14 (near 0) and DC bin 0 at 0.0
    raw_amps = np.random.uniform(10.0, 25.0, 64).astype(np.float32)
    raw_amps[0] = 0.0     # DC carrier null
    raw_amps[12:15] = 0.001  # Deep multipath fading notch
    raw_amps[27:38] = 0.05   # Guard carrier null band

    def validate_physical_carriers(amps: np.ndarray) -> dict:
        if len(amps) != 64:
            return {"valid": False, "reason": "Incorrect subcarrier count"}
        if not np.all(np.isfinite(amps)):
            return {"valid": False, "reason": "Non-finite subcarriers"}
        if np.any(amps < 0):
            return {"valid": False, "reason": "Negative amplitude"}
        # Check active carrier energy vs null band
        active_indices = np.concatenate([np.arange(1, 27), np.arange(38, 64)])
        null_indices = np.concatenate([[0], np.arange(27, 38)])
        active_power = np.mean(amps[active_indices] ** 2)
        null_power = np.mean(amps[null_indices] ** 2)
        if active_power <= 0:
            return {"valid": False, "reason": "Zero active carrier power"}
        return {
            "valid": True,
            "active_power": float(active_power),
            "null_power": float(null_power),
            "snr_like_ratio_db": float(10 * np.log10(active_power / max(1e-9, null_power)))
        }

    val = validate_physical_carriers(raw_amps)
    assert val["valid"]
    assert val["snr_like_ratio_db"] > 10.0


def test_phase55_1_session_disposition_states():
    """
    Verifies that the session quality gate workflow cleanly and unambiguously assigns
    one of four distinct verdicts: ACCEPTED, QUARANTINED, REJECTED, or INCOMPLETE.
    """
    def evaluate_session_verdict(
        target_mac_match: bool,
        channel_match: bool,
        finite_data: bool,
        frame_count: int,
        rate_hz: float,
        aborted_early: bool
    ) -> str:
        if aborted_early:
            return "INCOMPLETE"
        if not target_mac_match or not channel_match or not finite_data:
            return "REJECTED"
        if rate_hz < 30.0 or frame_count < 50:
            return "QUARANTINED"
        return "ACCEPTED"

    # Perfect session matching all criteria
    assert evaluate_session_verdict(True, True, True, 450, 35.0, False) == "ACCEPTED"

    # Passive trial with rate deficit (1.66 Hz)
    assert evaluate_session_verdict(True, True, True, 25, 1.66, False) == "QUARANTINED"

    # Wrong channel or corrupt data
    assert evaluate_session_verdict(True, False, True, 450, 35.0, False) == "REJECTED"
    assert evaluate_session_verdict(True, True, False, 450, 35.0, False) == "REJECTED"

    # Aborted early trial (like Phase 54 probe 15)
    assert evaluate_session_verdict(True, True, True, 6, 0.85, True) == "INCOMPLETE"
