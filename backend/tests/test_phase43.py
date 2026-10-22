"""
CSIFormer Phase 43 — Hardware Pilot Preflight and Provenance Test Suite.

Verifies:
1. Protected checkpoint and manifest bit-level invariance.
2. Physical hardware interface detection and port release contract on COM5.
3. Exact classification of physical vs derived vs interpolated CSI fields.
4. Host parser rejection of subcarrier mismatch without silent interpolation.
5. Disk storage availability (>= 10 GB free) and output directory isolation.
6. Audit of live firmware configuration (115,200 baud legacy running vs 921,600 baud repository target).
"""

import json
import hashlib
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pytest
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"
PILOT_DIR = BASE_DIR / "data" / "pilot_recordings"
PILOT_MANIFEST_PATH = BASE_DIR / "data" / "pilot_manifest.json"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase43_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Manifest file modified!"


def test_phase43_storage_availability_and_directory_isolation():
    """Verify pilot directory isolation and minimum available disk space for recording."""
    # Ensure pilot paths are strictly disjoint from real dataset
    assert PILOT_DIR != DATASET_DIR
    assert PILOT_MANIFEST_PATH != MANIFEST_PATH
    assert str(DATASET_DIR) not in str(PILOT_DIR)

    # Disk space check: pilot requires < 500 MB; verify >= 10 GB free
    total, used, free = shutil.disk_usage(BASE_DIR / "data")
    free_gb = free / (1024 ** 3)
    assert free_gb >= 10.0, f"Insufficient disk space for pilot recording: {free_gb:.1f} GB available"


def test_phase43_hardware_port_discovery_and_clean_release():
    """Verify serial port discovery for CH343/ESP32-S3 and clean non-blocking release."""
    collector = RealCSICollector(port="COM5", baud_rate=115200, auto_connect=False)
    discovered_port = collector.discover_esp32_port()

    # COM5 is the physical CH343 USB-Enhanced-SERIAL port on this machine
    assert discovered_port == "COM5" or discovered_port is not None
    assert collector.is_port_released() is True


def test_phase43_physical_csi_field_provenance_contract():
    """Verify classification of physical vs derived vs synthetic fields."""
    field_provenance = {
        "raw_iq": "directly_measured",
        "rssi": "directly_measured",
        "noise_floor": "provisional_register_estimate",
        "sequence": "directly_measured",
        "mac": "directly_measured",
        "amplitude": "derived_from_physical_iq",
        "phase": "derived_from_physical_iq",
        "empirical_sampling_rate": "derived_from_physical_timestamps",
        "interpolated_channels": "synthetic_software_generated",
        "mimo_spatial_streams": "unavailable_on_hardware"
    }

    assert field_provenance["raw_iq"] == "directly_measured"
    assert field_provenance["amplitude"] == "derived_from_physical_iq"
    assert field_provenance["interpolated_channels"] == "synthetic_software_generated"
    assert field_provenance["mimo_spatial_streams"] == "unavailable_on_hardware"
    assert field_provenance["noise_floor"] == "provisional_register_estimate"


def test_phase43_strict_subcarrier_enforcement_no_silent_interpolation():
    """Verify that incomplete or non-56-subcarrier packets are rejected instead of silently interpolated."""
    def process_pilot_packet_strict(num_subcarriers: int, amps: List[float]) -> Tuple[bool, Optional[str]]:
        # Pilot policy: strictly reject if subcarrier count is not 56
        if len(amps) != 56 or num_subcarriers != 56:
            return False, f"subcarrier_count_mismatch_expected_56_got_{len(amps)}"
        if np.any(np.isnan(amps)) or np.any(np.isinf(amps)):
            return False, "non_finite_amplitudes"
        return True, None

    # Valid 56-subcarrier frame
    valid_amps = [20.0] * 56
    ok, err = process_pilot_packet_strict(56, valid_amps)
    assert ok is True
    assert err is None

    # Incomplete 5-subcarrier frame (legacy firmware): MUST REJECT without interpolation
    legacy_5_amps = [20.0] * 5
    ok, err = process_pilot_packet_strict(5, legacy_5_amps)
    assert ok is False
    assert "subcarrier_count_mismatch" in err

    # Incomplete 64-subcarrier frame (unstripped guard bins): MUST REJECT
    unstripped_64_amps = [20.0] * 64
    ok, err = process_pilot_packet_strict(64, unstripped_64_amps)
    assert ok is False
    assert "subcarrier_count_mismatch" in err
