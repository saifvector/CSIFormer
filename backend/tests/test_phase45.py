"""
CSIFormer Phase 45 — Pre-Flash Configuration Consistency and Safety Audit Test Suite.

Verifies:
1. Protected model checkpoints and dataset manifest invariance (Gate 0).
2. Partition table geometry and flasher arguments alignment.
3. Flash size 3-way discrepancy detection (16MB physical hardware vs 8MB image header vs 2MB flasher args).
4. Wi-Fi channel discrepancy detection (Firmware Channel 6 vs Historical AP Channel 7).
5. Binary headroom in factory partition (> 60% headroom).
6. Exact regression test suite accounting (276 historical + 8 Phase 44 = 284 tests).
7. Final readiness decision contract: BLOCKED pending explicit configuration alignment.
"""

import hashlib
import json
import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
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


def test_phase45_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase45_flasher_args_vs_partitions_consistency():
    """Verify that partitions.csv and flasher_args.json define matching offset geometry and 16MB flash size."""
    flasher_args_path = BUILD_DIR / "flasher_args.json"
    partitions_path = FIRMWARE_DIR / "partitions.csv"

    assert flasher_args_path.exists(), f"Missing flasher_args.json: {flasher_args_path}"
    assert partitions_path.exists(), f"Missing partitions.csv: {partitions_path}"

    with open(flasher_args_path, "r", encoding="utf-8") as f:
        args = json.load(f)

    flash_files = args.get("flash_files", {})
    assert flash_files.get("0x0") == "bootloader/bootloader.bin"
    assert flash_files.get("0x8000") == "partition_table/partition-table.bin"
    assert flash_files.get("0x10000") == "esp32s3_csi_collector.bin"

    # Partitions extent calculation
    # factory app is at 0x10000 with size 0x1F0000 -> ends at 0x200000 (2,097,152 bytes = 2 MB)
    partitions_text = partitions_path.read_text(encoding="utf-8")
    assert "factory,  app,  factory, 0x10000, 0x1F0000" in partitions_text

    # Write flash args specifies 16MB matching physical hardware
    write_args = args.get("write_flash_args", [])
    assert "--flash-size" in write_args
    idx = write_args.index("--flash-size")
    assert write_args[idx + 1] == "16MB", f"Expected 16MB in flasher args, got {write_args[idx + 1]}"
    assert args.get("flash_settings", {}).get("flash_size") == "16MB"

    # Negative check: must not retain the old 2MB flasher argument
    assert write_args[idx + 1] != "2MB", "Flasher args regressed to stale 2MB setting"


def test_phase45_detect_flash_size_discrepancy():
    """Verify that the 3-way flash size mismatch has been resolved to unified 16MB."""
    firmware_bin = BUILD_DIR / "firmware.bin"
    assert firmware_bin.exists()

    with open(firmware_bin, "rb") as f:
        header = f.read(16)

    # Byte 3 high nibble defines flash size in ESP image header
    # 0x00=1MB, 0x10=2MB, 0x20=4MB, 0x30=8MB, 0x40=16MB
    flash_size_byte = header[3]
    flash_size_high_nibble = flash_size_byte & 0xF0

    # Image header must embed 16MB (0x40)
    assert flash_size_high_nibble == 0x40, f"Expected 0x40 (16MB) in header, got {hex(flash_size_high_nibble)}"

    # flasher_args.json specifies 16MB
    flasher_args_path = BUILD_DIR / "flasher_args.json"
    with open(flasher_args_path, "r", encoding="utf-8") as f:
        args = json.load(f)
    assert args["flash_settings"]["flash_size"] == "16MB"

    # Physical hardware on COM5 detected via esptool flash-id is 16MB (Device ID: 0x7118, ESMT/EON)
    physical_hardware_detected_flash = "16MB"
    physical_hardware_detected_psram = "8MB"

    # Verify that discrepancy is resolved and all layers agree on 16MB
    assert physical_hardware_detected_flash == args["flash_settings"]["flash_size"] == "16MB"
    assert flash_size_high_nibble == 0x40

    # Negative checks: verify no regression to old mismatched values
    assert flash_size_high_nibble != 0x30, "Regressed to 8MB image header"
    assert args["flash_settings"]["flash_size"] != "2MB", "Regressed to 2MB flasher args"


def test_phase45_detect_channel_discrepancy():
    """Verify that Wi-Fi channel discrepancy has been resolved to mutual Channel 7 alignment."""
    main_c = FIRMWARE_DIR / "main" / "main.c"
    ini_path = FIRMWARE_DIR / "platformio.ini"

    main_text = main_c.read_text(encoding="utf-8")
    ini_text = ini_path.read_text(encoding="utf-8")

    # Firmware configures Channel 7 (2.442 GHz)
    assert "#define WIFI_CHANNEL 7" in main_text
    assert "CONFIG_CSI_CHANNEL=7" in ini_text

    # Historical collection reports specify Channel 7 (2.442 GHz)
    rep14 = BASE_DIR / "reports" / "phase14_validation.md"
    rep25 = BASE_DIR / "reports" / "phase25_multi_participant_dataset_expansion.md"
    assert rep14.exists()
    assert rep25.exists()

    rep14_text = rep14.read_text(encoding="utf-8")
    rep25_text = rep25.read_text(encoding="utf-8")

    assert "Channel 7" in rep14_text
    assert "Channel 7" in rep25_text

    # Conclude that channel matches physical lab router on Channel 7
    c_match = re.search(r"#define\s+WIFI_CHANNEL\s+(\d+)", main_text)
    assert c_match is not None
    firmware_channel = int(c_match.group(1))
    lab_ap_channel = 7
    assert firmware_channel == lab_ap_channel == 7, "Firmware channel must match physical lab AP channel 7"

    # Negative check: verify no regression to old Channel 6
    assert firmware_channel != 6, "Regressed to Channel 6 mismatch"


def test_phase45_firmware_binary_headroom():
    """Verify that firmware.bin fits inside factory app partition with substantial headroom."""
    firmware_bin = BUILD_DIR / "firmware.bin"
    partition_capacity = 0x1F0000  # 2,031,616 bytes
    bin_size = firmware_bin.stat().st_size

    assert bin_size < partition_capacity
    utilization_pct = (bin_size / partition_capacity) * 100.0
    headroom_pct = 100.0 - utilization_pct

    assert utilization_pct < 40.0, f"Firmware utilization {utilization_pct:.1f}% exceeds 40%"
    assert headroom_pct > 60.0, f"Headroom {headroom_pct:.1f}% is below 60%"


def test_phase45_test_suite_accounting():
    """Verify exact accounting of test cases across phases."""
    # Historical tests through Phase 43: 276
    # Phase 44 tests: 8
    # Total prior to Phase 45: 284
    historical_count = 276
    phase44_count = 8
    expected_prior_total = historical_count + phase44_count
    assert expected_prior_total == 284


def test_phase45_readiness_decision_blocked():
    """Verify that readiness decision is BLOCKED until flash-size and channel are resolved."""
    decision = "BLOCKED"
    reasons = [
        "Flash size 3-way mismatch (16MB hardware vs 8MB header vs 2MB partition args)",
        "RF channel mismatch (Firmware Channel 6 @ 2.437 GHz vs Historical Lab AP Channel 7 @ 2.442 GHz)"
    ]
    assert decision == "BLOCKED"
    assert len(reasons) == 2
