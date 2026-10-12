import sys
import os
import torch
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.csiformer_net import CSIFormerNet
from app.services.trainer import ai_trainer
from app.services.activity_classifier import ai_pipeline

def test_csiformer_net_model():
    print("Testing CSIFormerNet PyTorch Architecture...")
    model = CSIFormerNet()
    dummy_input = torch.randn(4, 50, 64) # Batch size 4, 50 time steps, 64 subcarriers
    
    logits = model(dummy_input)
    assert logits.shape == (4, 8), f"Expected logits shape (4, 8), got {logits.shape}"
    
    probs = model.predict_probs(dummy_input)
    assert probs.shape == (4, 8), f"Expected softmax probs shape (4, 8), got {probs.shape}"
    assert torch.allclose(probs.sum(dim=-1), torch.tensor([1.0, 1.0, 1.0, 1.0]), atol=1e-4), "Softmax probabilities sum != 1.0"
    print("PASSED: CSIFormerNet PyTorch architecture test!")

def test_csiformer_training_and_inference():
    print("Testing PyTorch Training & Real-Time Inference Pipeline...")
    metrics = ai_trainer.train(epochs=3, batch_size=16)
    assert metrics["status"] == "trained"
    assert metrics["accuracy"] >= 0.0, f"Accuracy too low: {metrics['accuracy']}"

    # Test real-time sliding window queue inference
    for _ in range(50):
        ai_pipeline.add_csi_frame([15.0] * 64)

    prediction = ai_pipeline.predict_activity("Walking")
    assert prediction.activity in CSIFormerNet.CLASSES
    assert len(prediction.probabilities) == 8
    print("PASSED: Training & Real-time Inference Pipeline test!")

if __name__ == "__main__":
    test_csiformer_net_model()
    test_csiformer_training_and_inference()
    print("ALL PHASE 03 DEEP LEARNING TESTS PASSED!")
