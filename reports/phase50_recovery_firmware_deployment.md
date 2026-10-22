# CSIFormer Phase 50 — Recovery Firmware Deployment and CSI Driver Verification Report

**Status:** **`RECOVERY FIRMWARE VERIFIED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION`**  
**Physical Hardware Target:** ESP32-S3 (QFN56 revision v0.2), 16 MB Flash, 8 MB Embedded PSRAM on `COM5`  
**Lab Access Point:** TP-Link Archer C6 (`Tp link`, BSSID: `98:ba:5f:ef:28:26`, Channel 7 HT20 @ 2.442 GHz)  
**Date:** October 19, 2026  
**Safety Protocol:** Explicit user flash authorization confirmed; zero full-chip erase; zero dataset admissions; zero model retraining; protected model checkpoints and dataset manifest preserved bit-for-bit.

---

## 1. Executive Summary

Phase 50 successfully deployed the Phase 49 recovery firmware to the physical ESP32-S3 on `COM5` after securing explicit user authorization. Prior to deployment, pre-flash validation confirmed hardware identity (ESP32-S3 v0.2, 16 MB flash), physical presence of the Lab AP on Channel 7, and byte-for-byte cryptographic agreement of all build artifacts with the Phase 49 release gate.

Flashing was performed without a full-chip erase via the PlatformIO/ESP-IDF toolchain (`esptool v5.4.0`) at 921,600 baud, writing the bootloader (21,120 bytes @ `0x0`), partition table (3,072 bytes @ `0x8000`), and recovery application (771,072 bytes @ `0x10000`) with complete cryptographic hash verification.

Fresh boot monitoring captured stable hardware execution: the second-stage bootloader initialized the 16 MB flash in DIO mode at 80 MHz, mapped the application, and invoked `app_main()`. All subsystems initialized cleanly:
- `nvs_flash_init()`: `ESP_OK`
- `esp_netif_init()`: `ESP_OK`
- `esp_event_loop_create_default()`: `ESP_OK`
- `esp_netif_create_default_wifi_sta()`: completed
- `esp_wifi_init(&cfg)` (with `cfg.csi_enable = 1`): `ESP_OK`
- `esp_wifi_set_mode(WIFI_MODE_STA)`: `ESP_OK`
- `esp_wifi_start()`: `ESP_OK`
- `esp_wifi_set_channel(7)`: `ESP_OK`
- `esp_wifi_set_promiscuous(true)`: `ESP_OK`
- `esp_wifi_set_csi_config(&csi_config)`: **`ESP_OK`** (previously aborting with `ESP_FAIL` in Phase 48)
- `esp_wifi_set_csi_rx_cb()`: `ESP_OK`
- `esp_wifi_set_csi(true)`: `ESP_OK`

The physical hardware smoke test verified live, non-interpolated CSI frames streaming over serial from the lab AP (`98:BA:5F:EF:28:26`), with 27 packets parsed in an 8.25-second test window (0 parse errors, 64 physical OFDM subcarriers, RSSI -59 dBm). All 43 test assertions across Phases 42–50 passed cleanly. Protected model checkpoints and the dataset manifest remain completely unaltered.

---

## 2. Gate 1 — Explicit User Flash Authorization

Pursuant to Section 1 of the Phase 50 protocol, flash authorization was solicited interactively before initiating any write operation:

- **Interactive Authorization Prompt:**
  `"Do you explicitly authorize flashing the Phase 49 recovery firmware to the physical ESP32-S3 on COM5 and executing boot verification and the CSI smoke test?"`
- **Confirmed Response:**
  `A1: (Recommended) Yes, I explicitly authorize flashing the Phase 49 recovery firmware to the ESP32-S3 on COM5 and executing the boot verification and CSI smoke test.`
- **Authorization Basis:** Unambiguous affirmative selection recorded in trajectory at step index 10007.
- **Authorization Status:** **PASSED — EXPLICIT AUTHORIZATION CONFIRMED**

---

## 3. Gate 2 — Pre-Flash Hardware and Artifact Validation

### 3.1 Hardware and RF Environment Verification
- **Target Serial Port:** `COM5` (Espressif USB-JTAG/Serial debug bridge, VID/PID `303A:1001`)
- **Chip Architecture:** ESP32-S3 (QFN56) revision v0.2
- **Features:** Wi-Fi, BLE 5, Dual Core + LP Core, 240 MHz, Embedded PSRAM 8 MB (`AP_3v3`)
- **MAC Address:** `d4:05:92:7b:2e:d0`
- **Flash Memory ID (`esptool flash-id`):**
  - Manufacturer: `0x1c` (ESMT / EON)
  - Device ID: `0x7118`
  - Flash Capacity: 16 MB (`16,777,216` bytes)
  - Flash Mode / Voltage: Quad (4 lines), 3.3V
