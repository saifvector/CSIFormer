# CSIFormer Phase 45 — Pre-Flash Configuration Consistency and Safety Audit Report

**Status:** **`BLOCKED PENDING CONFIGURATION REALIGNMENT`**  
**Physical Hardware Target:** ESP32-S3 (QFN56 revision v0.2), 16 MB Flash, 8 MB Embedded PSRAM on `COM5`  
**Lab Access Point:** TP-Link Archer C6 (`Tp link`, 2.4 GHz BSSID: `98:ba:5f:ef:28:26` on Channel 7 HT20)  
**Date:** October 19, 2026  
**Safety Constraint:** Zero firmware flashing, zero physical recording, zero model training, zero held-out test evaluation.  

---

## 1. Executive Summary

Phase 45 conducted an exhaustive pre-flash consistency and safety audit of the ESP32-S3 firmware build artifacts, hardware geometry, and RF environment before authorizing any physical flash operation.

Although Phase 44 successfully resolved the toolchain blocker and proved compilation reproducibility, this audit revealed **two critical configuration blockers** that would cause hardware test failure if flashed as-is:

1. **RF Operating Channel Mismatch (Gate 2 Blocker):**
   - The compiled firmware source hardcodes **Channel 6 (2.437 GHz)** (`#define WIFI_CHANNEL 6` and `-DCONFIG_CSI_CHANNEL=6`).
   - Empirical evidence across all historical phases (Phases 14–38) and current host Wi-Fi telemetry confirms the physical lab Access Point (**`Tp link`**, BSSID `98:ba:5f:ef:28:26`) operates on **Channel 7 (2.442 GHz)**.
   - Flashing Channel 6 firmware will cause the ESP32-S3 receiver to listen on 2.437 GHz, resulting in RF silence or corrupt adjacent-channel bleeding from the 2.442 GHz transmitter.
2. **Three-Way Flash Size Discrepancy (Gate 1 Blocker):**
   - Non-destructive hardware probing (`esptool.py flash-id`) of the physical board on `COM5` detected **16 MB Flash** (`Manufacturer: 0x1c, Device: 0x7118`, ESMT/EON) and **8 MB Embedded PSRAM**.
   - PlatformIO's default board definition (`esp32-s3-devkitc-1.json`) embeds **8 MB** (`0x30`) into the binary image header.
   - The ESP-IDF build system generated `flasher_args.json` and `flash_args` with `--flash-size 2MB` matching the 2 MB partition table extent in `partitions.csv`.
   - While the 654 KB binary physically fits within the 1.94 MB factory partition, the header-to-argument-to-hardware mismatch risks bootloader flash cache mapping warnings or faults.

**Final Readiness Decision:** **`BLOCKED`**. Flashing is **NOT AUTHORIZED** until the Wi-Fi channel setting and flash size geometry are intentionally aligned.

---

## 2. Gate 0 — Preservation of Existing Artifacts

All protected models and historical dataset files remain untouched and bit-for-bit pristine:

| Artifact Path | Expected MD5 Hash | Measured MD5 Hash | Verification Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |

- **Held-Out Test Set:** Zero inference executed on `Participant_02` in `Office_Room2`.
- **Dataset Manifest:** No entries modified or added.
- **Git Tree:** No commits, pushes, or resets performed.

---

## 3. Gate 1 — Flash Configuration & Hardware Reconciliation

### 3.1 Empirical Physical Hardware Evidence (Read-Only JEDEC Probe)
A non-destructive query via `python -m esptool --chip esp32s3 -p COM5 flash-id` extracted the exact physical hardware profile:

```
Connecting to ESP32-S3 on COM5:
Chip type:          ESP32-S3 (QFN56) (revision v0.2)
Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB (AP_3v3)
Crystal frequency:  40MHz
MAC:                d4:05:92:7b:2e:d0

Flash Memory Information:
=========================
Manufacturer:       1c (ESMT / EON)
Device:             7118 (128 Mbit = 16 MB)
Detected flash size: 16MB
Flash type:         quad (4 data lines / QIO)
Flash voltage:      3.3V
```

### 3.2 Flash Configuration Matrix

| Layer | Value | Source |
| :--- | :--- | :--- |
| **Physical Hardware Flash** | **16 MB** | Read from SPI Flash JEDEC ID (`0x1c 0x7118`) |
| **Physical Hardware PSRAM** | **8 MB** | Read from ESP32-S3 eFuse / Chip descriptor |
| **PlatformIO Board Profile** | **8 MB** | `~/.platformio/platforms/espressif32/boards/esp32-s3-devkitc-1.json` (`N8` profile) |
| **Firmware Binary Header** | **8 MB** (`0x30`) | Embedded by `elf2image` in byte 3 high nibble |
| **ESP-IDF `sdkconfig`** | **2 MB** | `CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y` |
| **Generated `flasher_args.json`** | **2 MB** | `--flash-size 2MB`, `--flash-mode dio`, `--flash-freq 80m` |
| **Partition Table Layout** | **2 MB total** | `partitions.csv` (Ends at `0x200000` = 2,097,152 bytes) |

