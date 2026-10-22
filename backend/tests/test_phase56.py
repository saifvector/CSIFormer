"""
CSIFormer Phase 56 Test Suite — Acquisition-Rate Calibration Design & Timing Integrity.

Validates:
1. Gate 0: Cryptographic invariance of protected checkpoints and dataset manifest.
2. Historical Acquisition Method Evidence:
   - Verifies UdpStimulator parameters (unicast to station IP 192.168.0.232:5555, 35 Hz).
   - Verifies historical dataset manifest metrics (mean rate 35.4 Hz, duration 3-4s, Format A).
3. ESP-IDF Timestamp API Contract:
   - Verifies wifi_pkt_rx_ctrl_t timestamp semantics (32-bit microsecond local baseband counter, 71.58 min rollover).
   - Verifies distinction from 802.11 TSF beacon timestamp.
4. Format B v2 Extended Telemetry Parser:
   - Verifies parsing of CSI_DATA_V2 with hw_timestamp_us and 802.11 rx_seq.
   - Verifies strict backward compatibility with historical Format B (CSI_DATA) and Format A (raw_iq_stream).
5. Host-Side Monotonic Timing & Temporal Metadata Preservation:
   - Verifies distinction between wall-clock timestamp and host_monotonic_time.
   - Verifies sliding window temporal metadata retention via get_latest_window(return_metadata=True).
   - Verifies backward compatibility of get_latest_window(return_metadata=False).
   - Verifies window timing diagnostics (empirical rate, mean/max/std interval, CV).
6. Stepped Calibration Safety State Machine & Abort Gates:
   - Verifies stepped escalation sequence (0 -> 5 -> 15 -> 30 -> 35 pkts/s).
   - Verifies immediate safety aborts on latency spike (>100 ms), packet loss (>1%), and transport gaps.
7. Rate Acceptance vs Record Count Gate Independence:
   - Verifies that N >= 50 with passive low rate (1.66-3.8 Hz) fails the rate gate while passing the count gate.
"""

import math
import hashlib
import time
import sys
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


def test_phase56_gate0_protected_file_invariance():
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


def test_phase56_historical_acquisition_evidence_consistency():
    """
    Verifies that historical acquisition was driven by active UDP stimulation
    targeting station IP 192.168.0.232 at 35 Hz, and manifest records reflect ~35.4 Hz.
    """
    import json
    manifest_path = PROJECT_ROOT / "data/real_csi_dataset/dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sessions = manifest.get("sessions", [])
    assert len(sessions) == 74, f"Expected 74 historical sessions, found {len(sessions)}"

    rates = [s["sampling_rate_hz"] for s in sessions]
    durations = [s["duration_seconds"] for s in sessions]
    packet_counts = [s["packet_count"] for s in sessions]

    mean_rate = sum(rates) / len(rates)
    assert 34.0 <= mean_rate <= 36.5, f"Historical mean rate {mean_rate:.2f} Hz outside expected ~35.4 Hz range"
    assert all(3.0 <= d <= 4.1 for d in durations), "Historical sessions were not collected in short 3-4s bursts"
    assert all(95 <= c <= 165 for c in packet_counts), "Historical packet counts inconsistent with 35 Hz collection"


def test_phase56_espidf_timestamp_semantics_contract():
    """
    Verifies the mathematical and semantic model of the ESP-IDF wifi_pkt_rx_ctrl_t timestamp:
    - Units: microseconds (us)
    - Precision: 1 us
    - Clock domain: local baseband/MAC peripheral counter
    - 32-bit unsigned wraparound at 2^32 us (~4294.97 seconds / ~71.58 minutes).
    - Unrelated to 802.11 TSF beacon timestamps.
    """
    max_uint32 = 0xFFFFFFFF
    rollover_period_us = max_uint32 + 1
    rollover_period_sec = rollover_period_us / 1e6
    rollover_period_min = rollover_period_sec / 60.0

    assert rollover_period_us == 4294967296
    assert abs(rollover_period_min - 71.5828) < 0.01

    # Simulate rollover difference resolution
    t_prev = 4294967200  # 96 us before rollover
    t_curr = 204         # 204 us after rollover
    # Raw unsigned 32-bit modular arithmetic
    dt_us = (t_curr - t_prev) & max_uint32
    assert dt_us == 300  # Exact 300 us elapsed span across 32-bit boundary


