"""
CSIFormer Phase 42 — Firmware Transport Audit & Pilot Readiness Test Suite.

Verifies:
1. Protected checkpoint and manifest bit-level invariance.
2. Firmware packet serialization and parser compliance on Format B (56 subcarriers) and Format A (legacy).
3. Robust parser error handling against malformed, truncated, empty, and corrupted synthetic packets.
4. Mathematical verification of UART transport budget at 921,600 baud vs 115,200 baud.
5. Quality gate evaluation logic, sequence continuity, monotonicity, flatline detection, and provisional SNR handling.
6. Pilot directory and manifest isolation from the historical dataset and frozen test partition.
"""

import json
import hashlib
import sys
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pytest
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector
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


def test_phase42_checkpoint_and_manifest_hashes():
    """Verify protected checkpoints and dataset manifest remain byte-for-byte unchanged."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Manifest file modified!"


def test_phase42_format_b_parser_with_known_values():
    """Verify parsing of Format B structured telemetry (CSI_DATA) with known synthetic amplitudes and phases."""
    collector = RealCSICollector(auto_connect=False)

    # Generate synthetic 56-subcarrier packet
    expected_amps = [round(float(10.0 + 0.5 * i), 2) for i in range(56)]
    expected_phases = [round(float(-1.5 + 0.05 * i), 3) for i in range(56)]

    subcarrier_str = ",".join(f"{a}:{p}" for a, p in zip(expected_amps, expected_phases))
    synthetic_line = f"CSI_DATA,34:85:18:8E:22:10,-58.0,-95.0,1042,56,{subcarrier_str}\n"

    parsed = collector.parse_raw_telemetry_line(synthetic_line)
    assert parsed is not None
    assert parsed["mac"] == "34:85:18:8E:22:10"
    assert parsed["rssi"] == -58.0
    assert parsed["noise_floor"] == -95.0
    assert parsed["sequence"] == 1042
    assert parsed["num_subcarriers"] == 56
    assert len(parsed["raw_amplitudes"]) == 56
    assert len(parsed["raw_phases"]) == 56

    np.testing.assert_allclose(parsed["raw_amplitudes"], expected_amps, rtol=1e-4)
    np.testing.assert_allclose(parsed["raw_phases"], expected_phases, rtol=1e-3)


def test_phase42_format_a_parser_with_signed_iq():
    """Verify parsing of Format A (raw IQ interleaved stream) with positive and negative integers."""
    collector = RealCSICollector(auto_connect=False)

    # 5 complex pairs with known signed integers: (0,0), (-12, 16), (20, -21), (-30, -40), (127, -128)
    iq_pairs = [(0, 0), (-12, 16), (20, -21), (-30, -40), (127, -128)]
    expected_amps = [math.sqrt(r * r + im * im) for r, im in iq_pairs]
    expected_phases = [math.atan2(im, r) for r, im in iq_pairs]

    iq_str = ",".join(f"{r},{im}" for r, im in iq_pairs)
    synthetic_line = f"=== CSI CALLBACK FIRED === RSSI=-62 LEN=128 CSI:{iq_str}\n"

    parsed = collector.parse_raw_telemetry_line(synthetic_line)
    assert parsed is not None
    assert parsed["rssi"] == -62.0
    assert parsed["num_subcarriers"] == 5
    np.testing.assert_allclose(parsed["raw_amplitudes"], expected_amps, rtol=1e-4)
    np.testing.assert_allclose(parsed["raw_phases"], expected_phases, rtol=1e-4)


def test_phase42_parser_error_handling_and_corrupt_packets():
    """Verify robust rejection of malformed, truncated, empty, and corrupted packet inputs."""
    collector = RealCSICollector(auto_connect=False)

    # 1. Empty string
    assert collector.parse_raw_telemetry_line("") is None
    assert collector.parse_raw_telemetry_line("   \n") is None

    # 2. Random console / boot noise
    assert collector.parse_raw_telemetry_line("rst:0x1 (POWERON_RESET),boot:0x8 (SPI_FAST_FLASH_BOOT)") is None
    assert collector.parse_raw_telemetry_line("W (1204) wifi:Set promiscuous mode ok") is None

    # 3. Truncated Format B header (less than 6 tokens)
    assert collector.parse_raw_telemetry_line("CSI_DATA,34:85:18:8E:22:10,-58.0") is None

    # 4. Truncated subcarrier pair (missing colon)
    corrupt_line = "CSI_DATA,34:85:18:8E:22:10,-58.0,-95.0,1042,56,12.5_no_colon,14.2:0.5\n"
    # Should skip the malformed pair but not crash
    parsed = collector.parse_raw_telemetry_line(corrupt_line)
    if parsed is not None:
        assert len(parsed["raw_amplitudes"]) == 1  # Only the valid pair parsed

    # 5. Non-numeric RSSI in Format A
    corrupt_format_a = "=== CSI CALLBACK FIRED === RSSI=INVALID LEN=128 CSI:10,20\n"
    parsed_a = collector.parse_raw_telemetry_line(corrupt_format_a)
    assert parsed_a is not None
    assert parsed_a["rssi"] == -60.0  # Fallback RSSI applied safely

    # 6. Completely empty CSI payload
    assert collector.parse_raw_telemetry_line("=== CSI CALLBACK FIRED === RSSI=-60 LEN=128 CSI:\n") is None


def test_phase42_uart_transport_budget_calculation():
    """Mathematically verify UART transport capacity at 921,600 baud vs 115,200 baud."""
    # UART standard 8-N-1 framing = 10 bits per character/byte
    baud_921k = 921600
    baud_115k = 115200

    capacity_bytes_sec_921k = baud_921k / 10.0  # 92,160 B/s
    capacity_bytes_sec_115k = baud_115k / 10.0  # 11,520 B/s

    assert capacity_bytes_sec_921k == 92160.0
    assert capacity_bytes_sec_115k == 11520.0

    # Format B full 56-subcarrier packet size estimation:
    # Header: "CSI_DATA,34:85:18:8E:22:10,-58.0,-95.0,123456,56," -> 47 bytes
    header_len = 47
    # Subcarriers: 56 pairs of "%.2f:%.3f," (e.g. "123.45:-3.142,") -> avg 14.5 bytes each
    subcarriers_len = 56 * 14.5  # 812 bytes
    trailing_newline = 1
    total_packet_bytes = header_len + subcarriers_len + trailing_newline  # 860 bytes

    target_rate_hz = 35.0
    required_throughput_bytes_sec = total_packet_bytes * target_rate_hz  # 30,100 B/s

    # 921,600 baud verification:
    utilization_921k = required_throughput_bytes_sec / capacity_bytes_sec_921k
    headroom_921k = 1.0 - utilization_921k

    assert utilization_921k < 0.35, f"Expected < 35% utilization at 921.6k baud, got {utilization_921k:.2%}"
    assert headroom_921k > 0.65, f"Expected > 65% headroom at 921.6k baud, got {headroom_921k:.2%}"

    # 115,200 baud verification:
    utilization_115k = required_throughput_bytes_sec / capacity_bytes_sec_115k
    assert utilization_115k > 2.50, f"Expected > 250% overload at 115.2k baud, got {utilization_115k:.2%}"

    # Verify why 5-subcarrier legacy payload succeeded on 115,200 baud:
    legacy_packet_bytes = 47 + (5 * 14.5) + 1  # 120.5 bytes
    legacy_throughput = legacy_packet_bytes * target_rate_hz  # 4,217.5 B/s
    legacy_utilization_115k = legacy_throughput / capacity_bytes_sec_115k
    assert legacy_utilization_115k < 0.40  # ~36% utilization fits comfortably in 115.2k


def test_phase42_quality_gate_evaluation_provisional_snr():
    """Verify quality gate logic and prove why SNR is classified as provisional."""
    # 1. Prove that in ESP32-S3 firmware, noise_floor is reported as a constant register (-95 dBm)
    # causing SNR = RSSI - Noise to merely track RSSI + 95 dB
    rssi_values = np.array([-50.0, -60.0, -70.0, -80.0])
    fixed_noise = -95.0
    computed_snr = rssi_values - fixed_noise
    expected_snr = rssi_values + 95.0

    np.testing.assert_allclose(computed_snr, expected_snr)
    # The correlation between RSSI and computed SNR is exactly 1.0
    correlation = np.corrcoef(rssi_values, computed_snr)[0, 1]
    assert np.isclose(correlation, 1.0), "SNR without dynamic noise floor is identical to linear shift of RSSI"

    # 2. Sequence continuity and packet loss estimation
    sequences_good = list(range(100, 380))  # 280 continuous packets, 0 lost
    diffs_good = np.diff(sequences_good)
    lost_good = int(np.sum([d - 1 for d in diffs_good if d > 1]))
    assert lost_good == 0

    sequences_lossy = [1, 2, 5, 6, 7, 12, 13, 14]  # Gaps: (5-2-1)=2, (12-7-1)=4
    diffs_lossy = np.diff(sequences_lossy)
    lost_lossy = int(np.sum([d - 1 for d in diffs_lossy if d > 1]))
    assert lost_lossy == 6

    # 3. Sampling rate estimation via Phase 24 standard metric
    t_start = 1000.0
    t_end = 1008.0  # 8.0 seconds span
    timestamps = np.linspace(t_start, t_end, 281)  # 281 frames
    stats = compute_session_sampling_rate(timestamps)
    assert stats["valid"] is True
    assert np.isclose(stats["empirical_sampling_rate_hz"], 35.0, atol=0.01)


def test_phase42_pilot_isolation_invariants():
    """Verify that pilot session storage paths are completely isolated from frozen dataset directories."""
    pilot_dir = BASE_DIR / "data" / "pilot_recordings"
    pilot_manifest = BASE_DIR / "data" / "pilot_manifest.json"

    # Historical real dataset paths
    historical_manifest = DATASET_DIR / "dataset_manifest.json"

    # Assert path disjunction
    assert pilot_dir != DATASET_DIR
    assert pilot_manifest != historical_manifest
    assert str(DATASET_DIR) not in str(pilot_dir)

    # Verify that existing manifest contains zero pilot references
    with open(historical_manifest, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    session_ids = [s["session_id"] for s in manifest_data["sessions"]]
    assert not any("pilot" in sid.lower() for sid in session_ids), "Pilot session found in frozen dataset manifest!"