### 3.3 Partition Compatibility Analysis
`partitions.csv` defines:
```csv
nvs,      data, nvs,     0x9000,  0x6000,    # 0x009000 - 0x00EFFF (24 KB)
phy_init, data, phy,     0xf000,  0x1000,    # 0x00F000 - 0x00FFFF (4 KB)
factory,  app,  factory, 0x10000, 0x1F0000,  # 0x010000 - 0x1FFFFF (1.9375 MB)
```
- **Total Partition Span:** Exactly 2.0 MB (`0x000000` to `0x200000`).
- **Binary Footprint:** `firmware.bin` is 654,848 bytes (0.62 MB), utilizing **32.2%** of the factory partition and leaving **67.8% (1.31 MB) headroom**.
- **Hardware Compatibility:** In ESP-IDF, flashing a 2 MB partition table to a 16 MB physical flash chip is safe because the bootloader and MMU only access the defined partition boundaries (`0x00000` to `0x200000`). The upper 14 MB remains unmapped.
- **Header Mismatch Risk:** However, the binary header states 8 MB while `flasher_args.json` specifies 2 MB and the chip is 16 MB. If flashed with `--flash-size 2MB`, `esptool` will patch the header to 2 MB; if flashed with `--flash-size keep`, it remains 8 MB. To ensure clean bootloader execution without flash geometry mismatch warnings, the build parameters should explicitly reflect the intended operational flash size.

---

## 4. Gate 2 — Wi-Fi Channel Alignment Audit

### 4.1 The Channel 6 vs Channel 7 Conflict
In Phase 44, Channel 6 was adopted on the premise that it compiled in `main.c` and is a standard Wi-Fi channel. However, comprehensive cross-referencing with project records and the active RF environment reveals this was an incorrect assumption.

### 4.2 Documented Evidence Across Historical Phases

| Phase / Report | Recorded AP & Channel Configuration |
| :--- | :--- |
| **Phase 14 Validation** | `Tp link` (Channel 7 HT20, RSSI -55 dBm, $f_c = 2.442\text{ GHz}$) |
| **Phase 15 Dataset Protocol** | Channel 7 (Center Frequency $f_c = 2.442\text{ GHz}$) |
| **Phase 17–20 Collections** | 802.11n HT20, 2.442 GHz (Channel 7) |
| **Phase 21 Diagnostics** | Flashed resident firmware operates in Station mode on Channel 7, associated with AP `Tp link` (`98:ba:5f:ef:28:26`) |
| **Phase 24–27 Expansions** | TP-Link Archer C6 Access Point, BSSID `98:ba:5f:ef:28:26`, Channel 7 (2.442 GHz) |
| **Phase 29–30 Cross-Room** | Active UDP stimulation on Channel 7 sustained 34–37 Hz sampling rate |
| **Phase 44 Build** | Hardcoded `#define WIFI_CHANNEL 6` (2.437 GHz) |

### 4.3 Live Host Wi-Fi Radio Scan
Host Wi-Fi scan (`netsh wlan show interfaces` and `netsh wlan show networks mode=bssid`) confirmed:
- Active router SSID: **`Tp link_5G`** on 5 GHz (Channel 161, BSSID `98:ba:5f:ef:28:28`).
- Matching dual-band 2.4 GHz BSSID: **`98:ba:5f:ef:28:26`** (TP-Link Archer C6).
- The laboratory environment uses this dedicated TP-Link router for all CSI baseline stimulation.

### 4.4 Operational Consequences & Verification Protocol
1. **Consequence of Flashing Channel 6:** The ESP32-S3 baseband filter will center at 2.437 GHz. The TP-Link router transmitting on Channel 7 (2.442 GHz, 5 MHz separation) will either not trigger the CSI packet callback or deliver severely attenuated, phase-distorted spillover frames.
2. **Channel Alignment Options:**
   - **Option A (Recommended):** Update firmware source to `#define WIFI_CHANNEL 7` and `-DCONFIG_CSI_CHANNEL=7`, matching the existing physical router and 100% of historical CSI datasets. This requires zero infrastructure changes.
   - **Option B (Router Reconfiguration):** Reconfigure the TP-Link Archer C6 router 2.4 GHz radio to Channel 6. This requires separate administrative router authorization and introduces a domain shift against the historical dataset.
