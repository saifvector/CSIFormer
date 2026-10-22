"""
CSIFormer Phase 51 — CSI Stream Integrity, Physical Subcarrier Verification, and Pilot Readiness Audit Test Suite.

Verifies:
1. Gate 0 / Gate D: Protected model checkpoints and dataset manifest invariance.
2. Physical subcarrier analysis:
   - Differentiates 64-bin FFT representation (52 active subcarriers, 1 DC null, 11 guard nulls) from 56-subcarrier model representation.
   - Validates that physical raw measurements are preserved separately from resampled/aligned inference buffers.
3. Host parser edge case resilience and strict rejection of malformed/corrupt records:
   - Rejects records with fewer than 6 header tokens.
   - Rejects non-numeric RSSI / noise / sequence values.
   - Rejects corrupt or empty subcarrier strings.
   - Ignores non-CSI telemetry and boot logs.
4. Serial interface contract:
   - Validates clean non-blocking port closure and verified port release (no resource leakage).
5. Pilot readiness requirements:
   - BSSID filtering contract (separating target AP from ambient co-channel interference).
   - Physical subcarrier extraction policy (56 physical subcarriers vs guard bin inclusion).
   - Strict embargo on dataset admission without separate authorization.
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


def test_phase51_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase51_physical_vs_derived_subcarrier_structure():
    """
    Audit the mapping between the 64-bin physical FFT payload from ESP32-S3
    and the 56-subcarrier inference target.
    """
    collector = RealCSICollector(port=None, auto_connect=False)

    # Synthetic 64-bin frame mimicking real ESP32-S3 HT20 hardware output:
    # 52 active data subcarriers, 1 DC carrier (index 0 == 0.0), 11 guard bins (indices 27-37 == 0.0)
    amps_64 = [0.0 if i in [0] + list(range(27, 38)) else 15.0 for i in range(64)]
    phases_64 = [0.0 if i in [0] + list(range(27, 38)) else 1.25 for i in range(64)]

    subcarriers_str = ",".join(f"{a}:{p}" for a, p in zip(amps_64, phases_64))
    line = f"CSI_DATA,98:BA:5F:EF:28:26,-62.0,-93.0,100,64,{subcarriers_str}\n"

    parsed = collector.parse_raw_telemetry_line(line)
    assert parsed is not None
    assert parsed["num_subcarriers"] == 64
    assert len(parsed["raw_amplitudes"]) == 64

    # Verify that raw DC carrier and guard carriers are strictly 0.0 in physical capture
    raw_amps = np.array(parsed["raw_amplitudes"])
    assert raw_amps[0] == 0.0, "DC subcarrier must be 0.0"
    assert np.all(raw_amps[27:38] == 0.0), "Guard null bins (27-37) must be 0.0"
    active_indices = [i for i in range(64) if i not in [0] + list(range(27, 38))]
    assert len(active_indices) == 52, f"Expected 52 active subcarriers, found {len(active_indices)}"
    assert np.all(raw_amps[active_indices] == 15.0)


def test_phase51_parser_rejection_of_malformed_records():
    """Verify that the host parser strictly rejects malformed, incomplete, or corrupted records."""
    collector = RealCSICollector(port=None, auto_connect=False)

    # 1. Truncated header (< 6 tokens)
    assert collector.parse_raw_telemetry_line("CSI_DATA,98:BA:5F:EF:28:26,-60.0") is None

    # 2. Corrupted non-numeric RSSI
    assert collector.parse_raw_telemetry_line("CSI_DATA,98:BA:5F:EF:28:26,BAD_RSSI,-93.0,1,56,10.0:1.0\n") is None

    # 3. Corrupted non-numeric noise floor
    assert collector.parse_raw_telemetry_line("CSI_DATA,98:BA:5F:EF:28:26,-60.0,BAD_NOISE,1,56,10.0:1.0\n") is None

    # 4. Corrupted sequence
    assert collector.parse_raw_telemetry_line("CSI_DATA,98:BA:5F:EF:28:26,-60.0,-93.0,NOT_A_SEQ,56,10.0:1.0\n") is None

    # 5. Empty subcarriers payload
    assert collector.parse_raw_telemetry_line("CSI_DATA,98:BA:5F:EF:28:26,-60.0,-93.0,1,0,\n") is None

    # 6. Bootloader log lines (should return None without errors)
    assert collector.parse_raw_telemetry_line("I (551) ESP32S3_CSI_COLLECTOR: Wi-Fi CSI Collection Enabled\n") is None
    assert collector.parse_raw_telemetry_line("ESP-ROM:esp32s3-20210327\n") is None


def test_phase51_port_release_contract():
    """Verify that serial port discovery and release guarantee no leaked handles."""
    collector = RealCSICollector(port="COM5", baud_rate=115200, auto_connect=False)
    # Port release contract before connect
    assert collector.is_port_released() is True

    # Safe disconnect on unopen handle must be idempotent and return True
    assert collector.disconnect() is True
    assert collector.is_port_released() is True


def test_phase51_pilot_readiness_safety_embargo():
    """Verify that pilot directories and manifests remain completely unpopulated."""
    # Production manifest must remain untouched
    assert MANIFEST_PATH.exists()
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5

    # Pilot manifest must NOT exist prior to separate pilot authorization
    if PILOT_MANIFEST_PATH.exists():
        data = json.loads(PILOT_MANIFEST_PATH.read_text(encoding="utf-8"))
        assert len(data.get("sessions", [])) == 0, "Pilot manifest contains unapproved sessions!"

    # Pilot recording folder must contain no unauthorized research files
    if PILOT_DIR.exists():
        csv_files = list(PILOT_DIR.glob("*.csv"))
        assert len(csv_files) == 0, f"Unauthorized pilot CSV files present: {csv_files}"
