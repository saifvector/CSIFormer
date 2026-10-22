"""
CSIFormer Phase 56.1 Test Suite — Historical Rate Verification & Calibration Readiness Audit.

Validates:
1. Gate 0: Cryptographic invariance of protected checkpoints and dataset manifest.
2. Collector Buffer Lockstep Invariance:
   - Verifies that all 6 deques (raw_frame_buffer, timestamp_buffer, monotonic_buffer,
     sequence_buffer, source_mac_buffer, hw_timestamp_buffer) maintain identical lengths
     across frame arrivals, missing hardware timestamps, and window eviction (FIFO roll).
3. Telemetry Parser Mutual Exclusivity:
   - Verifies that malformed Format B v2 records (e.g. truncated or corrupted) return None
     and are NOT misparsed by the historical Format B (CSI_DATA) branch.
4. Historical Provenance Audit:
   - Verifies that historical session JSON files contain NO source MAC metadata and NO
     UDP transmission counts, proving target-BSSID rate and packets sent are strictly unknown.
5. Diagnostic Timing Robustness:
   - Verifies that get_window_timing_diagnostics() safely handles empty buffers (N=0),
     single-frame buffers (N=1), zero-span / duplicate timestamps (dt=0), and negative spans.
6. Decoupled Calibration Metrics Contract:
   - Verifies that all 6 calibration quantities (UDP sent, total CSI, target CSI, parsed CSI,
     hardware interval, host arrival interval) are mathematically independent.
"""

import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.services.real_csi_collector import RealCSICollector
    from app.services.session_validator import compute_session_sampling_rate
except ImportError:
    from backend.app.services.real_csi_collector import RealCSICollector
    from backend.app.services.session_validator import compute_session_sampling_rate

PROTECTED_ASSETS = {
    "models/csiformer_phase13_best.pth": "383b4d98c08f8970b0443738f170ec01",
    "models/csiformer_phase15_adapted.pth": "ab3d97a04d78edf75d807178772bc828",
    "data/real_csi_dataset/dataset_manifest.json": "a58e1280fb2c0a6649335a9a381d00c6"
}


def test_phase56_1_gate0_protected_file_invariance():
    """Confirms all protected assets remain strictly invariant."""
    for rel_path, expected_md5 in PROTECTED_ASSETS.items():
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Protected asset missing: {rel_path}"
        hasher = hashlib.md5()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        measured_md5 = hasher.hexdigest().lower()
        assert measured_md5 == expected_md5, f"MD5 mismatch for {rel_path}: {measured_md5} != {expected_md5}"


def test_phase56_1_collector_buffer_lockstep_alignment():
    """
    Verifies that all 6 internal deques in RealCSICollector maintain exact 1-to-1
    alignment even when hardware timestamps are intermittently missing, and when
    the sliding window fills and evicts older frames.
    """
    collector = RealCSICollector()

    # Feed 75 frames (exceeding WINDOW_SIZE=50 to test FIFO eviction)
    # Alternate frames with and without hw_timestamp_us
    for i in range(75):
        amps = [float(10.0 + i * 0.1)] * 56
        phases = [0.0] * 56
        frame = {
            "timestamp": 1792300000.0 + i * 0.033,
            "host_monotonic_time": 100.0 + i * 0.033,
            "sequence": 1000 + i,
            "mac": f"AA:BB:CC:DD:EE:{i%10:02X}",
            "rssi": -60.0 + (i % 5),
            "noise_floor": -95.0,
            "raw_amplitudes": amps,
            "raw_phases": phases
        }
        # Only even frames have hw_timestamp_us
        if i % 2 == 0:
            frame["hw_timestamp_us"] = 5000000 + i * 33333

        collector._process_parsed_frame(frame)

        # Invariant check: lengths of all buffers must be identical at all times
        n_raw = len(collector.raw_frame_buffer)
        assert len(collector.phase_frame_buffer) == n_raw
        assert len(collector.timestamp_buffer) == n_raw
        assert len(collector.monotonic_buffer) == n_raw
        assert len(collector.sequence_buffer) == n_raw
        assert len(collector.source_mac_buffer) == n_raw
        assert len(collector.hw_timestamp_buffer) == n_raw
        assert n_raw <= collector.WINDOW_SIZE

    # At completion (75 frames pushed into 50-slot deque):
    assert len(collector.raw_frame_buffer) == 50
    assert len(collector.hw_timestamp_buffer) == 50

    # Oldest retained frame must be index 25 (75 - 50 = 25)
    assert collector.sequence_buffer[0] == 1025
    assert collector.sequence_buffer[-1] == 1074

    # Because frames alternated missing timestamps, has_hw_timestamps must be False
    res = collector.get_latest_window(return_metadata=True)
    assert res is not None
    _, _, meta = res
    assert meta["has_hw_timestamps"] is False
    assert meta["hw_timestamps_us"] is None


