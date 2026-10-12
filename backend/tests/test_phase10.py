"""
Comprehensive Phase 10 Unit Test Suite.

Tests:
1. CSI Preprocessing Engine (Amplitude, Phase, Detrending, Filters, Outliers, Resampling)
2. Widar 3.0 Dataset Loader (.dat parsing, lazy loading, metadata)
3. NTU-Fi HAR Dataset Loader (.mat loading, class indexing)
4. Combined Dataset & DataLoader Collation
5. CSIFormerNet Deep Learning Architecture (Forward pass, variable lengths, multi-task, AMP, gradients)
6. Evaluation Metrics & Confusion Matrix Rendering
7. Training Engine Smoke Test & Checkpoint Export
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pytest
import torch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.services.csi_preprocessor import CSIPreprocessor
from app.datasets.widar_dataset import WidarDataset
from app.datasets.ntufi_dataset import NTUFiDataset
from app.datasets.combined_dataset import CombinedCSIDataset, collate_csi_batch, create_dataloaders
from app.models.csiformernet import CSIFormerNet
from app.evaluation.metrics import compute_classification_metrics, plot_confusion_matrix
from app.training.train import train_csiformer


class TestCSIPreprocessor:
    """Validate all signal processing operations in CSIPreprocessor."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.prep = CSIPreprocessor(target_mode="HT20", target_timesteps=50)

    def test_amplitude_and_phase_extraction(self):
        # Complex matrix: 30 subcarriers, 100 packets
        real_part = np.random.randn(100, 30)
        imag_part = np.random.randn(100, 30)
        c_mat = real_part + 1j * imag_part

        amp = self.prep.extract_amplitude(c_mat)
        phase = self.prep.extract_phase(c_mat)

        assert amp.shape == (100, 30)
        assert phase.shape == (100, 30)
        assert np.all(amp >= 0)
        assert np.all(phase >= -np.pi) and np.all(phase <= np.pi)

    def test_phase_unwrapping_and_detrending(self):
        # Generate artificial phase with 2pi jump and linear ramp
        ramp = np.linspace(-5, 15, 30)[:, None]  # (30, 1)
        phase = np.angle(np.exp(1j * ramp))      # wrapped into [-pi, pi]
        unwrapped = self.prep.unwrap_phase(phase, axis=0)
        detrended = self.prep.detrend_phase(unwrapped)

        assert detrended.shape == phase.shape
        # Slope after detrending should be close to 0
        slope = np.polyfit(np.arange(30), detrended[:, 0], 1)[0]
        assert abs(slope) < 1e-3

    def test_noise_filtering_and_outliers(self):
        # Sequence with high frequency jitter and a huge spike
        t = np.linspace(0, 1, 100)
        clean_signal = np.sin(2 * np.pi * 5 * t)[:, None]  # 5 Hz
        noisy = clean_signal + 0.5 * np.random.randn(100, 1)
        noisy[50, 0] = 50.0  # extreme outlier spike

        outlier_free = self.prep.remove_outliers(noisy)
        assert abs(outlier_free[50, 0]) < 10.0  # spike removed

        filtered = self.prep.filter_noise(outlier_free, axis=0)
        assert filtered.shape == noisy.shape

    def test_resampling_and_normalization(self):
        # Irregular length (e.g. 173 timesteps)
        data = np.random.randn(173, 56)
        resampled = self.prep.resample_time(data, target_len=50)
        assert resampled.shape == (50, 56)

        norm_z = self.prep.normalize(resampled)
        assert abs(np.mean(norm_z)) < 1e-4
        assert abs(np.std(norm_z) - 1.0) < 1e-2

    def test_sliding_window_segmentation(self):
        data = np.random.randn(125, 56)
        windows = self.prep.segment_windows(data, window_size=50, stride=25)
        # Expected windows: start 0, 25, 50, 75 (total 4 windows)
        assert len(windows) == 4
        assert windows[0].shape == (50, 56)

    def test_end_to_end_preprocessing(self):
        # Mock Intel 5300 input (T, 30, 3, 1)
        widar_mock = (np.random.randn(80, 30, 3, 1) + 1j * np.random.randn(80, 30, 3, 1)).astype(np.complex64)
        tensor_w = self.prep.preprocess_sample(widar_mock, source_type="widar3", return_torch=True)
        assert isinstance(tensor_w, torch.Tensor)
        assert tensor_w.shape == (50, 56)

        # Mock Atheros input (342, T)
        ntufi_mock = np.random.randn(342, 200).astype(np.float32)
        tensor_n = self.prep.preprocess_sample(ntufi_mock, source_type="atheros", return_torch=True)
        assert isinstance(tensor_n, torch.Tensor)
        assert tensor_n.shape == (50, 56)


class TestWidarDataset:
    """Validate Widar 3.0 PyTorch Dataset implementation."""

    def test_widar_dataset_load_and_getitem(self):
        ds = WidarDataset(split="train", max_samples=10)
        assert len(ds) == 10

        item = ds[0]
        assert "csi" in item
        assert "label" in item
        assert "subject" in item
        assert "dataset" in item
        assert item["dataset"] == "widar3"
        assert item["csi"].shape == (50, 56)
        assert 0 <= item["label"] < 6

        stats = ds.get_dataset_stats()
        assert stats["dataset_name"] == "Widar 3.0"
        assert stats["total_samples"] == 10


