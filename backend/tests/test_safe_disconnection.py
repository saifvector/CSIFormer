"""
CSIFormer — Safe ESP32-S3 Disconnection & Recording Finalization Unit Tests.

Covers:
1. Normal recording completion, atomic file saving, validation gate, and port release.
2. Graceful KeyboardInterrupt handling (frames preserved, invalid/unconfirmed not indexed).
3. Serial disconnection / USB physical removal during active acquisition.
4. File-write / disk finalization failure (port released safely regardless).
5. Validation failure gate (corrupted/empty recording prevented from manifest indexing).
6. Manifest update failure (graceful error handling without session corruption).
7. Repeated cleanup calls (idempotence of stop_session, disconnect, safe_shutdown).
8. Background thread termination and serial port release verification.
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "backend"))

from app.services.real_csi_collector import RealCSICollector
from app.services.collection_workflow import CollectionWorkflowManager
from app.services.session_validator import DatasetIntegrityValidator, SessionValidationError


# =============================================================================
# 1. Normal Recording Completion & Safe Cleanup
# =============================================================================
def test_normal_recording_completion_and_cleanup():
    """Verify standard recording finalization, validation, indexing, and serial release."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        # Mock serial connection
        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        # Start session
        start_res = manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory",
            duration_seconds=4.0
        )
        assert start_res["status"] == "recording_active"

        # Inject 60 valid frames
        manager.collector.inject_synthetic_burst(activity="walk", num_frames=60)

        # Perform safe shutdown with confirmed ground truth
        report = manager.safe_shutdown(confirmed=True, split="train")

        assert report["status"] == "shutdown_complete"
        assert report["recording_stopped"] is True
        assert report["session_files_finalized"] is True
        assert report["frame_count"] == 60
        assert report["validation_passed"] is True
        assert report["manifest_updated"] is True
        assert report["serial_port_released"] is True
        assert report["safe_to_disconnect_usb"] is True

        # Verify disk artifacts
        json_file = Path(report["json_path"])
        csv_file = Path(report["csv_path"])
        assert json_file.exists()
        assert csv_file.exists()

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["frames"]) == 60
        assert data["metadata"]["ground_truth_confirmed"] is True
        assert data["metadata"]["ground_truth_activity"] == "walk"

        # Verify manifest
        manifest_file = tmp_path / "dataset_manifest.json"
        assert manifest_file.exists()
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        assert len(manifest["sessions"]) == 1
        assert manifest["sessions"][0]["session_id"] == report["session_id"]
        assert manifest["sessions"][0]["packet_count"] == 60


# =============================================================================
# 2. Keyboard Interruption During Recording
# =============================================================================
def test_keyboard_interruption_during_recording():
    """Verify KeyboardInterrupt preserves captured frames, skips manifest indexing, and frees port."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory",
            duration_seconds=4.0
        )

        # Injected 30 frames before operator aborts
        manager.collector.inject_synthetic_burst(activity="walk", num_frames=30)

        # Operator triggers Ctrl+C (confirmed=None)
        report = manager.safe_shutdown(confirmed=None, notes="Interrupted by operator")

        assert report["recording_stopped"] is True
        assert report["session_files_finalized"] is True
        assert report["frame_count"] == 30
        assert report["manifest_updated"] is False
        assert report["serial_port_released"] is True
        assert report["safe_to_disconnect_usb"] is True

        # Frames are preserved on disk
        json_file = Path(report["json_path"])
        assert json_file.exists()
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["frames"]) == 30

        # Manifest is NOT updated for unconfirmed / aborted trial
        manifest_file = tmp_path / "dataset_manifest.json"
        assert not manifest_file.exists()


# =============================================================================
# 3. Serial Disconnection During Acquisition
# =============================================================================
def test_serial_disconnection_during_acquisition():
    """Verify hardware detachment / SerialException triggers clean worker shutdown."""
    collector = RealCSICollector(port="COM99", auto_connect=False)
    mock_serial = MagicMock()
    mock_serial.is_open = True

    # Simulate read error on disconnection
    import serial
    mock_serial.read.side_effect = serial.SerialException("USB device detached")
    collector.serial_handle = mock_serial
    collector.is_connected = True

    collector.start_streaming()
    assert collector.is_streaming is True

    # Give thread a slice to encounter exception
    time.sleep(0.1)

    # Disconnect must cleanly terminate thread and report port released
    released = collector.disconnect()
    assert released is True
    assert collector.is_port_released() is True
    assert collector.is_streaming is False
    assert collector.diagnostic_state == "SERIAL_DISCONNECTED"


# =============================================================================
# 4. File-Write or Finalization Failure
# =============================================================================
def test_file_write_finalization_failure():
    """Verify that file write errors are captured gracefully and serial port is still released."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory"
        )
        manager.collector.inject_synthetic_burst(activity="walk", num_frames=10)

        # Force write failure by pointing data_dir to an invalid non-directory path
        invalid_path = tmp_path / "not_a_dir"
        with open(invalid_path, "w") as f:
            f.write("blocking file")
        manager.collector.data_dir = invalid_path / "sub"

        report = manager.safe_shutdown(confirmed=True)

        assert report["session_files_finalized"] is False
        assert report["manifest_updated"] is False
        assert report["serial_port_released"] is True
        assert report["safe_to_disconnect_usb"] is True