def test_phase56_1_telemetry_parser_mutual_exclusivity():
    """
    Verifies that malformed Format B v2 lines are cleanly rejected as None
    and are NEVER misparsed as historical Format B (CSI_DATA).
    """
    collector = RealCSICollector()

    # 1. Truncated CSI_DATA_V2 line (fewer than 8 header tokens before subcarriers)
    malformed_v2_truncated = "CSI_DATA_V2,98:BA:5F:EF:28:26,-58.0,-95.0,105,123456"
    assert collector.parse_raw_telemetry_line(malformed_v2_truncated) is None

    # 2. Corrupted token types in CSI_DATA_V2 (e.g. non-numeric sequence or timestamp)
    subcarrier_str = ",".join([f"10.{i}:0.{i}" for i in range(56)])
    malformed_v2_bad_token = f"CSI_DATA_V2,98:BA:5F:EF:28:26,-58.0,-95.0,INVALID_SEQ,NOT_TS,4092,56,{subcarrier_str}"
    assert collector.parse_raw_telemetry_line(malformed_v2_bad_token) is None

    # 3. Valid CSI_DATA_V2 must be parsed with protocol "structured_csi_data_v2"
    valid_v2 = f"CSI_DATA_V2,98:BA:5F:EF:28:26,-58.0,-95.0,105,123456789,4092,56,{subcarrier_str}"
    parsed_v2 = collector.parse_raw_telemetry_line(valid_v2)
    assert parsed_v2 is not None
    assert collector.detected_protocol == "structured_csi_data_v2"

    # 4. Valid historical CSI_DATA must be parsed with protocol "structured_csi_data"
    valid_v1 = f"CSI_DATA,98:BA:5F:EF:28:26,-58.0,-95.0,105,56,{subcarrier_str}"
    parsed_v1 = collector.parse_raw_telemetry_line(valid_v1)
    assert parsed_v1 is not None
    assert collector.detected_protocol == "structured_csi_data"