class TestNTUFiDataset:
    """Validate NTU-Fi HAR PyTorch Dataset implementation."""

    def test_ntufi_dataset_load_and_getitem(self):
        ds = NTUFiDataset(split="train", max_samples=10)
        assert len(ds) == 10

        item = ds[0]
        assert "csi" in item
        assert "label" in item
        assert "dataset" in item
        assert item["dataset"] == "ntufi_har"
        assert item["csi"].shape == (50, 56)
        assert 0 <= item["label"] < 6

        stats = ds.get_dataset_stats()
        assert stats["dataset_name"] == "NTU-Fi HAR"
        assert stats["total_samples"] == 10


class TestCombinedDataset:
    """Validate Combined Dataset and DataLoader collation."""

    def test_combined_dataset_and_collation(self):
        combined_ds = CombinedCSIDataset(
            split="train",
            widar_max_samples=10,
            ntufi_max_samples=10
        )
        assert len(combined_ds) == 20

        sample = combined_ds[0]
        assert "presence" in sample
        assert "motion" in sample
        assert sample["csi"].shape == (50, 56)

        # Test batch collation
        batch = [combined_ds[i] for i in range(4)]
        collated = collate_csi_batch(batch)
        assert collated["csi"].shape == (4, 50, 56)
        assert collated["label"].shape == (4,)
        assert collated["presence"].shape == (4, 1)
        assert collated["motion"].shape == (4, 1)

    def test_dataloader_factory(self):
        train_l, val_l, test_l = create_dataloaders(
            dataset_name="combined",
            batch_size=4,
            widar_max_samples=10,
            ntufi_max_samples=10
        )
        assert len(train_l) > 0
        batch = next(iter(train_l))
        assert batch["csi"].shape == (4, 50, 56)


class TestCSIFormerNetArchitecture:
    """Validate CSIFormerNet model forward, backward, variable lengths, and AMP."""

    def test_model_forward_and_shapes(self):
        model = CSIFormerNet(num_subcarriers=56, seq_len=50, num_classes=12)
        x = torch.randn(2, 50, 56)
        outputs = model(x)

        assert outputs["activity_logits"].shape == (2, 12)
        assert outputs["presence_probability"].shape == (2, 1)
        assert outputs["motion_probability"].shape == (2, 1)
        assert outputs["attention_weights"].shape == (2, 50)
        assert outputs["activity_class"].shape == (2,)

    def test_variable_sequence_length(self):
        model = CSIFormerNet(num_subcarriers=56, seq_len=50, num_classes=12)
        # Sequence length 80 instead of nominal 50
        x_long = torch.randn(2, 80, 56)
        outputs = model(x_long)
        assert outputs["activity_logits"].shape == (2, 12)
        assert outputs["attention_weights"].shape == (2, 80)

    def test_gradient_backward_pass(self):
        model = CSIFormerNet(num_subcarriers=56, seq_len=50, num_classes=12)
        x = torch.randn(2, 50, 56)
        y_act = torch.tensor([1, 7], dtype=torch.long)
        y_pres = torch.tensor([[1.0], [1.0]])

        outputs = model(x)
        ce_loss = torch.nn.CrossEntropyLoss()(outputs["activity_logits"], y_act)
        bce_loss = torch.nn.BCEWithLogitsLoss()(outputs["presence_logits"], y_pres)
        total_loss = ce_loss + bce_loss

        total_loss.backward()
        for p in model.parameters():
            if p.requires_grad and p.grad is not None:
                assert not torch.isnan(p.grad).any()

    def test_amp_autocast_compatibility(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = CSIFormerNet(num_subcarriers=56, seq_len=50, num_classes=12).to(device)
        x = torch.randn(2, 50, 56, device=device)

        with torch.amp.autocast(device_type="cuda" if device == "cuda" else "cpu"):
            outputs = model(x)
            assert outputs["activity_logits"].shape == (2, 12)


class TestEvaluationMetrics:
    """Validate statistical performance metric computation and plotting."""

    def test_metrics_calculation_and_plot(self, tmp_path):
        y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        # One-hot like probabilities with high confidence
        y_probs = np.array([
            [0.9, 0.05, 0.05],
            [0.1, 0.8, 0.1],
            [0.05, 0.05, 0.9],
            [0.85, 0.1, 0.05],
            [0.05, 0.9, 0.05],
            [0.1, 0.1, 0.8],
            [0.8, 0.1, 0.1],
            [0.2, 0.7, 0.1],
            [0.1, 0.1, 0.8]
        ])
        class_names = ["ClassA", "ClassB", "ClassC"]

        metrics = compute_classification_metrics(y_true, y_probs, class_names)
        assert metrics["accuracy"] == 1.0
        assert metrics["f1_macro"] == 1.0
        assert metrics["precision_macro"] == 1.0

        # Test CM plotting
        cm_path = tmp_path / "test_cm.png"
        out_plot = plot_confusion_matrix(metrics["confusion_matrix"], class_names, save_path=cm_path)
        assert out_plot.exists()
        assert out_plot.stat().st_size > 1000


class TestTrainingEngineSmoke:
    """Execute mini smoke training step and verify export deliverables."""

    def test_smoke_training_step(self, tmp_path):
        models_dir = tmp_path / "models"
        reports_dir = tmp_path / "reports"
        logs_dir = tmp_path / "logs"

        result = train_csiformer(
            dataset_name="combined",
            target_mode="HT20",
            epochs=2,
            batch_size=8,
            widar_max_samples=16,
            ntufi_max_samples=16,
            models_dir=models_dir,
            reports_dir=reports_dir,
            log_dir=logs_dir,
            smoke_test=True
        )

        assert result["status"] == "COMPLETED"
        assert result["epochs_trained"] == 2
        assert (models_dir / "latest_checkpoint.pth").exists()
        assert (reports_dir / "training_report.md").exists()
        assert (reports_dir / "dataset_summary.md").exists()
