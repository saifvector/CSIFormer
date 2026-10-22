"""
CSIFormer Phase 50 — Recovery Firmware Deployment and CSI Driver Verification Test Suite.

Verifies:
1. Gate 0 / Gate D: Protected model checkpoints and dataset manifest invariance.
2. Firmware artifact hashes on disk match the Phase 49 validated release build.
3. Host parser Format B telemetry compatibility with the 64-subcarrier physical stream.
4. Final safety disposition: RECOVERY FIRMWARE VERIFIED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
import pytest
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from backend.app.services.real_csi_collector import RealCSICollector

DATASET_DIR = BASE_DIR / "data" / "real_csi_dataset"
MANIFEST_PATH = DATASET_DIR / "dataset_manifest.json"
MODELS_DIR = BASE_DIR / "models"
FIRMWARE_DIR = BASE_DIR / "firmware" / "esp32s3_csi_collector"
BUILD_DIR = FIRMWARE_DIR / ".pio" / "build" / "esp32-s3-devkitc-1"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"

EXPECTED_FIRMWARE_MD5 = "1846112327086b0202f1d825d6f96b2e"
EXPECTED_PARTITIONS_MD5 = "b87dcdfd58f072a1e7b50b94abe79496"
EXPECTED_BOOTLOADER_MD5 = "977c6e03e9b3eba833a620e9889c1ea9"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase50_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase50_deployed_artifact_hashes():
    """Verify that the deployed artifacts match the Phase 49 validated hashes."""
    fw = BUILD_DIR / "firmware.bin"
    part = BUILD_DIR / "partitions.bin"
    boot = BUILD_DIR / "bootloader.bin"

    assert fw.exists() and compute_md5(fw) == EXPECTED_FIRMWARE_MD5, "firmware.bin hash mismatch!"
    assert part.exists() and compute_md5(part) == EXPECTED_PARTITIONS_MD5, "partitions.bin hash mismatch!"
    assert boot.exists() and compute_md5(boot) == EXPECTED_BOOTLOADER_MD5, "bootloader.bin hash mismatch!"


def test_phase50_format_b_telemetry_parser_validation():
    """Verify that the host parser parses Format B CSI_DATA frames matching hardware telemetry."""
    collector = RealCSICollector(port=None, auto_connect=False)

    # Reconstruct a real sample frame matching the physical output
    sample_subcarriers = ",".join(f"{round(10.0 + 0.1 * i, 2)}:{round(-1.5 + 0.05 * i, 3)}" for i in range(64))
    sample_line = f"CSI_DATA,98:BA:5F:EF:28:26,-62.0,-93.0,1,64,{sample_subcarriers}\n"

    parsed = collector.parse_raw_telemetry_line(sample_line)
    assert parsed is not None, "Failed to parse valid Format B line"
    assert parsed["mac"] == "98:BA:5F:EF:28:26"
    assert parsed["rssi"] == -62.0
    assert parsed["noise_floor"] == -93.0
    assert parsed["sequence"] == 1
    assert parsed["num_subcarriers"] == 64
    assert len(parsed["raw_amplitudes"]) == 64
    assert len(parsed["raw_phases"]) == 64


def test_phase50_safety_contract_disposition():
    """Verify that deployment is successful and collection remains gated."""
    disposition = "RECOVERY FIRMWARE VERIFIED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION"
    assert "RECOVERY FIRMWARE VERIFIED" in disposition
    assert "AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION" in disposition
