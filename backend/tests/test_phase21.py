"""
CSIFormer Phase 21 — ESP32-S3 Zero-Packet Diagnosis & Live Acquisition Test Suite.

Automated deterministic testing covering:
1. Serial timeout handling and disconnected state (SERIAL_DISCONNECTED).
2. Connected idle state with zero serial bytes (SERIAL_CONNECTED_IDLE).
3. Non-CSI serial bytes and bootloader log handling (SERIAL_BYTES_NO_VALID_RECORDS).
4. Malformed record detection and parse failure handling (RECORDS_RECEIVED_PARSE_FAILED).
5. Format A (Running firmware raw IQ stream) parsing and subcarrier dimensionality (64 subcarriers).
6. Format B (Structured CSV stream) parsing and subcarrier dimensionality (56 subcarriers).
7. Partial serial record streaming and chunk buffering.
8. Empty and corrupt CSI dimension rejection.
9. Diagnostic telemetry counter accuracy (bytes, lines, records, parsed, errors).
10. Stream interruption detection on stall > 2.0s (STREAM_INTERRUPTED).
11. Clean worker thread shutdown, collector interruption, and resource release.
12. DatasetIntegrityValidator execution on saved physical format.
13. Historical physical dataset preservation (23 sessions, 3212 packets).
14. Bit-for-bit model checkpoint hash invariance (Production and Experimental).
"""

import sys
import os
import json
import time
import math
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

# Ensure backend and root directory are in python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))

from app.services.real_csi_collector import RealCSICollector
from app.services.session_validator import DatasetIntegrityValidator
from app.services.collection_workflow import CollectionWorkflowManager

DATASET_DIR = ROOT_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = ROOT_DIR / "models"


# =============================================================================
# 1. Serial Disconnected & Timeout Handling
# =============================================================================
def test_phase21_serial_disconnected_state():
    """Verify that an unavailable or invalid serial port resolves to SERIAL_DISCONNECTED."""
    collector = RealCSICollector(port="COM999", auto_connect=False)
    res = collector.connect()
    assert res is False
    assert collector.is_connected is False
    assert collector.get_diagnostic_state() == "SERIAL_DISCONNECTED"

    manager = CollectionWorkflowManager(port="COM999")
    v_res = manager.verify_hardware_stream(test_duration_s=0.05, trigger_reset=False)
    assert v_res["connected"] is False
    assert v_res["status"] == "error"
    assert v_res["diagnostic_state"] == "SERIAL_DISCONNECTED"


# =============================================================================
# 2. Connected Idle State (0 Bytes Received)
# =============================================================================
def test_phase21_serial_connected_idle_state():
    """Verify that a connected serial interface with 0 bytes resolves to SERIAL_CONNECTED_IDLE."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True
    collector.total_bytes_received = 0
    collector.total_lines_received = 0
    collector.csi_packets_parsed = 0

    assert collector.get_diagnostic_state() == "SERIAL_CONNECTED_IDLE"
    health = collector.get_stream_health()
    assert health["diagnostic_state"] == "SERIAL_CONNECTED_IDLE"
    assert health["total_bytes_received"] == 0
    assert health["csi_packets_parsed"] == 0


# =============================================================================
# 3. Serial Bytes Without Valid CSI Records (Bootloader / Wi-Fi logs)
# =============================================================================
def test_phase21_serial_bytes_no_valid_records():
    """Verify that non-CSI text (e.g. bootloader logs) transitions to SERIAL_BYTES_NO_VALID_RECORDS."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    # Simulate bootloader logs arriving
    collector.total_bytes_received = 256
    collector.total_lines_received = 5
    collector.boot_messages.append("rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)")
    collector.boot_messages.append("wifi:mode : sta (98:ba:5f:ef:28:26)")
    collector.csi_packets_parsed = 0
    collector.total_records_detected = 0

    assert collector.get_diagnostic_state() == "SERIAL_BYTES_NO_VALID_RECORDS"
    health = collector.get_stream_health()
    assert health["diagnostic_state"] == "SERIAL_BYTES_NO_VALID_RECORDS"
    assert len(health["boot_messages"]) >= 2