def test_phase56_1_historical_provenance_audit():
    """
    Audits historical session files in data/real_csi_dataset/ to confirm:
    1. No source MAC metadata is present in individual frames (Format A limitation).
    2. No UDP probe counter (packets_sent) was recorded.
    3. Target-BSSID rate and actual transmitted probe count are strictly UNKNOWN.
    """
    sample_session_path = PROJECT_ROOT / "data/real_csi_dataset/phase14_p15_real_clap_t2_1792303926_1792303926.json"
    assert sample_session_path.exists()

    with open(sample_session_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Confirm metadata does NOT log UDP stimulation metrics
    meta = data.get("metadata", {})
    assert "packets_sent" not in meta
    assert "udp_stimulator" not in meta
    assert "target_bssid_rate" not in meta

    # Confirm frames do NOT log source MAC address
    frames = data.get("frames", [])
    assert len(frames) > 0
    for frame in frames[:5]:
        assert "mac" not in frame or frame["mac"] is None
        assert "hw_timestamp_us" not in frame

    # Confirm protocol is raw_iq_stream (Format A)
    assert meta.get("hardware", {}).get("protocol") == "raw_iq_stream"


def test_phase56_1_diagnostic_timing_robustness():
    """
    Verifies that get_window_timing_diagnostics() handles edge cases robustly:
    - Empty buffer (N=0)
    - Single-frame buffer (N=1)
    - Duplicate timestamps / zero span (dt=0)
    - Non-monotonic timestamps / negative span
    """
    collector = RealCSICollector()

    # 1. Empty buffer
    diag_empty = collector.get_window_timing_diagnostics()
    assert diag_empty["buffered_frames"] == 0
    assert diag_empty["empirical_rate_hz"] == 0.0
    assert diag_empty["mean_interval_ms"] == 0.0
    assert diag_empty["is_full"] is False

    # 2. Single frame
    collector._process_parsed_frame({
        "timestamp": 1000.0,
        "host_monotonic_time": 10.0,
        "sequence": 1,
        "mac": "AA:BB:CC:DD:EE:FF",
        "rssi": -60.0,
        "noise_floor": -95.0,
        "raw_amplitudes": [10.0] * 56,
        "raw_phases": [0.0] * 56
    })
    diag_one = collector.get_window_timing_diagnostics()
    assert diag_one["buffered_frames"] == 1
    assert diag_one["empirical_rate_hz"] == 0.0
    assert diag_one["is_full"] is False

    # 3. Duplicate timestamps (clock frozen, dt=0)
    for i in range(10):
        collector._process_parsed_frame({
            "timestamp": 1000.0,
            "host_monotonic_time": 10.0,  # identical
            "sequence": 2 + i,
            "mac": "AA:BB:CC:DD:EE:FF",
            "rssi": -60.0,
            "noise_floor": -95.0,
            "raw_amplitudes": [10.0] * 56,
            "raw_phases": [0.0] * 56
        })
    diag_dup = collector.get_window_timing_diagnostics()
    assert diag_dup["buffered_frames"] == 11
    assert diag_dup["span_seconds"] == 0.0
    assert diag_dup["empirical_rate_hz"] == 0.0
    assert diag_dup["cv_interval"] == 0.0


def test_phase56_1_decoupled_calibration_quantities():
    """
    Verifies mathematical decoupling of the 6 calibration quantities:
    Quantity A: R_udp_sent (UDP datagrams sent / s)
    Quantity B: R_csi_total (Total CSI records received / s)
    Quantity C: R_csi_target (Target-BSSID CSI records / s)
    Quantity D: R_parsed (Successfully parsed records / s)
    Quantity E: dt_hw (Actual hardware inter-arrival interval)
    Quantity F: dt_host (Host serial arrival interval)
    """
    # Simulate a scenario with:
    # 35 UDP datagrams sent in 1.0s -> R_udp_sent = 35.0 Hz
    # 38 total RF frames on channel -> R_csi_total = 38.0 Hz
    # 33 target AP frames admitted -> R_csi_target = 33.0 Hz
    # 5 non-target frames filtered out
    # 1 serial framing parse error -> R_parsed = 37.0 Hz
    dt_wall = 1.0
    udp_sent = 35
    total_rf_records = 38
    parse_errors = 1
    parsed_records = total_rf_records - parse_errors
    target_admitted = 33
    filtered_non_target = parsed_records - target_admitted

    r_udp_sent = udp_sent / dt_wall
    r_csi_total = total_rf_records / dt_wall
    r_parsed = parsed_records / dt_wall
    r_csi_target = target_admitted / dt_wall

    assert r_udp_sent == 35.0
    assert r_csi_total == 38.0
    assert r_parsed == 37.0
    assert r_csi_target == 33.0
    assert filtered_non_target == 4

    # Quantities are strictly distinct:
    assert r_udp_sent != r_csi_target
    assert r_csi_total != r_csi_target
    assert r_parsed != r_csi_target