- **Lab Access Point:**
  - SSID: `Tp link` / `Tp link_5G` (TP-Link Archer C6, base MAC prefix `98:ba:5f:ef:28`)
  - Target 2.4 GHz BSSID: `98:ba:5f:ef:28:26`
  - Operating Channel: Channel 7 HT20 @ 2.442 GHz

### 3.2 Artifact Cryptographic Hash Verification
All disk release artifacts matched the Phase 49 validated hashes bit-for-bit:

| Artifact | Size | Expected Phase 49 MD5 | Measured Phase 50 MD5 | Verification |
| :--- | :--- | :--- | :--- | :--- |
| `bootloader.bin` | 21,120 bytes | `977c6e03e9b3eba833a620e9889c1ea9` | `977c6e03e9b3eba833a620e9889c1ea9` | **EXACT MATCH** |
| `partitions.bin` | 3,072 bytes | `b87dcdfd58f072a1e7b50b94abe79496` | `b87dcdfd58f072a1e7b50b94abe79496` | **EXACT MATCH** |
| `firmware.bin` | 771,072 bytes | `1846112327086b0202f1d825d6f96b2e` | `1846112327086b0202f1d825d6f96b2e` | **EXACT MATCH** |
| `flasher_args.json`| 959 bytes | `48027a4ad660f30cc1b4714c0218b8ac` | `48027a4ad660f30cc1b4714c0218b8ac` | **EXACT MATCH** |
| `flash_args` | 163 bytes | `2458eee62cf04463972a1f9c280e3857` | `2458eee62cf04463972a1f9c280e3857` | **EXACT MATCH** |

---

## 4. Gate 3 — Controlled Firmware Deployment

### 4.1 Invocation Details
- **Command Executed:**
  ```powershell
  Z:\.venv\Scripts\pio.exe run -d Z:\firmware\esp32s3_csi_collector -t upload --upload-port COM5 -v
  ```
- **Underlying Flasher Command:**
  ```text
  "C:\Users\saifu\.platformio\packages\tool-esptool\esptool" \
    --chip esp32s3 --port "COM5" --baud 921600 \
    --before default-reset --after hard-reset \
    write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
    0 Z:\firmware\esp32s3_csi_collector\.pio\build\esp32-s3-devkitc-1\bootloader.bin \
    0x8000 Z:\firmware\esp32s3_csi_collector\.pio\build\esp32-s3-devkitc-1\partitions.bin \
    0x10000 .pio\build\esp32-s3-devkitc-1\firmware.bin
  ```

### 4.2 Flashing Execution Metrics
- **Tool Version:** `esptool v5.4.0`
- **Target Serial Port:** `COM5`
- **Upload Baud Rate:** `921,600` baud
- **Flash Geometry:** `--flash-mode dio --flash-freq 80m --flash-size 16MB`
- **Erase Scope:** Targeted sector erasure only (`write-flash -z`); **zero full-chip erase**.
- **Payload Written:**
  - `0x00000000` (Bootloader): 21,120 bytes (13,593 compressed) at 425.8 kbit/s -> **Hash of data verified**
  - `0x00008000` (Partition Table): 3,072 bytes (105 compressed) at 647.3 kbit/s -> **Hash of data verified**
  - `0x00010000` (Factory App): 771,072 bytes (502,785 compressed) at 795.6 kbit/s -> **Hash of data verified**
- **Hardware Reset:** `Hard resetting via RTS pin...`
- **Duration / Exit Code:** 44.15 seconds, Exit Code `0` (`[SUCCESS] Took 44.15 seconds`)

---

## 5. Gate 4 — Boot Verification and Initialization Return Codes

### 5.1 Serial Boot Capture
A serial monitor connection on `COM5` captured the fresh post-flash boot sequence:

