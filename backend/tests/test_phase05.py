import sys
import os
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.csi_multiperson_net import CSIMultiPersonNet
from app.services.multiperson_tracker import multiperson_tracker

def test_csi_multiperson_net():
    print("Testing CSIMultiPersonNet PyTorch Architecture...")
    model = CSIMultiPersonNet()
    dummy_input = torch.randn(4, 50, 64) # Batch 4, 50 time steps, 64 subcarriers
    
    count_logits, coords = model(dummy_input)
    assert count_logits.shape == (4, 5), f"Expected count logits shape (4, 5), got {count_logits.shape}"
    assert coords.shape == (4, 4, 4), f"Expected coords shape (4, 4, 4), got {coords.shape}"
    print("PASSED: CSIMultiPersonNet PyTorch test!")

def test_multiperson_tracker_engine():
    print("Testing MultiTargetTrackerEngine Persistent IDs & Data Association...")
    raw_targets = [
        (2.5, 3.1, 1.0),
        (6.8, 5.2, 1.0),
        (1.9, 1.4, 1.0)
    ]
    
    result = multiperson_tracker.update_multi_targets(raw_targets, current_simulated_act="Multiple Persons")
    assert result["person_count"] == 3
    assert result["crowd_density_pct"] == 75.0
    assert len(result["tracks"]) == 3
    
    track_ids = [t["track_id"] for t in result["tracks"]]
    assert "Track-001" in track_ids
    assert "Track-002" in track_ids
    assert "Track-003" in track_ids
    print("PASSED: MultiTargetTrackerEngine test!")

if __name__ == "__main__":
    test_csi_multiperson_net()
    test_multiperson_tracker_engine()
    print("ALL PHASE 05 MULTI-PERSON TESTS PASSED!")
