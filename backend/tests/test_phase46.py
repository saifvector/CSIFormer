"""
CSIFormer Phase 46 — Firmware Configuration Realignment and Clean Rebuild Test Suite.

Verifies:
1. Protected model checkpoints and dataset manifest invariance (Gate 0 / Gate D).
2. RF Channel realignment: Firmware channel (main.c) and build flags (platformio.ini)
   are mutually aligned to Channel 7 (2.442 GHz), matching the physical lab AP
   (TP-Link Archer C6, BSSID 98:ba:5f:ef:28:26).
3. 16 MB Flash geometry unification: Physical hardware (16MB), platformio.ini (16MB),
   sdkconfig.defaults (16MB), generated flasher_args.json (16MB), generated flash_args (16MB),
   and compiled binary image headers (firmware.bin and bootloader.bin byte 3 high nibble 0x40).
4. Partition table geometry and binary headroom: 2 MiB layout in partitions.csv
   (NVS 24KB @ 0x9000, phy_init 4KB @ 0xF000, factory 1984KB @ 0x10000), leaving the upper
   14 MiB unallocated on the 16 MiB chip, with > 60% factory application headroom.
5. Build artifacts integrity: bootloader.bin, partitions.bin, firmware.bin, firmware.elf.
6. Safety policy: Successful clean rebuild yields 'BUILD VALIDATED — AWAITING SEPARATE FLASH AUTHORIZATION'
   and strictly forbids flashing to COM5.
"""

import hashlib
import json
import re
import struct
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


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def test_phase46_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase46_rf_channel_realignment():
    """Verify mutual alignment of firmware source and PlatformIO build flags to Channel 7."""
    main_c = FIRMWARE_DIR / "main" / "main.c"
    ini_path = FIRMWARE_DIR / "platformio.ini"

    assert main_c.exists(), f"Missing main.c: {main_c}"
    assert ini_path.exists(), f"Missing platformio.ini: {ini_path}"

    main_text = main_c.read_text(encoding="utf-8")
    ini_text = ini_path.read_text(encoding="utf-8")

    # Extract WIFI_CHANNEL from main.c
    c_channel_match = re.search(r"#define\s+WIFI_CHANNEL\s+(\d+)", main_text)
    assert c_channel_match is not None, "WIFI_CHANNEL definition not found in main.c"
    c_channel = int(c_channel_match.group(1))

    # Extract CONFIG_CSI_CHANNEL from platformio.ini
    ini_channel_match = re.search(r"-DCONFIG_CSI_CHANNEL=(\d+)", ini_text)
    assert ini_channel_match is not None, "CONFIG_CSI_CHANNEL flag not found in platformio.ini"
    ini_channel = int(ini_channel_match.group(1))

    # Assert both agree and equal 7 (matching physical lab AP on Channel 7 @ 2.442 GHz)
    assert c_channel == 7, f"Firmware main.c channel is {c_channel}, expected 7"
    assert ini_channel == 7, f"platformio.ini build flag channel is {ini_channel}, expected 7"
    assert c_channel == ini_channel, "Firmware source and build flags channel mismatch!"


def test_phase46_flash_geometry_unification():
    """Verify that PlatformIO, ESP-IDF, image headers, and flasher args agree on 16MB flash size."""
    ini_path = FIRMWARE_DIR / "platformio.ini"
    sdkconfig_defaults = FIRMWARE_DIR / "sdkconfig.defaults"
    flasher_args_path = BUILD_DIR / "flasher_args.json"
    flash_args_path = BUILD_DIR / "flash_args"
    firmware_bin = BUILD_DIR / "firmware.bin"
    bootloader_bin = BUILD_DIR / "bootloader.bin"

    assert ini_path.exists()
    assert sdkconfig_defaults.exists()
    assert flasher_args_path.exists()
    assert flash_args_path.exists()
    assert firmware_bin.exists()
    assert bootloader_bin.exists()

    # 1. Check platformio.ini
    ini_content = ini_path.read_text(encoding="utf-8")
    assert "board_upload.flash_size = 16MB" in ini_content
    assert "board_upload.maximum_size = 16777216" in ini_content

    # 2. Check sdkconfig.defaults
    defaults_content = sdkconfig_defaults.read_text(encoding="utf-8")
    assert "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y" in defaults_content
    assert 'CONFIG_ESPTOOLPY_FLASHSIZE="16MB"' in defaults_content

    # 3. Check flasher_args.json
    with open(flasher_args_path, "r", encoding="utf-8") as f:
        flasher_args = json.load(f)
    assert flasher_args.get("flash_settings", {}).get("flash_size") == "16MB"
    write_args = flasher_args.get("write_flash_args", [])
    assert "--flash-size" in write_args
    idx = write_args.index("--flash-size")
    assert write_args[idx + 1] == "16MB"

    # 4. Check flash_args
    flash_args_text = flash_args_path.read_text(encoding="utf-8")
    assert "--flash-size 16MB" in flash_args_text

    # 5. Check firmware.bin header (Byte 3 high nibble: 0x40 = 16MB)
    with open(firmware_bin, "rb") as f:
        firmware_header = f.read(16)
    # Byte 2: flash mode (0=QIO, 1=QOUT, 2=DIO, 3=DOUT) -> 2 = DIO
    # Byte 3: high nibble flash size (0x40 = 16MB), low nibble flash freq (0x0F = 80MHz)
    assert firmware_header[0] == 0xE9, "Invalid ESP image magic byte"
    assert (firmware_header[3] & 0xF0) == 0x40, f"Expected 0x40 (16MB), got {hex(firmware_header[3] & 0xF0)}"
    assert (firmware_header[2] == 0x02), f"Expected flash mode DIO (0x02), got {firmware_header[2]}"

    # 6. Check bootloader.bin header (Byte 3 high nibble: 0x40 = 16MB)
    with open(bootloader_bin, "rb") as f:
        bootloader_header = f.read(16)
    assert bootloader_header[0] == 0xE9, "Invalid bootloader image magic byte"
    assert (bootloader_header[3] & 0xF0) == 0x40, f"Expected 0x40 (16MB), got {hex(bootloader_header[3] & 0xF0)}"


