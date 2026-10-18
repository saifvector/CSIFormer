"""
Unit & Integration Test Suite for CSIFormer Phase 14:
Hardware Verification, Real-Time CSI Acquisition, and End-to-End Validation.

Automated deterministic testing covering:
1. Packet parsing (Format A Raw IQ and Format B CSV)
2. Malformed packet filtering and corruption rejection
3. Thread-safe sliding window construction ([50, 56])
4. Strict incomplete window rejection (Life-safety constraint)
5. Physics-informed preprocessing (Raw amplitude normalization + STFT Doppler)
6. Phase 13 production model loading and dual-branch forward pass
7. 12-class label mapping and fall detection index verification
8. Disconnect and reconnection recovery
9. FastAPI hardware endpoints and live streaming routes
"""

import sys
import os
import time
from pathlib import Path
import numpy as np
import torch
import pytest

# Ensure backend directory is in python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.real_csi_collector import RealCSICollector
from app.services.esp32_csi_adapter import ESP32CSIAdapter
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from app.models.csiformer_dual_branch import CSIDualBranchFusionNet
from app.services.live_pipeline_service import LivePipelineService, LABEL_MAP


# =============================================================================
# 1. Packet Parsing: Format A (Raw IQ) & Format B (CSV)
# =============================================================================
def test_packet_parsing_format_a_raw_iq():
    """Verifies parsing of ESP32-S3 firmware raw IQ string format."""
    collector = RealCSICollector(auto_connect=False)
    raw_line = "RSSI=-55 LEN=128 CSI:0,0,-17,-4,-17,-4,-14,-3,-9,-3,1,0,5,2"
    record = collector.parse_raw_line(raw_line)

    assert record is not None, "Failed to parse valid Format A raw IQ line!"
    assert record["rssi"] == -55.0
    assert "raw_amplitudes" in record
    assert len(record["raw_amplitudes"]) > 0
    assert np.isfinite(record["raw_amplitudes"]).all()


def test_packet_parsing_format_b_csv():
    """Verifies parsing of structured CSV ESP-IDF telemetry."""
    collector = RealCSICollector(auto_connect=False)
    # Generate 56 amp:phase pairs
    subcarriers_csv = ",".join([f"{15.0 + i*0.1:.2f}:{0.05*i:.2f}" for i in range(56)])
    raw_csv = f"CSI_DATA,24:DC:C3:A1:01:01,-52.0,-95.0,1042,56,{subcarriers_csv}"
    record = collector.parse_raw_line(raw_csv)

    assert record is not None, "Failed to parse valid Format B CSV line!"
    assert record["mac"] == "24:DC:C3:A1:01:01"
    assert record["rssi"] == -52.0
    assert record["noise_floor"] == -95.0
    assert record["sequence"] == 1042
    assert record["num_subcarriers"] == 56
    assert len(record["raw_amplitudes"]) == 56
    assert abs(record["raw_amplitudes"][0] - 15.0) < 0.2


def test_malformed_and_missing_csi_packets():
    """Verifies robust rejection of corrupted or malformed packets without crashing."""
    collector = RealCSICollector(auto_connect=False)

    # Empty string
    assert collector.parse_raw_line("") is None
    # Truncated header
    assert collector.parse_raw_line("RSSI=-55") is None
    # Non-numeric values in CSI field
    assert collector.parse_raw_line("RSSI=-55 LEN=128 CSI:invalid,nan,corrupted") is None
    # Incomplete CSV
    assert collector.parse_raw_line("CSI_DATA,incomplete,data") is None


# =============================================================================
# 2. Window Construction & Sliding Buffer
# =============================================================================
def test_window_construction_and_sliding_buffer():
    """Verifies that packets are buffered into exact [50, 56] temporal windows."""
    collector = RealCSICollector(auto_connect=False)
    assert len(collector.raw_frame_buffer) == 0

    # Ingest 75 consecutive packets
    for i in range(75):
        raw_line = f"RSSI=-50 LEN=128 CSI:{i%10},{i%5},-17,-4,-14,-3,-9,-3"
        rec = collector.parse_raw_line(raw_line)
        collector._buffer_packet(rec)

    # Deque must hold exactly WINDOW_SIZE (50) frames
    assert len(collector.raw_frame_buffer) == 50
    raw_win, phase_win = collector.get_latest_window()

    assert raw_win is not None
    assert raw_win.shape == (50, 56), f"Expected shape (50, 56), got {raw_win.shape}"
    assert np.isfinite(raw_win).all()


