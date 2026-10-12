import sys
import os
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.csi_localization_net import CSILocalizationNet
from app.services.localization_engine import localization_engine, SpatialLocalizationEngine
from app.services.dataset_recorder import dataset_recorder
from app.models.schemas import CSIPacketFrame

def test_csi_localization_net():
    print("Testing CSILocalizationNet PyTorch Architecture...")
    model = CSILocalizationNet()
    dummy_input = torch.randn(4, 50, 64) # Batch 4, 50 time steps, 64 subcarriers
    
    out = model(dummy_input)
    assert out.shape == (4, 4), f"Expected shape (4, 4), got {out.shape}"
    
    # Verify bounds (X: 0..10, Y: 0..8, Z: 0..3.5, Conf: 0..1)
    assert torch.all(out[:, 0] >= 0.0) and torch.all(out[:, 0] <= 10.0), "X coordinate out of bounds"
    assert torch.all(out[:, 1] >= 0.0) and torch.all(out[:, 1] <= 8.0), "Y coordinate out of bounds"
    assert torch.all(out[:, 2] >= 0.0) and torch.all(out[:, 2] <= 3.5), "Z coordinate out of bounds"
    assert torch.all(out[:, 3] >= 0.0) and torch.all(out[:, 3] <= 1.0), "Confidence out of bounds"
    print("PASSED: CSILocalizationNet PyTorch test!")

def test_localization_engine():
    print("Testing SpatialLocalizationEngine Trajectory & Room Zones...")
    pos1 = localization_engine.update_raw_position(4.0, 3.0, 1.0)
    pos2 = localization_engine.update_raw_position(5.0, 4.0, 1.0)
    
    assert pos2.x > 4.0 and pos2.y > 3.0
    assert localization_engine.speed_ms >= 0.0
    assert len(localization_engine.trajectory_history) > 0
    assert pos2.zone in SpatialLocalizationEngine.ZONES
    
    heatmap = localization_engine.get_occupancy_heatmap()
    assert len(heatmap) == 20 and len(heatmap[0]) == 16, "Heatmap grid size != 20x16"
    print("PASSED: SpatialLocalizationEngine test!")

def test_dataset_recorder_expanded_schema():
    print("Testing Expanded Dataset Recorder Schema...")
    session_id = dataset_recorder.start_recording("Walking")
    dummy_frame = CSIPacketFrame(
        node_id="esp32-rx-01",
        sequence=1,
        timestamp=100.0,
        subcarrier_count=64,
        amplitudes=[15.0]*64,
        phases=[0.1]*64
    )
    dataset_recorder.record_frame(dummy_frame, target_x=4.2, target_y=3.1, target_z=1.0, zone="Workspace Area", speed=1.2)
    stats = dataset_recorder.stop_recording()
    
    assert stats["frame_count"] == 1
    assert os.path.exists(stats["file_path"])
    print("PASSED: Dataset Recorder expanded schema test!")

if __name__ == "__main__":
    test_csi_localization_net()
    test_localization_engine()
    test_dataset_recorder_expanded_schema()
    print("ALL PHASE 04 LOCALIZATION & TRACKING TESTS PASSED!")
