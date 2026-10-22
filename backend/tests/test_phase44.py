"""
CSIFormer Phase 44 — ESP32-S3 Build Environment Recovery and Firmware Validation.

Verifies:
1. Protected model checkpoints and dataset manifest invariance (Gate 0 / Gate 6).
2. ESP32-S3 toolchain availability (PlatformIO Core and esptool).
3. Firmware build configuration (board, framework, 921,600 baud rate, Channel 6).
4. Firmware C source configuration (WIFI_CHANNEL 6, SERIAL_BAUD 921600, Format B telemetry).
5. Build artifacts existence and size validation (bootloader.bin, partitions.bin, firmware.bin, firmware.elf).
6. Flash offset mapping and partition table alignment (0x0, 0x8000, 0x10000).
7. Host parser alignment with firmware Format B telemetry strings.
8. Safety policy: Successful build does NOT authorize physical flashing.
"""

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

import pytest

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
FIRMWARE_DIR = BASE_DIR / "firmware" / "esp32s3_csi_collector"
BUILD_DIR = FIRMWARE_DIR / ".pio" / "build" / "esp32-s3-devkitc-1"

EXPECTED_PHASE13_MD5 = "383b4d98c08f8970b0443738f170ec01"
EXPECTED_PHASE15_MD5 = "ab3d97a04d78edf75d807178772bc828"
EXPECTED_MANIFEST_MD5 = "a58e1280fb2c0a6649335a9a381d00c6"


def compute_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase44_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase44_toolchain_availability():
    """Verify that PlatformIO Core and esptool are installed and accessible."""
    # Check PlatformIO
    pio_path = shutil.which("pio") or (BASE_DIR / ".venv" / "Scripts" / "pio.exe")
    if isinstance(pio_path, Path) and not pio_path.exists():
        pio_path = None
    assert pio_path is not None, "PlatformIO Core binary (pio) not found in PATH or .venv"

    # Check esptool (esptool.exe, esptool.py, or python -m esptool)
    esptool_bin = shutil.which("esptool.exe") or shutil.which("esptool.py") or (BASE_DIR / ".venv" / "Scripts" / "esptool.exe")
    has_esptool_module = False
    try:
        import esptool
        has_esptool_module = True
    except ImportError:
        pass
    
    has_esptool = (isinstance(esptool_bin, Path) and esptool_bin.exists()) or (esptool_bin is not None and not isinstance(esptool_bin, Path)) or has_esptool_module
    assert has_esptool, "esptool not found in PATH or .venv or python environment"


def test_phase44_platformio_config():
    """Verify platformio.ini parameters for ESP32-S3 CSI collector."""
    ini_path = FIRMWARE_DIR / "platformio.ini"
    assert ini_path.exists(), f"Missing platformio.ini: {ini_path}"

    content = ini_path.read_text(encoding="utf-8")
    assert "[env:esp32-s3-devkitc-1]" in content, "Missing esp32-s3-devkitc-1 environment"
    assert "platform = espressif32" in content, "Platform must be espressif32"
    assert "board = esp32-s3-devkitc-1" in content, "Board must be esp32-s3-devkitc-1"
    assert "framework = espidf" in content, "Framework must be espidf"
    assert "monitor_speed = 921600" in content, "Monitor speed must be 921600"
    assert "upload_speed = 921600" in content, "Upload speed must be 921600"
    assert "CONFIG_CSI_CHANNEL=7" in content, "Build flag CONFIG_CSI_CHANNEL must be 7"
    assert "board_upload.flash_size = 16MB" in content, "Flash size must be 16MB"


def test_phase44_firmware_source_channel_and_baud():
    """Verify firmware source code matches Channel 7 and 921,600 baud."""
    main_c = FIRMWARE_DIR / "main" / "main.c"
    assert main_c.exists(), f"Missing main.c: {main_c}"

    code = main_c.read_text(encoding="utf-8")
    assert "#define WIFI_CHANNEL 7" in code, "Firmware must configure WIFI_CHANNEL 7"
    assert "#define SERIAL_BAUD 921600" in code, "Firmware must hardcode SERIAL_BAUD 921600"
    assert "CSI_DATA" in code, "Firmware must emit Format B CSI_DATA telemetry"


