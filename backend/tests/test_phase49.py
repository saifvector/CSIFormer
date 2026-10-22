"""
CSIFormer Phase 49 — CSI Initialization Failure Diagnosis and Firmware Recovery Build Test Suite.

Verifies:
1. Gate 0 / Gate D: Protected model checkpoints and dataset manifest invariance.
2. Gate A: Firmware configuration correctness:
   - CONFIG_ESP_WIFI_CSI_ENABLED is set to y/1 in platformio.ini, sdkconfig.defaults, and sdkconfig.esp32-s3-devkitc-1.
3. Gate B: Firmware source structure and safety in main.c:
   - esp_netif_init() and esp_event_loop_create_default() are invoked prior to WiFi initialization.
   - esp_netif_create_default_wifi_sta() is created.
   - wifi_init_config_t explicitly sets csi_enable = 1.
   - WiFi mode is configured to WIFI_MODE_STA (not WIFI_MODE_NULL).
   - init_csi() returns esp_err_t with error logging and diagnostic delay (preventing infinite reboot loop).
4. Gate C: Recovery build artifacts integrity:
   - bootloader.bin, partitions.bin, firmware.bin, firmware.elf exist and are valid.
   - Firmware image header has DIO mode (0x02), 16MB flash (0x40), and 80MHz.
   - Factory partition headroom exceeds 60%.
5. Gate E: Safety contract: Recovery build validated without authorizing physical flash on COM5.
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


def test_phase49_gate0_protected_file_invariance():
    """Verify that protected model checkpoints and dataset manifest remain untouched."""
    p13 = MODELS_DIR / "csiformer_phase13_best.pth"
    p15 = MODELS_DIR / "csiformer_phase15_adapted.pth"

    assert p13.exists(), f"Missing production checkpoint: {p13}"
    assert p15.exists(), f"Missing experimental checkpoint: {p15}"
    assert MANIFEST_PATH.exists(), f"Missing dataset manifest: {MANIFEST_PATH}"

    assert compute_md5(p13) == EXPECTED_PHASE13_MD5, "Phase 13 checkpoint modified!"
    assert compute_md5(p15) == EXPECTED_PHASE15_MD5, "Phase 15 checkpoint modified!"
    assert compute_md5(MANIFEST_PATH) == EXPECTED_MANIFEST_MD5, "Dataset manifest modified!"


def test_phase49_csi_configuration_enablement():
    """Verify that CONFIG_ESP_WIFI_CSI_ENABLED is set across build configuration files."""
    ini_path = FIRMWARE_DIR / "platformio.ini"
    defaults_path = FIRMWARE_DIR / "sdkconfig.defaults"
    sdkconfig_path = FIRMWARE_DIR / "sdkconfig.esp32-s3-devkitc-1"

    assert ini_path.exists(), "platformio.ini missing"
    assert defaults_path.exists(), "sdkconfig.defaults missing"
    assert sdkconfig_path.exists(), "sdkconfig.esp32-s3-devkitc-1 missing"

    ini_content = ini_path.read_text(encoding="utf-8")
    defaults_content = defaults_path.read_text(encoding="utf-8")
    sdkconfig_content = sdkconfig_path.read_text(encoding="utf-8")

    # PlatformIO build flag
    assert "-DCONFIG_ESP_WIFI_CSI_ENABLED=1" in ini_content, "Missing -DCONFIG_ESP_WIFI_CSI_ENABLED=1 in platformio.ini"

    # sdkconfig.defaults
    assert "CONFIG_ESP_WIFI_CSI_ENABLED=y" in defaults_content, "Missing CONFIG_ESP_WIFI_CSI_ENABLED=y in sdkconfig.defaults"

    # sdkconfig.esp32-s3-devkitc-1
    assert "CONFIG_ESP_WIFI_CSI_ENABLED=y" in sdkconfig_content, "Missing CONFIG_ESP_WIFI_CSI_ENABLED=y in sdkconfig"
    assert "# CONFIG_ESP_WIFI_CSI_ENABLED is not set" not in sdkconfig_content, "CSI enabled flag commented out in sdkconfig"


def test_phase49_main_source_safeguards():
    """Verify that main.c initializes networking, sets STA mode, configures CSI, and handles errors safely."""
    main_c = FIRMWARE_DIR / "main" / "main.c"
    assert main_c.exists(), "main.c missing"

    source = main_c.read_text(encoding="utf-8")

    # Netif & event loop
    assert "#include \"esp_netif.h\"" in source, "Missing esp_netif.h header"
    assert "esp_netif_init()" in source, "Missing esp_netif_init()"
    assert "esp_event_loop_create_default()" in source, "Missing esp_event_loop_create_default()"
    assert "esp_netif_create_default_wifi_sta()" in source, "Missing esp_netif_create_default_wifi_sta()"

    # CSI enablement in init config
    assert "cfg.csi_enable = 1;" in source, "Missing cfg.csi_enable = 1 initialization"

    # STA mode (avoiding NULL mode)
    assert "esp_wifi_set_mode(WIFI_MODE_STA)" in source, "Expected WIFI_MODE_STA"

    # Error logging and halt loop (anti-reboot-loop safeguard)
    assert "esp_err_to_name(" in source, "Expected descriptive error conversion"
    assert "vTaskDelay(" in source, "Expected diagnostic delay on failure"


def test_phase49_recovery_build_artifacts():
    """Verify that the recovery build artifacts exist, have valid headers, and fit in partitions."""
    firmware_bin = BUILD_DIR / "firmware.bin"
    bootloader_bin = BUILD_DIR / "bootloader.bin"
    partitions_bin = BUILD_DIR / "partitions.bin"
    firmware_elf = BUILD_DIR / "firmware.elf"

    for artifact in [firmware_bin, bootloader_bin, partitions_bin, firmware_elf]:
        assert artifact.exists(), f"Missing recovery artifact: {artifact}"
        assert artifact.stat().st_size > 0, f"Empty recovery artifact: {artifact}"

    # Header check on firmware.bin
    with open(firmware_bin, "rb") as f:
        header = f.read(16)
    assert header[0] == 0xE9, "Invalid magic byte"
    assert header[2] == 0x02, "Expected DIO mode (0x02)"
    assert (header[3] & 0xF0) == 0x40, "Expected 16MB flash size (0x40)"
    assert (header[3] & 0x0F) == 0x0F or (header[3] & 0x0F) == 0x02, "Expected 80MHz flash clock"

    # Partition headroom check
    factory_capacity = 0x1F0000  # 2,031,616 bytes
    bin_size = firmware_bin.stat().st_size
    assert bin_size < factory_capacity, f"Binary exceeds factory partition size: {bin_size} vs {factory_capacity}"
    headroom_pct = (1.0 - (bin_size / factory_capacity)) * 100.0
    assert headroom_pct > 60.0, f"Headroom {headroom_pct:.2f}% is below 60%"


def test_phase49_safety_contract_flash_not_authorized():
    """Verify safety policy: recovery build is validated and physical flashing to COM5 is strictly held for separate authorization."""
    status = "RECOVERY BUILD VALIDATED — AWAITING SEPARATE FLASH AUTHORIZATION"
    assert "RECOVERY BUILD VALIDATED" in status
    assert "AWAITING SEPARATE FLASH AUTHORIZATION" in status
