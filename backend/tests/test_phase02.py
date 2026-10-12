import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.csi_signal_processor import csi_dsp
from app.services.dataset_recorder import dataset_recorder
from app.models.schemas import CSIPacketFrame

def test_dsp_processor():
    print("Testing DSP Signal Processor...")
    raw_amps = [12.5, 14.1, 85.0, 13.9, 14.2] + [15.0] * 59
    raw_phases = [0.1 * i for i in range(64)]

    clean_amps, clean_phases, doppler_energy = csi_dsp.process_frame(raw_amps, raw_phases)

    assert len(clean_amps) == 64
    assert len(clean_phases) == 64
    assert clean_amps[2] < 80.0, "Hampel filter failed to suppress outlier spike"
    print("PASSED: DSP Signal Processor test!")

def test_dataset_recorder():
    print("Testing Dataset Recorder & Exporter...")
    res_start = dataset_recorder.start_recording("UnitTestSession", "Walking", "Subj-Test")
    assert res_start["status"] == "started"

    for i in range(5):
        frame = CSIPacketFrame(
            node_id="test-node-01",
            sequence=i,
            timestamp=1700000000.0 + i,
            subcarrier_count=64,
            amplitudes=[10.0 + i] * 64,
            phases=[0.1 * j for j in range(64)],
            rssi=-50,
            noise_floor=-90,
            snr=40
        )
        dataset_recorder.record_frame(frame)

    status = dataset_recorder.get_recording_status()
    assert status["recorded_frames"] == 5

    res_stop = dataset_recorder.stop_recording()
    session_id = res_stop["id"]
    assert res_stop["frame_count"] == 5

    csv_output = dataset_recorder.export_csv(session_id)
    assert "timestamp,node_id,sequence" in csv_output
    assert "Walking" in csv_output
    print("PASSED: Dataset Recorder & Exporter test!")

if __name__ == "__main__":
    test_dsp_processor()
    test_dataset_recorder()
    print("ALL PHASE 02 BACKEND TESTS PASSED!")