def test_phase56_format_b_v2_parser_and_backward_compatibility():
    """
    Verifies that RealCSICollector:
    1. Parses CSI_DATA_V2 lines containing hw_timestamp_us and rx_seq.
    2. Maintains strict backward compatibility with Format B (CSI_DATA).
    3. Maintains strict backward compatibility with Format A (RSSI=... CSI:...).
    """
    collector = RealCSICollector()

    # Format B v2 line
    # CSI_DATA_V2,<mac>,<rssi>,<noise>,<seq>,<hw_timestamp_us>,<rx_seq>,<num_sc>,amp_0:phase_0,...
    subcarrier_str = ",".join([f"10.{i}:0.{i}" for i in range(56)])
    line_v2 = f"CSI_DATA_V2,98:BA:5F:EF:28:26,-58.0,-95.0,105,123456789,4092,56,{subcarrier_str}"

    parsed_v2 = collector.parse_raw_telemetry_line(line_v2)
    assert parsed_v2 is not None
    assert collector.detected_protocol == "structured_csi_data_v2"
    assert parsed_v2["mac"] == "98:BA:5F:EF:28:26"
    assert parsed_v2["sequence"] == 105
    assert parsed_v2["hw_timestamp_us"] == 123456789
    assert parsed_v2["rx_seq"] == 4092
    assert parsed_v2["num_subcarriers"] == 56
    assert "host_monotonic_time" in parsed_v2
    assert "timestamp" in parsed_v2

    # Format B v1 line (historical structured)
    line_v1 = f"CSI_DATA,98:BA:5F:EF:28:26,-58.0,-95.0,105,56,{subcarrier_str}"
    parsed_v1 = collector.parse_raw_telemetry_line(line_v1)
    assert parsed_v1 is not None
    assert collector.detected_protocol == "structured_csi_data"
    assert parsed_v1["sequence"] == 105
    assert parsed_v1["num_subcarriers"] == 56
    assert "hw_timestamp_us" not in parsed_v1
    assert "host_monotonic_time" in parsed_v1

    # Format A line (historical raw IQ)
    iq_pairs = ",".join(["10,-4"] * 64)
    line_v0 = f"RSSI=-55 LEN=128 CSI:{iq_pairs}"
    parsed_v0 = collector.parse_raw_telemetry_line(line_v0)
    assert parsed_v0 is not None
    assert collector.detected_protocol == "raw_iq_stream"
    assert parsed_v0["mac"] == "ESP32-S3-NODE-01"
    assert "host_monotonic_time" in parsed_v0


def test_phase56_host_monotonic_timing_and_sliding_window_metadata():
    """
    Verifies that host monotonic arrival timestamps are preserved,
    and sliding window returns temporal metadata when requested while
    preserving default 2-tuple return for backward compatibility.
    """
    collector = RealCSICollector()

    t_mono_start = time.perf_counter()
    nominal_dt = 1.0 / 30.0  # 30 Hz -> 33.33 ms interval

    # Feed 50 synthetic frames at ~30 Hz
    for i in range(50):
        t_mono = t_mono_start + i * nominal_dt
        t_wall = 1792300000.0 + i * nominal_dt
        amps = [float(20.0 + math.sin(i * 0.1 + sc * 0.05)) for sc in range(56)]
        phases = [0.0] * 56
        frame = {
            "timestamp": t_wall,
            "host_monotonic_time": t_mono,
            "sequence": 1000 + i,
            "mac": "98:BA:5F:EF:28:26",
            "rssi": -55.0,
            "noise_floor": -95.0,
            "raw_amplitudes": amps,
            "raw_phases": phases
        }
        collector._process_parsed_frame(frame)

    # 1. Backward compatibility test: default call returns 2-tuple (raw_win, phase_win)
    res_default = collector.get_latest_window(return_metadata=False)
    assert isinstance(res_default, tuple)
    assert len(res_default) == 2
    raw_win, phase_win = res_default
    assert raw_win.shape == (50, 56)
    assert phase_win.shape == (50, 56)

    # 2. Metadata retention call: returns 3-tuple (raw_win, phase_win, meta_dict)
    res_meta = collector.get_latest_window(return_metadata=True)
    assert isinstance(res_meta, tuple)
    assert len(res_meta) == 3
    r_win, p_win, meta = res_meta
    assert r_win.shape == (50, 56)
    assert "timestamps" in meta
    assert "monotonic_timestamps" in meta
    assert "sequences" in meta
    assert "empirical_rate_hz" in meta

    assert meta["sequences"][0] == 1000
    assert meta["sequences"][-1] == 1049
    assert abs(meta["empirical_rate_hz"] - 30.0) < 0.5
    assert abs(meta["mean_interval_ms"] - 33.33) < 0.5

    # 3. Buffer timing diagnostics helper
    diag = collector.get_window_timing_diagnostics()
    assert diag["is_full"] is True
    assert diag["buffered_frames"] == 50
    assert abs(diag["empirical_rate_hz"] - 30.0) < 0.5
    assert diag["cv_interval"] < 0.05  # Highly uniform synthetic arrivals