```text
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)
SPIWP:0xee
mode:DIO, clock div:1
load:0x3fce2820,len:0x14f0
load:0x403c8700,len:0xde4
load:0x403cb700,len:0x2f58
entry 0x403c88fc
I (24) boot: ESP-IDF 6.1.0 2nd stage bootloader
I (25) boot: compile time Oct 19 2026 23:21:10
I (25) boot: Multicore bootloader
I (25) boot: chip revision: v0.2
I (28) boot: efuse block revision: v1.4
I (31) boot.esp32s3: Boot SPI Speed : 80MHz
I (35) boot.esp32s3: SPI Mode       : DIO
I (39) boot.esp32s3: SPI Flash Size : 16MB
I (43) boot: Enabling RNG early entropy source...
I (47) boot: Partition Table:
I (50) boot: ## Label            Usage          Type ST Offset   Length
I (56) boot:  0 nvs              WiFi data        01 02 00009000 00006000
I (63) boot:  1 phy_init         RF data          01 01 0000f000 00001000
I (69) boot:  2 factory          factory app      00 00 00010000 001f0000
I (76) boot: End of partition table
I (79) esp_image: segment 0: paddr=00010020 vaddr=3c090020 size=1b01ch (110620) map
I (106) esp_image: segment 1: paddr=0002b044 vaddr=3fc97c00 size=04fd4h ( 20436) load
I (111) esp_image: segment 2: paddr=00030020 vaddr=42000020 size=886bch (558780) map
I (213) esp_image: segment 3: paddr=000b86e4 vaddr=3fc9cbd4 size=001b8h (   440) load
I (214) esp_image: segment 4: paddr=000b88a4 vaddr=40374000 size=13b0ch ( 80652) load
I (236) esp_image: segment 5: paddr=000cc3b8 vaddr=50000000 size=00024h (    36) load
I (245) boot: Loaded app from partition at offset 0x10000
I (245) boot: Disabling RNG early entropy source...
I (255) cpu_start: Multicore app
I (263) cpu_start: GPIO 44 and 43 are used as console UART I/O pins
I (264) cpu_start: Pro cpu start user code
I (264) cpu_start: cpu freq: 160000000 Hz
I (266) app_init: Application information:
I (269) app_init: Project name:     esp32s3_csi_collector
I (274) app_init: App version:      16cb232-dirty
I (279) app_init: Compile time:     Oct 19 2026 23:18:05
I (284) app_init: ELF file SHA256:  b5262e456...
I (288) app_init: ESP-IDF:          6.1.0
I (351) main_task: Started on CPU0
I (381) main_task: Calling app_main()
I (401) ESP32S3_CSI_COLLECTOR: Initializing ESP32-S3 Wi-Fi CSI Sensing Node...
I (411) wifi:wifi driver task: 3fceeb84, prio:23, stack:6656, core=0
I (491) phy_init: phy_version 712,87e8c20e,Apr 13 2026,18:51:10
I (541) wifi:mode : sta (d4:05:92:7b:2e:d0)
I (541) wifi:enable tsf
I (551) wifi:ic_enable_sniffer
I (551) ESP32S3_CSI_COLLECTOR: Wi-Fi CSI Collection Enabled on Channel 7
I (551) ESP32S3_CSI_COLLECTOR: ESP32-S3 CSI Node Active & Streaming Telemetry on Channel 7...
I (561) main_task: Returned from app_main()
```

### 5.2 API Initialization Return Code Matrix

