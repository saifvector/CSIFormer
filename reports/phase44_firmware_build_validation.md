# CSIFormer Phase 44 — ESP32-S3 Build Environment Recovery and Firmware Validation Report

**Status:** BUILD PASSED — FLASH NOT AUTHORIZED  
**Target Hardware:** ESP32-S3-WROOM-1 / ESP32-S3-DevKitC-1  
**Framework:** ESP-IDF (via PlatformIO Core 6.2.0 / espressif32 @ 8.0.0)  
**Date:** October 19, 2026  
**Execution Environment:** Windows 11 (Workspace mapped via virtual drive `Z:\` to eliminate CMake path whitespace constraints)  

---

## 1. Executive Summary

Phase 44 resolved the build-toolchain blocker identified in Phase 43, establishing a 100% reproducible firmware build pipeline for the ESP32-S3 CSI collector (`firmware/esp32s3_csi_collector/`).

### Key Achievements:
1. **Toolchain Recovery:** Successfully installed PlatformIO Core (`pio` 6.2.0) and Espressif toolchains (`toolchain-xtensa-esp-elf` 15.2.0, `framework-espidf` 6.1.0, `tool-cmake` 3.30.2, `tool-ninja` 1.9.0, `esptool.py` 5.6.0).
2. **Whitespace Blocker Resolution:** Resolved the critical Windows path whitespace blocker (`C:\Users\saifu\Desktop\4-1 project`) by mounting a virtual drive (`subst Z: "C:\Users\saifu\Desktop\4-1 project"`), allowing CMake and Ninja to execute without parsing errors.
3. **Partition Table & Source Modernization:** Defined `partitions.csv` with a 1.9375 MB factory partition, updated `platformio.ini` source directory mappings, and modernized `main.c` for ESP-IDF v5/v6 compatibility (`wifi_csi_config_t` updates and safe format specifier casting).
4. **Successful Clean Compilation:** Compiled full firmware without flashing, generating valid `bootloader.bin`, `partitions.bin`, `firmware.bin`, and `firmware.elf`.
5. **Wi-Fi Channel Reconciled:** Reconciled historical Channel 7 vs Channel 6 references in favor of Channel 6 (2.437 GHz) as hardcoded in the firmware and `platformio.ini`.
6. **Integrity & Regressions:** Verified that protected model checkpoints and dataset manifest remain byte-for-byte identical; 276 existing regression tests and 8 new Phase 44 unit tests passed (100% pass rate).

> [!IMPORTANT]
> **CRITICAL SAFETY ENFORCEMENT:** Compilation and artifact inspection succeeded completely. However, **ZERO FLASHING HAS BEEN PERFORMED OR AUTHORIZED**. The live ESP32-S3 on COM5 remains untouched in its factory/legacy state. Physical flashing requires separate, explicit user authorization.

---

## 2. Gate 0 — Project & Model Integrity Preflight

All protected assets were verified before and after all build operations:

| Artifact | Expected MD5 | Observed MD5 | Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Untouched)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Untouched)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Untouched)** |

- Model retraining: **NONE**
- Held-out test set evaluation: **NONE**
- Physical data collection: **NONE**
- Git destructive operations: **NONE**

---

## 3. Build Toolchain Recovery (Gate 1 & Gate 2)

### 3.1 Toolchain Inventory
- **PlatformIO Core:** Version 6.2.0 installed in `.venv`
- **Platform:** `espressif32` @ 8.0.0
- **Framework:** `framework-espidf` @ 4.60100.0 (ESP-IDF 6.1.0)
- **Compiler:** `toolchain-xtensa-esp-elf` @ 15.2.0+20251204 (GCC 15.2.0)
- **Build System:** `tool-cmake` @ 3.30.2, `tool-ninja` @ 1.9.0
- **Flasher Utility:** `esptool.py` v5.6.0 (installed in `.venv`)

### 3.2 Windows Path Whitespace Mitigation
The repository directory path contains a space: `C:\Users\saifu\Desktop\4-1 project`.  
ESP-IDF's CMake scripts and GCC's `-fmacro-prefix-map` fail when paths contain spaces because Ninja command lines and ESP-IDF path generators split the path into separate tokens.

**Permanent, Non-Destructive Solution:**
A virtual drive mapping was established:
```powershell
subst Z: "C:\Users\saifu\Desktop\4-1 project"
```
Compilation executes against `Z:\firmware\esp32s3_csi_collector`, which provides a clean, single-token POSIX/Windows compatible path while directly pointing to the exact workspace files.

---

## 4. Firmware Configuration and Source Refactoring (Gate 3)

### 4.1 Project Configuration (`platformio.ini`)
The configuration was updated to explicitly point to the `main` source directory and custom partition table:
```ini
[platformio]
src_dir = main

[env:esp32-s3-devkitc-1]
platform = espressif32
board = esp32-s3-devkitc-1
framework = espidf
monitor_speed = 921600
upload_speed = 921600
board_build.partitions = partitions.csv

build_flags = 
    -DCONFIG_CSI_ENABLE=1
    -DCONFIG_CSI_CHANNEL=6
```

### 4.2 Custom Partition Table (`partitions.csv`)
An explicit ESP-IDF partition table was created to guarantee sufficient space for the application and NVS storage:
```csv
# ESP-IDF Partition Table
# Name,   Type, SubType, Offset,  Size, Flags
nvs,      data, nvs,     0x9000,  0x6000,
phy_init, data, phy,     0xf000,  0x1000,
factory,  app,  factory, 0x10000, 0x1F0000,
```
- Factory App partition size: `0x1F0000` (2,031,616 bytes / 1.9375 MB).

### 4.3 Modernization of `main.c`
1. **Header Inclusion:** Made `esp_spi_flash.h` conditionally included alongside modern `esp_flash.h` to maintain backward and forward compatibility across ESP-IDF versions.
2. **CSI Configuration Structure:** Updated `wifi_csi_config_t` initialization:
   - Deprecated `ltf2_en` replaced with `ltf_merge_en = true`.
   - Removed obsolete `rx_filter_len` field.
   - Added explicit `dump_ack_en = false`.
3. **Format Specifier Safety:** Cast `packet_sequence` to `(unsigned long)` to satisfy GCC's `-Werror=format=` check across 32-bit and 64-bit architectures.

---

## 5. Binary Inspection & Flash Offset Layout (Gate 4)

Compilation produced four primary artifacts in `firmware/esp32s3_csi_collector/.pio/build/esp32-s3-devkitc-1/`:

| Binary File | Size (Bytes) | MD5 Checksum | SHA-256 Checksum | Flash Offset |
| :--- | :--- | :--- | :--- | :--- |
| `bootloader.bin` | 21,120 (20.6 KB) | `f697ecc905fbe1f10ca228770ecc82e5` | `0b6ffffcb078cfd8d4739d31ad1cf08c6dfbb72de1a6a26c7007fa9facdacbf7` | `0x0` |
| `partitions.bin` | 3,072 (3.0 KB) | `b87dcdfd58f072a1e7b50b94abe79496` | `520c18ca0bda73aed288d427d260ab051d71219f605707350e6c42401f4836fc` | `0x8000` |
| `firmware.bin` | 654,848 (639.5 KB) | `dd8f1b64364299bb3c13965907dd7775` | `a4bd2ef7670ee17a8cdcfb310fea4d55c53020884c3c3fa3d3750a965329cc1a` | `0x10000` |
| `firmware.elf` | 7,701,264 (7.34 MB) | `29205f34bf9b6c9302fced42804248d4` | `a3a3f459276fbf877a3914486b5bace42e3e8e13c4bdfca13537b8bf17a467f6` | — |

### 5.1 Memory Utilization Summary
- **RAM Usage:** 35,004 bytes used out of 327,680 bytes (**10.7% utilization**, 292,676 bytes free).
- **Flash Memory Usage:** 654,429 bytes code used out of 2,031,616 bytes partition (**32.2% utilization**, 1,377,187 bytes / **67.8% headroom**).

### 5.2 `esptool.py image-info` Verification
Analysis of `firmware.bin` using `esptool.py v5.6.0`:
- **Target Chip:** ESP32-S3 (Chip ID: 9)
- **Flash Frequency / Mode:** 80 MHz, DIO mode
- **Header Checksum:** `0x0e` (VALID)
- **Image Validation Hash:** `0170fe1a7ff11216d1372fd978c4b017666072d8693108257f3aa25942a59ed6` (VALID)
- **Segment Breakdown:**
  - Segment 0 (DROM): `0x16170` bytes @ `0x3c080020`
  - Segment 1 (DRAM): `0x0517c` bytes @ `0x3fc97b00`
  - Segment 2 (IRAM): `0x04cfc` bytes @ `0x40374000`
  - Segment 3 (IROM): `0x70fb4` bytes @ `0x42000020`
  - Segment 4 (IRAM): `0x0edd4` bytes @ `0x40378cfc`
  - Segment 5 (RTC_DATA): `0x00024` bytes @ `0x50000000`

### 5.3 Flash Offsets & Arguments Layout
According to generated `flasher_args.json`:
- Bootloader: `0x0`
- Partition Table: `0x8000`
- Factory App: `0x10000`

Theoretical flashing command (for future reference upon explicit authorization):
```powershell
python -m esptool --chip esp32s3 -p <PORT> -b 921600 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_freq 80m --flash_size 2MB 0x0 bootloader.bin 0x8000 partitions.bin 0x10000 firmware.bin
```

---

## 6. Wi-Fi Channel Reconciled: Channel 6 vs Channel 7

During Phase 42–43, a discrepancy was noted between historical Phase 24 notes (which mentioned Channel 7 / 2.442 GHz) and the repository firmware source (`firmware/esp32s3_csi_collector/main/main.c`), which configures Channel 6.

### Resolution:
1. **Source & Build Configuration:** Both `main.c` (`#define WIFI_CHANNEL 6`) and `platformio.ini` (`-DCONFIG_CSI_CHANNEL=6`) hardcode **Channel 6** (center frequency 2.437 GHz).
2. **RF Standard:** Channel 6 is an internationally standardized, non-overlapping 20 MHz Wi-Fi channel in the 2.4 GHz band (Channels 1, 6, 11). Channel 7 overlaps significantly with adjacent channels.
3. **Operational Policy:** Channel 6 is confirmed as the definitive target channel. Any physical Wi-Fi AP or transmitter utilized during future pilot collections must be configured to broadcast beacon frames on **Channel 6 (2.437 GHz)**.

---

## 7. UART Telemetry and Format B Parser Alignment

The firmware formats serial CSI telemetry using Format B:
```c
CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,amp_1:phase_1,...
```

### Host Alignment Validation:
- Host receiver `backend/app/services/real_csi_collector.py` parses lines starting with `CSI_DATA`.
- Unit test `test_phase44_uart_format_b_parser_alignment` verified end-to-end telemetry parsing of a 64-subcarrier frame:
  - MAC address: `AA:BB:CC:DD:EE:FF` correctly parsed.
  - RSSI: `-54.0 dBm` correctly parsed.
  - Noise floor: `-91.0 dBm` correctly parsed.
  - Sequence number: `42` correctly parsed.
  - Subcarriers: 64 amplitudes and 64 phases extracted with zero numerical distortion.
  - Protocol state transitions to `structured_csi_data`.

---

## 8. Verification & Regression Testing (Gate 5)

### 8.1 Phase 44 Test Suite (`backend/tests/test_phase44.py`)
Eight dedicated unit tests verify all Phase 44 requirements:
1. `test_phase44_protected_file_invariance`: PASSED
2. `test_phase44_toolchain_availability`: PASSED
3. `test_phase44_platformio_config`: PASSED
4. `test_phase44_firmware_source_channel_and_baud`: PASSED
5. `test_phase44_build_artifacts_existence_and_sizes`: PASSED
6. `test_phase44_flash_offsets`: PASSED
7. `test_phase44_uart_format_b_parser_alignment`: PASSED
8. `test_phase44_flash_not_authorized`: PASSED

### 8.2 Full Regression Suite
- Total tests executed: **276 passed** (0 failures, 10 expected PyTorch nested tensor warnings).
- Execution time: 125.91s.
- Zero regressions across previous phases (Phases 1–43).

---

## 9. Conclusion & Pilot Readiness Gate

Phase 44 has completely satisfied all objectives for toolchain recovery and firmware build reproducibility:
1. ESP-IDF build environment is healthy, reproducible, and verified.
2. Binary images are compiled, verified, and ready in `firmware/esp32s3_csi_collector/.pio/build/esp32-s3-devkitc-1/`.
3. Channel 6 and 921,600 baud parameters are unified across firmware, build configuration, and host parser.
4. Protected model checkpoints and dataset manifest remain byte-for-byte identical.

**Current Safety Posture:**  
- Flash status: **NOT AUTHORIZED / UNFLASHED**
- COM5 hardware status: **CONNECTED / RUNNING LEGACY FIRMWARE (115,200 baud)**
- Pilot recording: **SUSPENDED PENDING USER AUTHORIZATION**