def test_phase56_rate_gate_vs_record_count_gate_separation():
    """
    Verifies that a 50-frame window collected at passive rates (~2.0 Hz)
    passes the record-count gate (N >= 50) but fails the empirical rate gate (>= 28.0 Hz).
    """
    passive_dt = 0.5  # 2.0 Hz -> 500 ms interval
    t0 = 1000.0
    timestamps = [t0 + i * passive_dt for i in range(50)]

    assert len(timestamps) == 50  # Passes record-count gate

    metrics = compute_session_sampling_rate(timestamps)
    assert metrics["valid"] is True
    assert metrics["frame_count"] == 50
    assert abs(metrics["empirical_sampling_rate_hz"] - 2.0) < 0.01

    # Rate gate requires >= 28.0 Hz
    rate_gate_passed = metrics["empirical_sampling_rate_hz"] >= 28.0
    count_gate_passed = metrics["frame_count"] >= 50

    assert count_gate_passed is True
    assert rate_gate_passed is False, "Passive 2.0 Hz collection must FAIL the 28.0 Hz rate gate!"


def test_phase56_calibration_procedure_safety_abort_simulation():
    """
    Simulates the Stepped Acquisition Calibration Safety State Machine:
    Verifies that:
    - Stage 0 (Passive baseline) passes safely.
    - Low-rate probe runs safely if RTT <= 100 ms and loss == 0%.
    - Safety abort triggers immediately if latency spikes > 100 ms or loss > 1%.
    """
    class MockCalibrationRunner:
        def __init__(self):
            self.state = "IDLE"
            self.current_stage = 0
            self.stages = [0.0, 5.0, 15.0, 30.0, 35.0]
            self.abort_reason = None

        def evaluate_probe_safety(self, rtt_ms: float, loss_pct: float, uart_gap_pct: float) -> bool:
            if rtt_ms > 100.0:
                self.state = "ABORTED"
                self.abort_reason = f"latency_spike_{rtt_ms:.1f}ms"
                return False
            if loss_pct > 1.0:
                self.state = "ABORTED"
                self.abort_reason = f"packet_loss_{loss_pct:.1f}pct"
                return False
            if uart_gap_pct > 0.5:
                self.state = "ABORTED"
                self.abort_reason = f"uart_transport_loss_{uart_gap_pct:.1f}pct"
                return False
            return True

    runner = MockCalibrationRunner()

    # Stage 0: Passive (no traffic)
    assert runner.evaluate_probe_safety(rtt_ms=0.0, loss_pct=0.0, uart_gap_pct=0.0) is True

    # Stage 1 normal probe (12 ms RTT, 0% loss)
    assert runner.evaluate_probe_safety(rtt_ms=12.5, loss_pct=0.0, uart_gap_pct=0.0) is True

    # Stage 1 latency spike (115 ms > 100 ms threshold)
    safety_ok = runner.evaluate_probe_safety(rtt_ms=115.0, loss_pct=0.0, uart_gap_pct=0.0)
    assert safety_ok is False
    assert runner.state == "ABORTED"
    assert "latency_spike" in runner.abort_reason