| API Call | Expected Return | Actual Return | Return Name | Status |
| :--- | :--- | :--- | :--- | :--- |
| `nvs_flash_init()` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_netif_init()` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_event_loop_create_default()` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_netif_create_default_wifi_sta()` | Non-null pointer | Valid pointer | N/A | **SUCCESS** |
| `esp_wifi_init(&cfg)` (`csi_enable=1`) | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_storage(RAM)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_mode(WIFI_MODE_STA)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_start()` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_channel(7)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_promiscuous(true)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_csi_config(&csi_config)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS (FIX VERIFIED)** |
| `esp_wifi_set_csi_rx_cb(wifi_csi_cb)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |
| `esp_wifi_set_csi(true)` | `ESP_OK` | `0x00000000` | `ESP_OK` | **SUCCESS** |

---

## 6. Gate 5 — Hardware CSI Smoke Test and Telemetry Validation

### 6.1 Live Acquisition Metrics
A dedicated non-recording smoke test (`scratch/run_csi_smoke_test.py`) was executed to capture live CSI telemetry from the ESP32-S3 over `COM5`:

- **Elapsed Duration:** 8.25 seconds
- **Total Bytes Received:** 28,006 bytes
- **Total Lines Received:** 116 lines
- **CSI Packets Parsed:** 27 packets
- **Parse Errors:** 0 (100% parse success rate)
- **Average Ingest Packet Rate:** 3.27 Hz (real beacon and data frames from lab AP)
- **Signal Quality Metrics:**
  - RSSI Range: `-59.0 dBm` to `-62.0 dBm` (strong, stable signal)
  - Noise Floor: `-91.0 dBm` to `-93.0 dBm`
  - Computed SNR: ~32 dB (well above the 15 dB threshold)
- **Serial Connection Release:** True (port closed cleanly upon test termination)

### 6.2 Telemetry Packet Structure
Representative Format B packet captured live from the Archer C6 router (`98:BA:5F:EF:28:26`):
```text
CSI_DATA,98:BA:5F:EF:28:26,-62,-93,1,64,0.00:0.000,5.83:-1.030,10.20:-1.373,13.34:-1.344,17.46:-1.340,18.44:-1.352,20.40:-1.373,21.59:-1.337,21.59:-1.337,21.38:-1.383,19.65:-1.313,17.46:-1.340,14.32:-1.360,11.40:-1.305,7.62:-1.166,4.47:-1.107,2.00:0.000,4.00:1.571,7.07:1.713,9.49:1.893,10.77:1.951,12.53:2.070,13.60:2.200,13.45:2.304,12.73:2.356,10.82:2.554,10.30:2.634,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,0.00:0.000,16.12:-1.695,16.00:-1.571,16.00:-1.571,15.00:-1.571,13.04:-1.494,12.00:-1.571,9.00:-1.571,6.08:-1.736,4.12:-1.816,2.00:3.142,4.47:2.678,7.21:2.159,9.43:2.129,13.00:1.966,14.32:2.003,16.76:1.874,17.72:1.857,18.44:1.789,19.42:1.778,19.10:1.676,18.25:1.736,17.12:1.688,14.00:1.571,12.04:1.488,9.06:1.460,4.12:1.326
```

### 6.3 Physical vs Derived Channel Characteristics
- **Raw Dimensions:** 64 subcarriers (52 data subcarriers, 4 pilot subcarriers, and 8 guard/null subcarriers).
- **Physical Provenance:** Amplitudes show characteristic frequency-selective multipath fading across OFDM subcarriers (varying between 2.00 and 22.56) with non-synthetic, continuous phase gradients. Zero artificial interpolation or synthetic noise was injected.

---

## 7. Gate 6 — Protected Asset Invariance & Regression Results

### 7.1 Protected Model Checkpoint & Manifest Checksums

| Resource | Expected Cryptographic MD5 | Measured Cryptographic MD5 | Disposition |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **PRISTINE** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **PRISTINE** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **PRISTINE** |

- **Dataset Sessions Admitted:** 0
- **Model Retraining:** None
- **Held-out Partition Inference:** None

### 7.2 Regression Test Execution Summary

| Test File | Description | Assertions | Result |
| :--- | :--- | :--- | :--- |
| `backend/tests/test_phase42.py` | Transport budget, parser, pilot isolation | 7 | **7 PASSED** |
| `backend/tests/test_phase43.py` | Hardware port discovery, subcarrier rules | 5 | **5 PASSED** |
| `backend/tests/test_phase44.py` | Toolchain, build artifacts, offsets | 8 | **8 PASSED** |
| `backend/tests/test_phase45.py` | Pre-flash configuration audit | 7 | **7 PASSED** |
| `backend/tests/test_phase46.py` | Flash geometry, channel realignment | 7 | **7 PASSED** |
| `backend/tests/test_phase49.py` | CSI enablement, source safeguards | 5 | **5 PASSED** |
| `backend/tests/test_phase50.py` | Deployment verification, Format B telemetry | 4 | **4 PASSED** |
| **Total Regression Assertions** | **Phases 42 through 50** | **43** | **43 / 43 PASSED (3.43s)** |

---

## 8. Git Status and Working Tree Audit

- **Uncommitted Modifications:**
  - `firmware/esp32s3_csi_collector/main/main.c`: Recovery source code (netif init, STA mode, error handling).
  - `firmware/esp32s3_csi_collector/platformio.ini`: `-DCONFIG_ESP_WIFI_CSI_ENABLED=1`.
- **Untracked Test & Report Files:**
  - `backend/tests/test_phase49.py`: Phase 49 verification suite.
  - `backend/tests/test_phase50.py`: Phase 50 deployment and smoke test suite.
  - `reports/phase49_csi_initialization_recovery.md`: Phase 49 diagnosis report.
  - `reports/phase50_recovery_firmware_deployment.md`: Current deployment report.
  - `scratch/run_csi_smoke_test.py`: Phase 50 smoke test harness.
  - `scratch/read_boot_log.py`: Boot log extraction utility.
- No unrelated files or protected model weights were touched.

---

## 9. Final Release Disposition

**`RECOVERY FIRMWARE VERIFIED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION`**

The Phase 48 CSI initialization abort and reboot loop have been definitively resolved. The physical ESP32-S3 board on `COM5` is now stably executing the verified recovery firmware, actively receiving physical CSI frames on Channel 7 from the Lab AP (`98:BA:5F:EF:28:26`), and parsing them with zero errors. All system invariants, protected checkpoints, and dataset manifests remain intact.
