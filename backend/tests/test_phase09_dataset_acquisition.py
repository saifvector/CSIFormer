import os
import sys
import json
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.schemas import CSIPacketFrame
from app.services.packet_validator import packet_validator, PacketValidatorEngine
from app.services.data_quality_analyzer import data_quality_analyzer, DataQualityAnalyzer
from app.services.dataset_session_manager import dataset_session_manager, DatasetSessionManager, CLASS_FOLDER_MAP

def test_dataset_directory_hierarchy():
    """Validates automatic creation and integrity of all 12 dataset directories."""
    print("Testing Phase 09: Dataset Directory Hierarchy Initialization...")
    dataset_session_manager.init_directories()
    root = dataset_session_manager.root_dir

    expected_subfolders = [
        "empty_room", "standing", "sitting", "walking",
        "running", "falling", "lying_down", "multiperson",
        "metadata", "sessions", "exports", "reports"
    ]

    for sub in expected_subfolders:
        dir_path = os.path.join(root, sub)
        assert os.path.exists(dir_path), f"Missing dataset directory: {dir_path}"
        assert os.path.isdir(dir_path), f"Path is not a directory: {dir_path}"
    print("PASSED: 12/12 Dataset directories verified on disk!")

def test_packet_validator_engine():
    """Validates structural validation, corruption rejection, and sequence continuity tracking."""
    print("Testing Phase 09: PacketValidatorEngine...")
    validator = PacketValidatorEngine(expected_subcarriers=64)
    validator.reset_node_state()

    # 1. Valid Frame
    valid_frame = CSIPacketFrame(
        node_id="esp32-rx-01",
        sequence=100,
        timestamp=1700000000.0,
        subcarrier_count=64,
        amplitudes=[15.0] * 64,
        phases=[0.1] * 64,
        rssi=-52,
        noise_floor=-95,
        snr=43
    )
    res_valid = validator.validate_frame(valid_frame)
    assert res_valid.is_valid is True
    assert res_valid.dropped_packets_detected == 0

    # 2. Sequence Continuity & Drop Detection (skip from seq 100 to seq 105 -> 4 dropped packets)
    gap_frame = CSIPacketFrame(
        node_id="esp32-rx-01",
        sequence=105,
        timestamp=1700000000.16,
        subcarrier_count=64,
        amplitudes=[15.0] * 64,
        phases=[0.1] * 64,
        rssi=-52,
        noise_floor=-95,
        snr=43
    )
    res_gap = validator.validate_frame(gap_frame)
    assert res_gap.is_valid is True
    assert res_gap.dropped_packets_detected == 4

    # 3. Invalid Subcarrier Length (e.g. 32 instead of 64)
    short_frame = CSIPacketFrame(
        node_id="esp32-rx-01",
        sequence=106,
        timestamp=1700000000.20,
        subcarrier_count=32,
        amplitudes=[15.0] * 32,
        phases=[0.1] * 32,
        rssi=-52,
        noise_floor=-95,
        snr=43
    )
    res_short = validator.validate_frame(short_frame)
    assert res_short.is_valid is False
    assert "INVALID_SUBCARRIER_LENGTH" in res_short.error_type

    # 4. Corrupted NaN / Infinite Value Frame
    nan_frame = CSIPacketFrame(
        node_id="esp32-rx-01",
        sequence=107,
        timestamp=1700000000.23,
        subcarrier_count=64,
        amplitudes=[float("nan")] * 64,
        phases=[0.1] * 64,
        rssi=-52,
        noise_floor=-95,
        snr=43
    )
    res_nan = validator.validate_frame(nan_frame)
    assert res_nan.is_valid is False
    assert "CORRUPT_AMPLITUDE_VALUE" in res_nan.error_type

    summary = validator.get_integrity_summary()
    assert summary["total_validated"] == 4
    assert summary["total_valid"] == 2
    assert summary["total_corrupted"] == 2
    assert summary["total_dropped"] == 4
    print("PASSED: PacketValidatorEngine correctly verified valid, dropped, and corrupted frames!")

def test_data_quality_analyzer():
    """Validates DataQualityAnalyzer metrics, packet loss rate, and composite scoring."""
    print("Testing Phase 09: DataQualityAnalyzer...")
    analyzer = DataQualityAnalyzer()
    analyzer.start_session_monitoring("TEST_QUALITY_SES", 1700000000.0)
    validator = PacketValidatorEngine(expected_subcarriers=64)

    # Stream 30 valid frames with realistic SNR variability
    for i in range(30):
        frame = CSIPacketFrame(
            node_id="esp32-rx-01",
            sequence=i,
            timestamp=1700000000.0 + (i * 0.033),
            subcarrier_count=64,
            amplitudes=[15.0 + np.sin(i * 0.2)] * 64,
            phases=[0.05 * j for j in range(64)],
            rssi=-50 + (i % 3),
            noise_floor=-95,
            snr=45 + (i % 2)
        )
        val = validator.validate_frame(frame)
        analyzer.process_frame_metrics(frame, val)

    report = analyzer.compute_quality_report("TEST_QUALITY_SES")
    assert report.total_frames_received == 30
    assert report.valid_frames_count == 30
    assert report.corrupted_frames_count == 0
    assert report.dropped_packets_count == 0
    assert report.packet_loss_pct == 0.0
    assert report.frame_completeness_pct == 100.0
    assert report.composite_quality_score >= 85.0
    assert report.quality_level in ["Excellent", "Good"]
    print(f"PASSED: DataQualityAnalyzer generated valid score {report.composite_quality_score}% ({report.quality_level})!")