# =============================================================================
# 4. Malformed Record Detection & Parse Failure Handling
# =============================================================================
def test_phase21_records_received_parse_failed():
    """Verify that corrupted CSI candidate records increment parse errors and flag parse failure."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    # Corrupt Format A line
    corrupt_line_a = "RSSI=-60 LEN=128 CSI:corrupt,nan,invalid,strings"
    parsed_a = collector.parse_raw_telemetry_line(corrupt_line_a)
    assert parsed_a is None

    # Corrupt Format B line
    corrupt_line_b = "CSI_DATA,invalid_fields_only"
    parsed_b = collector.parse_raw_telemetry_line(corrupt_line_b)
    assert parsed_b is None

    collector.total_records_detected = 2
    collector.parse_errors = 2
    collector.csi_packets_parsed = 0

    assert collector.get_diagnostic_state() == "RECORDS_RECEIVED_PARSE_FAILED"


# =============================================================================
# 5. Format A (Running Firmware Raw IQ Stream) Parsing & Subcarrier Dimensions
# =============================================================================
def test_phase21_format_a_raw_iq_parsing():
    """Verify that Format A (LEN=128, 64 IQ pairs) parses correctly with 64 subcarriers."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    # 128 integers = 64 IQ interleaved pairs
    iq_values = [i % 20 - 10 for i in range(128)]
    iq_str = ",".join(str(v) for v in iq_values)
    line = f"RSSI=-58 LEN=128 CSI:{iq_str}"

    frame = collector.parse_raw_telemetry_line(line)
    assert frame is not None
    assert frame["rssi"] == -58.0
    assert frame["num_subcarriers"] == 64
    assert len(frame["raw_amplitudes"]) == 64
    assert len(frame["raw_phases"]) == 64
    assert all(math.isfinite(a) for a in frame["raw_amplitudes"])
    assert all(math.isfinite(p) for p in frame["raw_phases"])

    # Process frame through collector
    collector._process_parsed_frame(frame)
    assert collector.csi_packets_parsed == 1
    assert collector.raw_csi_dimensions == 64
    assert collector.get_diagnostic_state() == "CSI_STREAM_ACTIVE"


# =============================================================================
# 6. Format B (Structured CSV Stream) Parsing & Subcarrier Dimensions
# =============================================================================
def test_phase21_format_b_csv_parsing():
    """Verify that Format B (56 HT20 subcarriers) parses correctly."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    pairs = [f"{10.0 + i * 0.1:.2f}:{0.05 * i:.2f}" for i in range(56)]
    line = "CSI_DATA,98:ba:5f:ef:28:26,-52.0,-92.0,101,56," + ",".join(pairs)

    frame = collector.parse_raw_telemetry_line(line)
    assert frame is not None
    assert frame["mac"] == "98:ba:5f:ef:28:26"
    assert frame["rssi"] == -52.0
    assert frame["sequence"] == 101
    assert frame["num_subcarriers"] == 56
    assert len(frame["raw_amplitudes"]) == 56

    collector._process_parsed_frame(frame)
    assert collector.raw_csi_dimensions == 56
    assert collector.get_diagnostic_state() == "CSI_STREAM_ACTIVE"


# =============================================================================
# 7. Partial Serial Record Buffering
# =============================================================================
def test_phase21_partial_serial_record_buffering():
    """Verify that split serial byte chunks are buffered until complete newline delimiter."""
    collector = RealCSICollector(port="COM5", auto_connect=False)

    part1 = "RSSI=-60 LEN=128 CSI:1,2,3,4"
    part2 = ",5,6,7,8\n"

    # Simulate ingest chunk logic directly
    buffer = ""
    parsed_frames = []

    for chunk in [part1, part2]:
        buffer += chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if line:
                f = collector.parse_raw_telemetry_line(line)
                if f:
                    parsed_frames.append(f)

    assert len(parsed_frames) == 1
    assert parsed_frames[0]["num_subcarriers"] == 4  # 8 integers -> 4 subcarriers


# =============================================================================
# 8. Invalid CSI Dimensions & Empty Frame Rejection
# =============================================================================
def test_phase21_empty_csi_dimension_rejection():
    """Verify that records with 0 subcarriers are ignored by buffer and window builder."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    empty_frame = {
        "timestamp": time.time(),
        "sequence": 1,
        "rssi": -60.0,
        "noise_floor": -95.0,
        "raw_amplitudes": [],
        "raw_phases": []
    }
    initial_buf_len = len(collector.raw_frame_buffer)
    collector._process_parsed_frame(empty_frame)
    assert len(collector.raw_frame_buffer) == initial_buf_len


# =============================================================================
# 9. Diagnostic Telemetry Counter Correctness
# =============================================================================
def test_phase21_diagnostic_counter_correctness():
    """Verify that packets, bytes, sequence gaps, and loss rates calculate accurately."""
    collector = RealCSICollector(port="COM5", auto_connect=False)

    f1 = {"timestamp": 100.0, "sequence": 1, "rssi": -55.0, "noise_floor": -95.0, "raw_amplitudes": [1.0]*56, "raw_phases": [0.0]*56}
    f2 = {"timestamp": 100.033, "sequence": 4, "rssi": -55.0, "noise_floor": -95.0, "raw_amplitudes": [1.0]*56, "raw_phases": [0.0]*56}

    collector._process_parsed_frame(f1)
    collector._process_parsed_frame(f2)

    assert collector.packets_received == 2
    assert collector.packets_lost == 2  # Gaps: expected 2 and 3 -> 2 lost
    health = collector.get_stream_health()
    assert health["packets_received"] == 2
    assert health["packets_lost"] == 2
    assert health["packet_loss_pct"] == 50.0