# =============================================================================
# 5. Validation Failure Prevents Manifest Indexing
# =============================================================================
def test_validation_failure_prevents_manifest_indexing():
    """Verify that an empty or corrupt session (0 frames) fails validation and is not indexed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory"
        )
        # 0 frames recorded

        report = manager.safe_shutdown(confirmed=True)

        assert report["session_files_finalized"] is True
        assert report["frame_count"] == 0
        assert report["validation_passed"] is False
        assert "0 frames" in str(report["validation_error"])
        assert report["manifest_updated"] is False
        assert report["serial_port_released"] is True
        assert report["safe_to_disconnect_usb"] is True

        manifest_file = tmp_path / "dataset_manifest.json"
        assert not manifest_file.exists()


# =============================================================================
# 6. Manifest Update Failure Handled Gracefully
# =============================================================================
def test_manifest_update_failure_handled_gracefully():
    """Verify that a corrupt or unwriteable manifest does not crash or corrupt session files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory"
        )
        manager.collector.inject_synthetic_burst(activity="walk", num_frames=55)

        # Write corrupt JSON into dataset_manifest.json
        manifest_file = tmp_path / "dataset_manifest.json"
        with open(manifest_file, "w") as f:
            f.write("CORRUPT_NOT_VALID_JSON{[[")

        report = manager.safe_shutdown(confirmed=True)

        assert report["session_files_finalized"] is True
        assert report["frame_count"] == 55
        assert report["manifest_updated"] is False
        assert report["serial_port_released"] is True
        assert report["safe_to_disconnect_usb"] is True


# =============================================================================
# 7. Repeated Cleanup Calls Idempotence
# =============================================================================
def test_repeated_cleanup_calls_idempotence():
    """Verify calling stop_session, disconnect, and safe_shutdown repeatedly is safe."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        manager = CollectionWorkflowManager(port="COM99", data_dir=tmp_path)

        mock_serial = MagicMock()
        mock_serial.is_open = True
        manager.collector.serial_handle = mock_serial
        manager.collector.is_connected = True
        manager.collector.csi_packets_parsed = 1
        manager.collector.connect = MagicMock(return_value=True)

        manager.start_session(
            participant_id="Participant_03",
            activity_label="walk",
            room_type="Laboratory"
        )
        manager.collector.inject_synthetic_burst(activity="walk", num_frames=55)

        # Stop session call 1
        res1 = manager.stop_session()
        assert res1["frame_count"] == 55
        json_p = res1["json_path"]

        # Stop session call 2 (idempotent: does NOT overwrite paths with None or frames with 0)
        res2 = manager.stop_session()
        assert res2["frame_count"] == 55
        assert res2["json_path"] == json_p
        assert res2.get("already_stopped") is True

        # Disconnect call 1, 2, 3
        assert manager.collector.disconnect() is True
        assert manager.collector.disconnect() is True
        assert manager.collector.disconnect() is True

        # Safe shutdown call 1
        rep1 = manager.safe_shutdown(confirmed=True)
        assert rep1["status"] == "shutdown_complete"
        assert rep1["manifest_updated"] is True

        # Safe shutdown call 2
        rep2 = manager.safe_shutdown(confirmed=True)
        assert rep2["status"] == "shutdown_complete"

        # Manifest must have exactly 1 entry, not duplicated
        with open(tmp_path / "dataset_manifest.json", "r") as f:
            manifest = json.load(f)
        assert len(manifest["sessions"]) == 1


# =============================================================================
# 8. Serial Port Release and Background Thread Termination
# =============================================================================
def test_serial_port_release_and_thread_termination():
    """Verify is_port_released reflects true thread and handle state."""
    collector = RealCSICollector(port="COM99", auto_connect=False)

    # Initial idle state
    assert collector.is_port_released() is True

    # Connected state
    mock_serial = MagicMock()
    mock_serial.is_open = True
    collector.serial_handle = mock_serial
    collector.is_connected = True
    assert collector.is_port_released() is False

    # Streaming state
    collector.start_streaming()
    assert collector.is_port_released() is False
    assert collector.is_streaming is True

    # Stop streaming
    collector.stop_streaming()
    assert collector.is_streaming is False
    # Serial handle is still open
    assert collector.is_port_released() is False

    # Disconnect
    released = collector.disconnect()
    assert released is True
    assert collector.is_port_released() is True
    assert mock_serial.close.called