def test_dataset_session_manager_lifecycle_and_multiformat_export():
    """Validates full session lifecycle (start, pause, resume, stop) and CSV, JSON, NPY multi-format persistence."""
    print("Testing Phase 09: DatasetSessionManager Lifecycle & Multi-Format Serialization...")
    
    # 1. Start Session
    start_res = dataset_session_manager.start_session(
        activity_class="Walking",
        subject_id="UnitTestSubject",
        room_name="Acoustic Lab 2",
        room_size="10m x 8m x 3.5m",
        router_id="Router-TX-01",
        notes="Automated Phase 09 Verification Session"
    )
    assert start_res["status"] == "started"
    sid = start_res["session_id"]
    assert "walking" in sid.lower()

    # 2. Record Valid Frames
    for seq in range(10):
        frame = CSIPacketFrame(
            node_id="esp32-rx-01",
            sequence=seq,
            timestamp=1700000000.0 + (seq * 0.033),
            subcarrier_count=64,
            amplitudes=[14.0 + (seq * 0.2)] * 64,
            phases=[0.02 * j for j in range(64)],
            rssi=-51,
            noise_floor=-94,
            snr=43
        )
        dataset_session_manager.record_frame(
            frame,
            target_x=4.2,
            target_y=3.1,
            target_z=1.0,
            zone="Workspace Area",
            speed_ms=1.1
        )

    # 3. Test Pause and Resume
    pause_res = dataset_session_manager.pause_session()
    assert pause_res["status"] == "paused"
    assert dataset_session_manager.is_paused is True

    resume_res = dataset_session_manager.resume_session()
    assert resume_res["status"] == "resumed"
    assert dataset_session_manager.is_paused is False

    # 4. Stop Session & Export Multi-Format
    stop_res = dataset_session_manager.stop_session()
    assert stop_res["status"] == "completed"
    assert stop_res["session_id"] == sid
    assert stop_res["frame_count"] == 10
    assert stop_res["composite_quality_score"] > 80.0

    files = stop_res["files"]
    assert os.path.exists(files["json"]), f"Missing JSON export: {files['json']}"
    assert os.path.exists(files["csv"]), f"Missing CSV export: {files['csv']}"
    assert os.path.exists(files["npy"]), f"Missing NPY export: {files['npy']}"
    assert os.path.exists(files["metadata"]), f"Missing metadata export: {files['metadata']}"

    # 5. Verify Content of CSV
    with open(files["csv"], "r") as f:
        lines = f.readlines()
        assert len(lines) == 11 # Header + 10 rows
        assert "timestamp,node_id,sequence" in lines[0]
        assert "amp_0" in lines[0] and "phase_63" in lines[0]

    # 6. Verify Content of JSON
    with open(files["json"], "r") as f:
        json_data = json.load(f)
        assert len(json_data) == 10
        assert json_data[0]["activity_label"] == "Walking"
        assert json_data[0]["subject_id"] == "UnitTestSubject"

    # 7. Verify Content of NumPy Tensor (.npy)
    npy_tensor = np.load(files["npy"])
    assert npy_tensor.shape == (10, 64, 2), f"Expected tensor shape (10, 64, 2), got {npy_tensor.shape}"
    assert npy_tensor.dtype == np.float32

    print("PASSED: Multi-Format Serialization (.csv, .json, .npy) verified with 100% integrity!")

def test_dataset_analytics_dashboard_and_readiness_report():
    """Validates real disk scanning, class balance %, and research readiness reporting."""
    print("Testing Phase 09: Dataset Analytics Dashboard & Research Readiness Report...")
    
    stats = dataset_session_manager.get_dataset_statistics()
    assert stats["total_recordings"] >= 1
    assert stats["total_frames"] >= 10
    assert stats["total_storage_bytes"] > 0
    assert "class_distribution" in stats
    assert "Walking" in stats["class_distribution"]

    report = dataset_session_manager.generate_research_readiness_report()
    assert "readiness_level" in report
    assert "readiness_score_pct" in report
    assert "recommendations" in report
    assert len(report["recommendations"]) >= 1

    print(f"PASSED: Analytics & Readiness Report verified (Readiness: {report['readiness_level']})!")

if __name__ == "__main__":
    test_dataset_directory_hierarchy()
    test_packet_validator_engine()
    test_data_quality_analyzer()
    test_dataset_session_manager_lifecycle_and_multiformat_export()
    test_dataset_analytics_dashboard_and_readiness_report()
    print("ALL PHASE 09 DATASET ACQUISITION TESTS PASSED WITH 100% SUCCESS!")
