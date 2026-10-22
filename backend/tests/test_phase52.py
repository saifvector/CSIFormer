"""
CSIFormer Phase 52 — Source Filtering, Physical Subcarrier Masking, and Acquisition-Rate Readiness Test Suite.

Verifies:
1. Gate 0 / Gate D: Protected model checkpoints and dataset manifest bit-level invariance.
2. Transmitter MAC vs BSSID Semantics & Configurable Target-Source Filtering:
   - Delineates transmitter MAC (TA) from BSSID.
   - Admits target AP frames (98:BA:5F:EF:28:26) when filter_by_mac=True.
   - Filters out ambient non-target frames (e.g. 18:CC:88:7E:74:71).
   - Fails closed on missing or corrupted source metadata.
3. HT20 64-Bin Physical Carrier Masking:
   - Preserves 64-bin physical representation.
   - Correctly identifies 52 physical active data subcarriers and 12 DC/guard nulls.
   - Verified separation of physical active tones without altering existing model preprocessing.
4. Stream Diagnostics Contract:
   - get_stream_diagnostics() accurately reports source counts, filtered counts, and port status.
5. Model Preprocessing Invariance:
   - Sliding window buffer continues producing exact [50, 56] temporal windows.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
import pytest
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector
from backend.app.services.esp32_csi_adapter import ESP32CSIAdapter

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase52_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase52_target_source_filtering_and_fail_closed():
    """Verify transmitter MAC filtering, target AP admission, ambient rejection, and fail-closed policy."""
    collector = RealCSICollector(
        port=None,
        auto_connect=False,
        target_mac="98:BA:5F:EF:28:26",
        filter_by_mac=True
    )

    # 1. Target AP frame -> admitted
    target_frame = {
        "timestamp": 1000.0,
        "sequence": 1,
        "mac": "98:ba:5f:ef:28:26",  # case-insensitive test
        "rssi": -60.0,
        "noise_floor": -92.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [15.0] * 56,
        "raw_phases": [1.0] * 56
    }
    collector._process_parsed_frame(target_frame)
    assert collector.csi_packets_parsed == 1
    assert collector.filtered_non_target_packets == 0
    assert collector.source_mac_counts.get("98:BA:5F:EF:28:26") == 1

    # 2. Ambient non-target frame -> rejected
    ambient_frame = {
        "timestamp": 1000.1,
        "sequence": 2,
        "mac": "18:CC:88:7E:74:71",
        "rssi": -65.0,
        "noise_floor": -93.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [12.0] * 56,
        "raw_phases": [0.5] * 56
    }
    collector._process_parsed_frame(ambient_frame)
    assert collector.csi_packets_parsed == 1  # Unchanged
    assert collector.filtered_non_target_packets == 1
    assert collector.source_mac_counts.get("18:CC:88:7E:74:71") == 1

    # 3. Missing MAC metadata -> fails closed and records error
    missing_mac_frame = {
        "timestamp": 1000.2,
        "sequence": 3,
        "mac": "",
        "rssi": -60.0,
        "noise_floor": -92.0,
        "num_subcarriers": 56,
        "raw_amplitudes": [15.0] * 56,
        "raw_phases": [1.0] * 56
    }
    initial_errors = collector.parse_errors
    collector._process_parsed_frame(missing_mac_frame)
    assert collector.parse_errors == initial_errors + 1
    assert collector.csi_packets_parsed == 1


def test_phase52_ht20_physical_carrier_mask():
    """Verify IEEE 802.11n HT20 64-bin physical subcarrier masking and component separation."""
    # 1. Mask geometry
    active_mask, null_mask = ESP32CSIAdapter.get_ht20_64_carrier_masks()
    assert len(active_mask) == 64
    assert len(null_mask) == 64
    assert np.sum(active_mask) == 52, "Must have exactly 52 active subcarriers"
    assert np.sum(null_mask) == 12, "Must have exactly 12 null/guard positions"
    assert np.all(active_mask == ~null_mask), "Active and null masks must be strictly complementary"

    # Verify DC subcarrier is null
    assert null_mask[0] is True or null_mask[0] == True
    assert active_mask[0] is False or active_mask[0] == False

    # Verify guard bands (27..37) are null
    assert np.all(null_mask[27:38] == True)
    assert np.all(active_mask[27:38] == False)

    # 2. Synthetic 64-bin physical frame
    synthetic_64 = np.zeros(64, dtype=np.float32)
    # Fill active bins with distinct values (1..52)
    synthetic_64[ESP32CSIAdapter.HT20_64_ACTIVE_DATA_INDICES] = np.arange(1, 53, dtype=np.float32)

    # Extract 52 active tones
    extracted_52 = ESP32CSIAdapter.extract_ht20_52_active_subcarriers(synthetic_64)
    assert extracted_52.shape == (52,)
    np.testing.assert_array_equal(extracted_52, np.arange(1, 53, dtype=np.float32))

    # Separate components
    components = ESP32CSIAdapter.separate_physical_and_null_components(synthetic_64)
    assert components["active_52"].shape == (52,)
    assert components["null_12"].shape == (12,)
    assert np.all(components["null_12"] == 0.0), "All null positions must be zero"


def test_phase52_stream_diagnostics_contract():
    """Verify that get_stream_diagnostics returns complete, accurate stream health metrics."""
    collector = RealCSICollector(
        port="COM5",
        baud_rate=115200,
        auto_connect=False,
        target_mac="98:BA:5F:EF:28:26",
        filter_by_mac=True
    )
    diag = collector.get_stream_diagnostics()

    assert diag["target_mac"] == "98:BA:5F:EF:28:26"
    assert diag["filter_by_mac"] is True
    assert "source_mac_counts" in diag
    assert "filtered_non_target_packets" in diag
    assert "packet_rate_hz" in diag
    assert "port_released" in diag
    assert diag["port_released"] is True


def test_phase52_model_preprocessing_invariance():
    """Verify that model temporal sliding window format [50, 56] is preserved without drift."""
    collector = RealCSICollector(port=None, auto_connect=False, filter_by_mac=False)

    # Push 50 frames to fill window
    for i in range(50):
        frame = {
            "timestamp": 1000.0 + i * 0.033,
            "sequence": i + 1,
            "mac": "98:BA:5F:EF:28:26",
            "rssi": -60.0,
            "noise_floor": -92.0,
            "num_subcarriers": 64,
            "raw_amplitudes": [10.0] * 64,
            "raw_phases": [0.0] * 64
        }
        collector._process_parsed_frame(frame)

    window = collector.get_latest_window()
    assert window is not None
    raw_win, phase_win = window
    assert raw_win.shape == (50, 56), f"Expected (50, 56), got {raw_win.shape}"
    assert phase_win.shape == (50, 56), f"Expected (50, 56), got {phase_win.shape}"