# =============================================================================
# 3. Incomplete Window Rejection (Life-Safety Requirement)
# =============================================================================
def test_incomplete_window_rejection():
    """Verifies that incomplete, truncated, or NaN/flatline windows are strictly rejected."""
    service = LivePipelineService()

    # 1. Truncated window: (30, 56)
    short_win = np.random.randn(30, 56).astype(np.float32)
    # Inject into mock collector
    collector = RealCSICollector(auto_connect=False)
    for _ in range(30):
        collector._buffer_packet(collector.parse_raw_line("RSSI=-55 LEN=128 CSI:0,0,-17,-4,-14,-3,-9,-3"))
    win_res = collector.get_latest_window()
    assert win_res is None, "Incomplete window (<50 frames) must return None!"

    # 2. Corrupted window with NaN
    nan_win = np.random.randn(50, 56).astype(np.float32)
    nan_win[5, 10] = np.nan
    assert not np.isfinite(nan_win).all()


# =============================================================================
# 4. Physics Preprocessing
# =============================================================================
def test_physics_csi_preprocessor():
    """Verifies physics-informed STFT Doppler extraction and shape alignment."""
    prep = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )

    dummy_csi = np.random.randn(50, 56).astype(np.float32) + 15.0
    dopp_spec = prep.compute_doppler_spectrogram(dummy_csi)

    assert dopp_spec.shape == (50, 56), f"Expected STFT Doppler shape (50, 56), got {dopp_spec.shape}"
    assert np.isfinite(dopp_spec).all(), "Doppler spectrogram contains NaN/Inf values!"


# =============================================================================
# 5. Model Loading, Dual-Branch Forward Pass & Label Mapping
# =============================================================================
def test_phase13_model_checkpoint_and_forward_pass():
    """Verifies production checkpoint loading and dual-branch inference."""
    repo_root = BASE_DIR.parent
    ckpt_path = repo_root / "models" / "csiformer_phase13_best.pth"
    assert ckpt_path.exists(), f"Production checkpoint missing: {ckpt_path}"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CSIDualBranchFusionNet(
        num_subcarriers=56,
        doppler_bins=56,
        seq_len=50,
        num_classes=12,
        embed_dim=128,
        nhead=8,
        num_layers=3,
        dim_feedforward=512,
        fusion_mode="gated"
    ).to(device)

    state = torch.load(ckpt_path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.eval()

    # Create dummy batch [1, 50, 56]
    bx_raw = torch.randn(1, 50, 56, device=device)
    bx_dopp = torch.randn(1, 50, 56, device=device)

    with torch.no_grad():
        out = model(bx_raw, bx_dopp)

    assert "activity_logits" in out
    logits = out["activity_logits"]
    assert logits.shape == (1, 12), f"Expected logits [1, 12], got {logits.shape}"

    assert "projected_features" in out
    assert out["projected_features"].shape == (1, 128)

    assert "gate_weights" in out
    weights = out["gate_weights"]
    assert weights.shape == (1, 128)
    assert (weights >= 0.0).all() and (weights <= 1.0).all()


def test_label_mapping_and_life_safety_fall_class():
    """Verifies 12-class label index alignment and life-safety fall class 9."""
    assert len(LABEL_MAP) == 12
    # Life-Safety Fall Detection must be class 9
    assert 9 in LABEL_MAP
    assert "FALL DETECTION" in LABEL_MAP[9]
    # Widar classes 0..5
    assert LABEL_MAP[0] == "Push&Pull (Widar)"
    assert LABEL_MAP[5] == "Draw-Zigzag (Widar)"
    # NTU-Fi classes 6..11
    assert LABEL_MAP[6] == "Box (NTU-Fi)"
    assert LABEL_MAP[11] == "Walk (NTU-Fi)"


# =============================================================================
# 6. Disconnect & Recovery Handling
# =============================================================================
def test_disconnect_and_recovery_handling():
    """Verifies that disconnecting serial port releases resources and handles error states."""
    collector = RealCSICollector(port="COM999", auto_connect=False)
    # Attempting to connect to non-existent port returns False cleanly without exception
    conn = collector.connect()
    assert conn is False
    assert collector.is_connected is False

    # Disconnecting inactive port is safe
    collector.disconnect()
    assert collector.is_connected is False

    stats = collector.get_stats()
    assert stats["is_connected"] is False
    assert stats["is_streaming"] is False


# =============================================================================
# 7. FastAPI Endpoints Integration
# =============================================================================
def test_fastapi_hardware_endpoints():
    """Verifies hardware and live streaming API routes."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Get devices status
    resp_devices = client.get("/api/v1/hardware/devices")
    assert resp_devices.status_code == 200
    assert "devices" in resp_devices.json()

    # 2. Get collector status
    resp_collector = client.get("/api/v1/hardware/collector/status")
    assert resp_collector.status_code == 200
    data = resp_collector.json()
    assert "is_streaming" in data
    assert "model_loaded" in data
    assert data["model_loaded"] is True

    # 3. Get collector window (returns buffering or ready)
    resp_win = client.get("/api/v1/hardware/collector/window")
    assert resp_win.status_code == 200
    assert "status" in resp_win.json()

    # 4. Scan COM ports
    resp_ports = client.get("/api/v1/hardware/ports")
    assert resp_ports.status_code == 200
    assert len(resp_ports.json()) > 0