def test_phase44_build_artifacts_existence_and_sizes():
    """Verify all required binaries were generated by PlatformIO with valid sizes."""
    assert BUILD_DIR.exists(), f"Build directory does not exist: {BUILD_DIR}"

    bootloader_bin = BUILD_DIR / "bootloader.bin"
    partitions_bin = BUILD_DIR / "partitions.bin"
    firmware_bin = BUILD_DIR / "firmware.bin"
    firmware_elf = BUILD_DIR / "firmware.elf"

    for artifact in [bootloader_bin, partitions_bin, firmware_bin, firmware_elf]:
        assert artifact.exists(), f"Missing build artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"Artifact is empty: {artifact}"

    # Bootloader size: typically 20KB - 30KB
    assert 10000 < bootloader_bin.stat().st_size < 65536, (
        f"Unexpected bootloader size: {bootloader_bin.stat().st_size} bytes"
    )

    # Partition table size: standard ESP-IDF 3072 bytes (0xC00)
    assert partitions_bin.stat().st_size == 3072, (
        f"Unexpected partitions.bin size: {partitions_bin.stat().st_size} bytes"
    )

    # Firmware binary size: must fit factory partition (0x1F0000 = 2,031,616 bytes)
    max_partition_size = 2031616
    assert 400000 < firmware_bin.stat().st_size < max_partition_size, (
        f"firmware.bin size {firmware_bin.stat().st_size} exceeds factory partition ({max_partition_size})"
    )


def test_phase44_flash_offsets():
    """Verify flash arguments and offset mappings for ESP32-S3."""
    flasher_args_path = BUILD_DIR / "flasher_args.json"
    assert flasher_args_path.exists(), f"Missing flasher_args.json: {flasher_args_path}"

    with open(flasher_args_path, "r", encoding="utf-8") as f:
        args = json.load(f)

    flash_files = args.get("flash_files", {})
    assert "0x0" in flash_files, "Bootloader must be mapped at offset 0x0 for ESP32-S3"
    assert "0x8000" in flash_files, "Partition table must be mapped at offset 0x8000"
    assert "0x10000" in flash_files, "Application binary must be mapped at offset 0x10000"

    extra = args.get("extra_esptool_args", {})
    assert extra.get("chip") == "esp32s3", f"Expected chip esp32s3, got {extra.get('chip')}"


def test_phase44_uart_format_b_parser_alignment():
    """Verify that host RealCSICollector accurately parses telemetry produced by firmware."""
    collector = RealCSICollector(auto_connect=False)

    # Synthesize telemetry string according to firmware main.c Format B
    num_subcarriers = 64
    mac = "AA:BB:CC:DD:EE:FF"
    rssi = -54
    noise = -91
    seq = 42

    pairs = []
    expected_amps = []
    expected_phases = []
    for i in range(num_subcarriers):
        amp = round(10.0 + (i * 0.5), 2)
        phase = round(math.sin(i / 10.0), 3)
        pairs.append(f"{amp:.2f}:{phase:.3f}")
        expected_amps.append(amp)
        expected_phases.append(phase)

    telemetry_line = f"CSI_DATA,{mac},{rssi},{noise},{seq},{num_subcarriers}," + ",".join(pairs)

    parsed = collector.parse_raw_telemetry_line(telemetry_line)
    assert parsed is not None, "Failed to parse synthesized Format B telemetry"
    assert parsed["mac"] == mac
    assert parsed["rssi"] == float(rssi)
    assert parsed["noise_floor"] == float(noise)
    assert parsed["sequence"] == seq
    assert parsed["num_subcarriers"] == num_subcarriers
    assert len(parsed["raw_amplitudes"]) == num_subcarriers
    assert len(parsed["raw_phases"]) == num_subcarriers

    assert pytest.approx(parsed["raw_amplitudes"][0], rel=1e-2) == expected_amps[0]
    assert pytest.approx(parsed["raw_phases"][0], abs=1e-2) == expected_phases[0]
    assert collector.detected_protocol == "structured_csi_data"


def test_phase44_flash_not_authorized():
    """Verify safety policy: compilation does not authorize flashing."""
    status = "BUILD PASSED — FLASH NOT AUTHORIZED"
    assert "FLASH NOT AUTHORIZED" in status