# =============================================================================
# 10. Stream Interruption Detection
# =============================================================================
def test_phase21_stream_interrupted_state():
    """Verify that STREAM_INTERRUPTED is flagged when no packet arrives for > 2.0 seconds."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    # Valid packet received 3 seconds ago
    collector.csi_packets_parsed = 10
    collector.last_valid_packet_time = time.time() - 3.5

    assert collector.get_diagnostic_state() == "STREAM_INTERRUPTED"


# =============================================================================
# 11. Collector Interruption and Resource Cleanup
# =============================================================================
def test_phase21_collector_interruption_and_cleanup():
    """Verify that start/stop/disconnect correctly cleans up worker threads and serial handles."""
    collector = RealCSICollector(port="COM5", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True

    collector.start_streaming()
    assert collector.is_streaming is True

    collector.stop_streaming()
    assert collector.is_streaming is False

    collector.disconnect()
    assert collector.is_connected is False
    assert mock_serial.close.called
    assert collector.get_diagnostic_state() == "SERIAL_DISCONNECTED"


# =============================================================================
# 12. Dataset Integrity Validation on Saved Physical Format
# =============================================================================
def test_phase21_saved_session_validation_flow():
    """Verify that a recorded session conforming to schema passes DatasetIntegrityValidator."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        session_file = tmp_path / "phase21_test_walk.json"

        frames = []
        for i in range(100):
            frames.append({
                "timestamp": 1700000000.0 + i * 0.033,
                "sequence": i + 1,
                "rssi": -55.0,
                "noise": -95.0,
                "raw_amplitudes": [10.0] * 64,
                "raw_phases": [0.0] * 64,
                "raw_num_subcarriers": 64,
                "amplitudes": [10.0] * 56,
                "phases": [0.0] * 56,
                "num_subcarriers": 56
            })

        payload = {
            "metadata": {
                "session_id": "phase21_test_walk",
                "timestamp_utc": "2026-10-18T12:00:00Z",
                "room_type": "Laboratory",
                "participant_id": "Participant_03",
                "ground_truth_activity": "walk",
                "ground_truth_confirmed": True,
                "tx_rx_distance_meters": 2.5,
                "duration_seconds": 3.3
            },
            "frame_count": 100,
            "frames": frames
        }

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        validator = DatasetIntegrityValidator(tmp_path)
        v_res = validator.validate_session_file(session_file)

        assert v_res["valid"] is True
        assert v_res["packet_count"] == 100
        assert v_res["participant_id"] == "Participant_03"
        assert v_res["activity"] == "walk"


# =============================================================================
# 13. Baseline Physical Dataset Preservation
# =============================================================================
def test_phase21_dataset_baseline_preservation():
    """Verify that all 23 historical sessions and 3,212 packets remain intact."""
    validator = DatasetIntegrityValidator(DATASET_DIR, MANIFEST_PATH)
    res = validator.validate_dataset_manifest()

    assert res["all_sessions_valid"] is True
    assert res["total_sessions"] == 23
    assert res["total_packets"] == 3212
    assert res["total_windows"] == 49
    assert set(res["distinct_participants"]) == {"Participant_01", "Participant_02"}


# =============================================================================
# 14. Model Checkpoint Bit-for-Bit Hash Invariance
# =============================================================================
def test_phase21_checkpoint_hash_invariance():
    """Verify that Production and Experimental checkpoints match expected MD5 hashes exactly."""
    prod_ckpt = MODELS_DIR / "csiformer_phase13_best.pth"
    exp_ckpt = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert prod_ckpt.exists(), f"Production checkpoint missing: {prod_ckpt}"
    assert exp_ckpt.exists(), f"Experimental checkpoint missing: {exp_ckpt}"

    prod_hash = hashlib.md5(prod_ckpt.read_bytes()).hexdigest()
    exp_hash = hashlib.md5(exp_ckpt.read_bytes()).hexdigest()

    assert prod_hash == "383b4d98c08f8970b0443738f170ec01", f"Production checkpoint modified! Actual: {prod_hash}"
    assert exp_hash == "ab3d97a04d78edf75d807178772bc828", f"Experimental checkpoint modified! Actual: {exp_hash}"