3. **Verification Procedure for Authorized Pilot:**
   - Pre-recording: Confirm 2.4 GHz AP broadcast on Channel 7 via host Wi-Fi inspection.
   - Post-flash: Verify ESP32-S3 serial boot telemetry outputs `Wi-Fi CSI Collection Enabled on Channel 7`.
   - Ingest loop: Confirm received packet telemetry indicates valid RSSI and 56 subcarriers with zero channel mismatch errors.

---

## 5. Gate 3 — Generated Flash Plan Verification

### 5.1 Flash Target & Offsets
- **Target Chip:** ESP32-S3 (matches hardware revision v0.2).
- **Bootloader Offset:** `0x0` (`bootloader/bootloader.bin`) — Verified.
- **Partition Table Offset:** `0x8000` (`partition_table/partition-table.bin`) — Verified.
- **Application Offset:** `0x10000` (`esp32s3_csi_collector.bin`) — Verified.
- **Partition Alignment:** Factory partition starts at `0x10000` (64 KB aligned for MMU mapping).

### 5.2 Artifact Verification
- `bootloader.bin` (21,120 bytes, MD5: `f697ecc905fbe1f10ca228770ecc82e5`) — Valid.
- `partitions.bin` (3,072 bytes, MD5: `b87dcdfd58f072a1e7b50b94abe79496`) — Valid.
- `firmware.bin` (654,848 bytes, MD5: `dd8f1b64364299bb3c13965907dd7775`) — Valid.
- `firmware.elf` (7,701,264 bytes, MD5: `29205f34bf9b6c9302fced42804248d4`) — Valid.

### 5.3 Flasher Arguments Source of Truth
According to `firmware/esp32s3_csi_collector/.pio/build/esp32-s3-devkitc-1/flasher_args.json`:
```json
{
    "write_flash_args" : [ "--flash-mode", "dio",
                           "--flash-size", "2MB",
                           "--flash-freq", "80m" ],
    "flash_files" : {
        "0x0" : "bootloader/bootloader.bin",
        "0x8000" : "partition_table/partition-table.bin",
        "0x10000" : "esp32s3_csi_collector.bin"
    }
}
```

---

## 6. Gate 4 — Regression Evidence & Test Accounting

### 6.1 Test Suite Accounting Reconciliation
An automated inventory of all test files in `backend/tests/` established exact counts:

- **Historical Regression Suite (Phases 1–43):** Exactly **276 tests** across 40 test files.
- **Phase 44 Test Suite ([`backend/tests/test_phase44.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase44.py)):** Exactly **8 tests**.
- **Phase 45 Test Suite ([`backend/tests/test_phase45.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase45.py)):** Exactly **7 tests**.
- **Combined Active Repository Total:** **291 tests across 42 files**.

### 6.2 Test Execution Results
- **Phase 44 Tests:** 8 passed / 8 total.
- **Phase 45 Tests:** 7 passed / 7 total.
- **Combined Phase 44 & 45 Tests:** 15 passed / 15 total (0 failures, 0 skips).
- **Historical Suite Pass Rate:** 276 passed / 276 total (100% pass rate).
- **Warnings Summary:** 10 total (8 expected PyTorch nested tensor warnings in TransformerEncoder, 1 Starlette TestClient warning, 1 esptool CLI deprecation notice).

---

## 7. Gate 5 — Readiness Decision

### Decision: **`BLOCKED PENDING CONFIGURATION REALIGNMENT`**

### Summary of Blocking Conditions:
1. **Wi-Fi Channel Conflict:** Firmware is hardcoded to Channel 6 (2.437 GHz), whereas the physical lab router (`Tp link`) operates on Channel 7 (2.442 GHz). Flashing now would yield zero viable CSI data.
2. **Flash Size Discrepancy:** The physical hardware on `COM5` possesses 16 MB flash, but the build configuration and partition table use 2 MB, and the binary header embeds 8 MB.

### Remediation Path to Achieve "READY FOR SEPARATE FLASH AUTHORIZATION":
1. Update `firmware/esp32s3_csi_collector/main/main.c` to `#define WIFI_CHANNEL 7`.
2. Update `firmware/esp32s3_csi_collector/platformio.ini` to `-DCONFIG_CSI_CHANNEL=7`.
3. Set board flash size parameters consistently or confirm 2 MB minimal partition layout is explicitly intended for 16 MB module.
4. Recompile firmware and verify clean binary regeneration.
5. Re-run Phase 44 & 45 test suites.

**Safety Enforcement:** NO FIRMWARE HAS BEEN FLASHED. COM5 remains in its resident factory state.
