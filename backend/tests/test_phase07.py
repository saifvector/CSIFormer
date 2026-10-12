import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.esp32_hardware_manager import esp32_hardware_manager
from app.services.experiment_manager import experiment_manager
from app.services.model_evaluator import model_evaluator

def test_esp32_hardware_manager():
    print("Testing ESP32HardwareManager Device Discovery & Packet Parser...")
    status = esp32_hardware_manager.get_hardware_status()
    assert status["connected_device_count"] >= 3
    
    # Test ESP-IDF Packet Parser
    sample_packet = "CSI_DATA,24:DC:C3:A1:01:01,-52.0,-95.0,102,64,[12.5:0.5;14.2:0.8;15.1:1.1]"
    parsed = esp32_hardware_manager.parse_csi_raw_string(sample_packet)
    assert parsed is not None
    assert parsed["mac"] == "24:DC:C3:A1:01:01"
    assert parsed["rssi"] == -52.0
    assert parsed["num_subcarriers"] == 64
    assert len(parsed["amplitudes"]) == 3
    print("PASSED: ESP32HardwareManager device status & packet parser test!")

def test_experiment_manager():
    print("Testing ExperimentSessionManager Protocols & Execution...")
    experiments = experiment_manager.list_experiments()
    assert len(experiments) >= 4
    
    # Test Experiment Lifecycle
    sess = experiment_manager.start_experiment("exp_01")
    assert sess["status"] == "recording"
    assert sess["exp_id"] == "exp_01"
    
    res = experiment_manager.stop_experiment()
    assert res["status"] == "completed"
    print("PASSED: ExperimentSessionManager workflow test!")

def test_model_evaluator():
    print("Testing HardwareModelEvaluator Real Hardware Metrics...")
    report = model_evaluator.evaluate_real_hardware_dataset()
    assert report["metrics"]["accuracy_pct"] > 95.0
    assert report["metrics"]["f1_score_pct"] >= 99.0
    assert report["metrics"]["mean_localization_error_m"] <= 0.25
    assert len(report["activity_classes"]) == 8
    print("PASSED: HardwareModelEvaluator real hardware evaluation test!")

if __name__ == "__main__":
    test_esp32_hardware_manager()
    test_experiment_manager()
    test_model_evaluator()
    print("ALL PHASE 07 ESP32 HARDWARE INTEGRATION TESTS PASSED!")
