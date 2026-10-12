"""
Unit and Integration Tests for CSIFormer Training Dataset Acquisition & ESP32-S3 Adapter.
"""

import os
import json
import csv
from pathlib import Path
import numpy as np
import pytest

from app.services.esp32_csi_adapter import ESP32CSIAdapter


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = BASE_DIR / "datasets"
WIDAR_DIR = DATASETS_DIR / "widar3"
NTUFI_DIR = DATASETS_DIR / "ntufi_har"
REPORTS_DIR = DATASETS_DIR / "reports"


class TestESP32CSIAdapter:
    """Test the mathematical transformation and transfer learning adapter."""

    def test_intel5300_subcarrier_interpolation(self):
        adapter_ht20 = ESP32CSIAdapter(target_mode="HT20")
        adapter_ht40 = ESP32CSIAdapter(target_mode="HT40")

        # Mock Intel 5300 input: (3 antennas, 30 subcarriers, 100 time frames)
        mock_intel = np.random.rand(3, 30, 100)

        out_ht20 = adapter_ht20.intel5300_to_esp32(mock_intel)
        out_ht40 = adapter_ht40.intel5300_to_esp32(mock_intel)

        # HT20 expects 56 subcarriers
        assert out_ht20.shape == (3, 56, 100)
        # HT40 expects 114 subcarriers
        assert out_ht40.shape == (3, 114, 100)

    def test_atheros_subcarrier_mapping(self):
        adapter_ht20 = ESP32CSIAdapter(target_mode="HT20")
        adapter_ht40 = ESP32CSIAdapter(target_mode="HT40")

        # Mock Atheros input: (3 antennas, 114 subcarriers, 50 time frames)
        mock_atheros = np.random.rand(3, 114, 50)

        out_ht20 = adapter_ht20.atheros_to_esp32(mock_atheros)
        out_ht40 = adapter_ht40.atheros_to_esp32(mock_atheros)

        # HT20 decimated to 56 subcarriers
        assert out_ht20.shape == (3, 56, 50)
        # HT40 direct 114 subcarriers
        assert out_ht40.shape == (3, 114, 50)

    def test_antenna_reduction(self):
        adapter = ESP32CSIAdapter()
        mock_multi_ant = np.ones((3, 56, 50))

        out_single = adapter.normalize_antenna_stream(mock_multi_ant, target_antennas=1)
        out_dual = adapter.normalize_antenna_stream(mock_multi_ant, target_antennas=2)

        assert out_single.shape == (1, 56, 50)
        assert out_dual.shape == (2, 56, 50)

    def test_temporal_resampling(self):
        adapter = ESP32CSIAdapter(target_rate_hz=30.0)
        # 1000 Hz input sequence for 2 seconds = 2000 samples
        mock_fast_seq = np.random.rand(1, 56, 2000)

        resampled = adapter.resample_temporal_rate(mock_fast_seq, source_rate_hz=1000.0)
        # 2 seconds at 30 Hz = 60 samples
        assert resampled.shape == (1, 56, 60)

    def test_phase_sanitization(self):
        adapter = ESP32CSIAdapter()
        subcarriers = 56
        timestamps = 20
        # Create synthetic phase with a known linear slope (SFO ramp) + noise
        slope = 0.5
        carrier_idx = np.arange(subcarriers)
        raw_phase = slope * carrier_idx[:, None] + np.random.normal(0, 0.01, size=(subcarriers, timestamps))

        sanitized = adapter.sanitize_phase(raw_phase)
        # Sanitized phase should have mean slope near 0
        residual_slope = np.polyfit(carrier_idx, sanitized[:, 0], 1)[0]
        assert abs(residual_slope) < 0.05

    def test_end_to_end_adaptation(self):
        adapter = ESP32CSIAdapter(target_mode="HT20", target_rate_hz=30.0)
        widar_raw = np.random.rand(3, 30, 1000)  # 1 sec of Widar 3.0 at 1000 Hz
        result = adapter.adapt_sample(widar_raw, source_type="widar", source_rate_hz=1000.0, target_antennas=1)

        assert result["target_mode"] == "HT20"
        assert result["subcarriers"] == 56
        assert result["sampling_rate_hz"] == 30.0
        assert result["adapted_csi"].shape == (1, 56, 30)
        assert 0.0 <= np.min(result["adapted_csi"]) <= 1.0
        assert 0.0 <= np.max(result["adapted_csi"]) <= 1.0


class TestDatasetExclusionsAndIntegrity:
    """Verify that all exclusions and requirements are strictly honored."""

    def test_directories_exist(self):
        assert (WIDAR_DIR / "csi").exists()
        assert (WIDAR_DIR / "labels").exists()
        assert (WIDAR_DIR / "metadata").exists()
        assert (NTUFI_DIR / "csi").exists()
        assert (NTUFI_DIR / "labels").exists()
        assert (NTUFI_DIR / "metadata").exists()
        assert REPORTS_DIR.exists()

    def test_excluded_extensions_in_widar(self):
        # Ensure no videos, pdfs, or bvp files are placed in widar csi
        prohibited_exts = [".pdf", ".mp4", ".avi", ".zip", ".tar", ".gz"]
        all_widar_files = list(WIDAR_DIR.glob("**/*"))
        for f in all_widar_files:
            if f.is_file():
                assert f.suffix.lower() not in prohibited_exts, f"Prohibited file found: {f}"
                assert "bvp" not in f.name.lower(), f"BVP file found: {f}"
                assert "gait" not in f.name.lower(), f"Gait file found: {f}"