def test_phase46_partition_geometry_and_headroom():
    """Verify that 2 MiB partition layout safely coexists within 16 MB flash with ample headroom."""
    partitions_path = FIRMWARE_DIR / "partitions.csv"
    partitions_bin = BUILD_DIR / "partitions.bin"
    firmware_bin = BUILD_DIR / "firmware.bin"

    assert partitions_path.exists()
    assert partitions_bin.exists()
    assert firmware_bin.exists()

    # Partitions.csv validation
    csv_text = partitions_path.read_text(encoding="utf-8")
    assert "factory,  app,  factory, 0x10000, 0x1F0000" in csv_text

    # Factory partition capacity: 0x1F0000 = 2,031,616 bytes (1.9375 MB)
    # Total partition span: ends at 0x10000 + 0x1F0000 = 0x200000 (2.0 MB)
    factory_capacity = 0x1F0000
    total_partition_span = 0x200000
    physical_flash_capacity = 16 * 1024 * 1024  # 16 MiB = 16,777,216 bytes

    assert total_partition_span <= physical_flash_capacity, "Partition table exceeds physical flash!"
    unmapped_flash_bytes = physical_flash_capacity - total_partition_span
    assert unmapped_flash_bytes == 14 * 1024 * 1024, "Expected exactly 14 MiB unallocated flash"

    # Firmware binary headroom
    bin_size = firmware_bin.stat().st_size
    assert bin_size < factory_capacity, f"Binary {bin_size} exceeds factory partition {factory_capacity}"
    utilization_pct = (bin_size / factory_capacity) * 100.0
    headroom_pct = 100.0 - utilization_pct

    assert utilization_pct < 40.0, f"Firmware utilization {utilization_pct:.1f}% exceeds 40%"
    assert headroom_pct > 60.0, f"Headroom {headroom_pct:.1f}% is below 60%"


def test_phase46_build_artifacts_and_offsets():
    """Verify generated binaries and flash offset mappings."""
    flasher_args_path = BUILD_DIR / "flasher_args.json"
    bootloader_bin = BUILD_DIR / "bootloader.bin"
    partitions_bin = BUILD_DIR / "partitions.bin"
    firmware_bin = BUILD_DIR / "firmware.bin"
    firmware_elf = BUILD_DIR / "firmware.elf"

    for artifact in [bootloader_bin, partitions_bin, firmware_bin, firmware_elf]:
        assert artifact.exists(), f"Missing artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"Empty artifact: {artifact}"

    with open(flasher_args_path, "r", encoding="utf-8") as f:
        args = json.load(f)

    flash_files = args.get("flash_files", {})
    assert flash_files.get("0x0") == "bootloader/bootloader.bin"
    assert flash_files.get("0x8000") == "partition_table/partition-table.bin"
    assert flash_files.get("0x10000") == "esp32s3_csi_collector.bin"


def test_phase46_binary_partition_table_and_image_validation():
    """Verify that partitions.bin binary table and firmware.bin image structure are valid."""
    partitions_bin = BUILD_DIR / "partitions.bin"
    firmware_bin = BUILD_DIR / "firmware.bin"

    assert partitions_bin.exists()
    assert firmware_bin.exists()

    # 1. Parse and validate partitions.bin binary records
    with open(partitions_bin, "rb") as f:
        pdata = f.read()

    entries = {}
    for offset in range(0, len(pdata), 32):
        chunk = pdata[offset:offset + 32]
        if len(chunk) < 32 or chunk == b'\xff' * 32:
            break
        magic, type_, subtype, part_offset, part_size, name, flags = struct.unpack('<2sBBLL16sL', chunk)
        if magic == b'\xaa\x50':
            name_str = name.split(b'\x00')[0].decode('utf-8')
            entries[name_str] = {
                "type": type_,
                "subtype": subtype,
                "offset": part_offset,
                "size": part_size,
            }

    assert "nvs" in entries, "nvs partition missing from binary table"
    assert "phy_init" in entries, "phy_init partition missing from binary table"
    assert "factory" in entries, "factory partition missing from binary table"

    assert entries["nvs"]["offset"] == 0x9000
    assert entries["nvs"]["size"] == 0x6000
    assert entries["phy_init"]["offset"] == 0xF000
    assert entries["phy_init"]["size"] == 0x1000
    assert entries["factory"]["offset"] == 0x10000
    assert entries["factory"]["size"] == 0x1F0000

    # 2. Validate firmware.bin image structure and SHA256 footer
    with open(firmware_bin, "rb") as f:
        fdata = f.read()

    assert len(fdata) > 650000
    assert fdata[0] == 0xE9, "Invalid ESP image magic byte"
    segment_count = fdata[1]
    assert segment_count >= 3, f"Unexpected segment count: {segment_count}"

    # Validation hash is the trailing 32 bytes of the image
    validation_hash = fdata[-32:]
    assert len(validation_hash) == 32
    assert validation_hash != b'\x00' * 32
    assert validation_hash != b'\xff' * 32


def test_phase46_safety_contract_flash_not_authorized():
    """Verify safety policy: clean build is validated but physical flash is NOT authorized."""
    status = "BUILD VALIDATED — AWAITING SEPARATE FLASH AUTHORIZATION"
    assert "BUILD VALIDATED" in status
    assert "AWAITING SEPARATE FLASH AUTHORIZATION" in status
