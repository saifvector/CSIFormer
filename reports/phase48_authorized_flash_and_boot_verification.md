# CSIFormer Phase 48 — Authorized Firmware Flash, Boot Verification, and Hardware Smoke Test Report

**Status:** **`FLASH SUCCEEDED — BOOT OR CSI SMOKE TEST FAILED`**  
**Physical Hardware Target:** ESP32-S3 (QFN56 revision v0.2), 16 MB Flash, 8 MB Embedded PSRAM on `COM5`  
**Lab Access Point:** TP-Link Archer C6 (`Tp link`, BSSID: `98:ba:5f:ef:28:26`, Channel 7 HT20 @ 2.442 GHz)  
**Date:** October 19, 2026  
**Safety Protocol:** Explicit user flash authorization confirmed; zero full-chip erase; protected model checkpoints and dataset manifest preserved bit-for-bit; zero new dataset sessions admitted.

---

## 1. Executive Summary

Phase 48 executed the physical firmware deployment of the Phase 47 release build to the physical ESP32-S3 development board on `COM5`. Prior to any write operation, explicit authorization was solicited and confirmed by the user under Gate A. Gate B preflight hardware inspection verified that the target board is an authentic ESP32-S3 with 16 MB flash capacity and that the 6 release artifacts match the Phase 47 validated cryptographic hashes bit-for-bit.

Under Gate C, the Phase 47 validated build was successfully uploaded to `COM5` via PlatformIO (`esptool v5.4.0`) at 921,600 baud without full-chip erasure. The bootloader (21,120 bytes @ `0x0`), partition table (3,072 bytes @ `0x8000`), and application binary (654,848 bytes @ `0x10000`) were written and verified with cryptographic hash checks (`Hash of data verified`, exit code 0).

Under Gate D, serial boot monitoring at 115,200 baud captured the fresh hardware reset. The ESP-IDF 6.1.0 secondary bootloader successfully verified the 16 MB flash geometry (`DIO`, `80MHz`), parsed the partition table, and mapped the application into CPU address space. However, during execution of `app_main()`, a fatal panic occurred at `main.c:100` within `init_csi()`:
```text
ESP_ERROR_CHECK failed: esp_err_t 0xffffffff (ESP_FAIL) at 0x42001715
file: "C:/Users/saifu/Desktop/4-1 project/firmware/esp32s3_csi_collector/main/main.c" line 100
func: init_csi
expression: esp_wifi_set_csi_config(&csi_config)
abort() was called at PC 0x4037d063 on core 0
```
This error caused the microcontroller to enter an unhandled reboot loop. Root cause analysis reveals that under ESP-IDF 6.1.0, calling `esp_wifi_set_csi_config(&csi_config)` while the Wi-Fi mode is set to `WIFI_MODE_NULL` causes the internal driver to return `ESP_FAIL` (`-1`).

In strict compliance with Phase 48 safety rules, no unauthorized code modifications, ad-hoc rebuilds, or dataset admissions were attempted. Protected checkpoints and the dataset manifest remain completely unaltered.

---

## 2. Gate A — Explicit User Flash Authorization

Pursuant to the mandatory prerequisite, physical flash authorization was verified interactively prior to executing any write command:

- **Interactive Authorization Prompt:**
  `"Do you explicitly authorize flashing the Phase 47 validated firmware artifacts to the physical ESP32-S3 development board on COM5 and executing the boot verification and hardware smoke test?"`
- **Confirmed Response:**
  `A1: (Recommended) Yes, I explicitly authorize flashing the Phase 47 validated firmware to the ESP32-S3 on COM5 and executing the boot verification and hardware smoke test.`
- **Authorization Basis:** Unambiguous positive selection recorded in trajectory at step index 9540.
- **Gate A Status:** **PASSED — EXPLICIT AUTHORIZATION CONFIRMED**

---

## 3. Gate B — Pre-Flash Hardware and Artifact Verification

### 3.1 Serial Port and Board Identification
- **Target Serial Port:** `COM5` (verified as Espressif USB-JTAG/Serial debug bridge, VID/PID `303A:1001`)
- **Chip Architecture:** ESP32-S3 (QFN56) (revision v0.2)
- **Features:** Wi-Fi, BLE 5, Dual Core + LP Core, 240 MHz, Embedded PSRAM 8 MB (`AP_3v3`)
- **MAC Address:** `d4:05:92:7b:2e:d0`
- **Crystal Frequency:** 40 MHz
- **Flash Hardware Parameters (via `esptool flash_id`):**
  - Manufacturer ID: `0x1c` (ESMT / EON)
  - Device ID: `0x7118`
  - Flash Capacity: 16 MB (`16,777,216` bytes)

### 3.2 Laboratory RF Environment and Channel Grounding
- **Access Point SSID:** `Tp link` (TP-Link Archer C6)
- **BSSID:** `98:ba:5f:ef:28:26`
- **Current Operating Channel:** Channel 7 HT20 (Center frequency: 2.442 GHz, 20 MHz channel width)
- **Signal RSSI:** -52 dBm
- **Firmware Agreement:**
  - `firmware/esp32s3_csi_collector/main/main.c`: `#define WIFI_CHANNEL 7`
  - `firmware/esp32s3_csi_collector/platformio.ini`: `build_flags = -DCONFIG_CSI_CHANNEL=7 ...`
  - Channel agreement: **MUTUALLY ALIGNED (Channel 7)**

### 3.3 Artifact Cryptographic Hash Verification
All generated release artifacts on disk were compared against the Phase 47 release gate report:

| Artifact | Size | Expected Phase 47 MD5 | Measured Phase 48 MD5 | Verification |
| :--- | :--- | :--- | :--- | :--- |
| `bootloader.bin` | 21,120 bytes | `4a458917c604096b5a37ac1124addeef` | `4a458917c604096b5a37ac1124addeef` | **EXACT MATCH** |
| `partitions.bin` | 3,072 bytes | `b87dcdfd58f072a1e7b50b94abe79496` | `b87dcdfd58f072a1e7b50b94abe79496` | **EXACT MATCH** |
| `firmware.bin` | 654,848 bytes | `bb9aa1da83649f397a75be89f488d990` | `bb9aa1da83649f397a75be89f488d990` | **EXACT MATCH** |
| `firmware.elf` | 7,701,264 bytes | `2f3a2501e5598d0553a253285509ff6e` | `2f3a2501e5598d0553a253285509ff6e` | **EXACT MATCH** |
| `flasher_args.json`| 959 bytes | `48027a4ad660f30cc1b4714c0218b8ac` | `48027a4ad660f30cc1b4714c0218b8ac` | **EXACT MATCH** |
| `flash_args` | 163 bytes | `2458eee62cf04463972a1f9c280e3857` | `2458eee62cf04463972a1f9c280e3857` | **EXACT MATCH** |

- **Gate B Status:** **PASSED — ALL PREFLIGHT CRITERIA MET**

---

## 4. Gate C — Controlled Firmware Flash Execution

### 4.1 Invocation and Flash Plan
- **Flash Method:** Supported PlatformIO / ESP-IDF upload target using validated build plan.
- **Top-Level Command:**
  ```powershell
  pio run -d Z:\firmware\esp32s3_csi_collector -t upload --upload-port COM5 -v
  ```
- **Underlying esptool Command Executed:**
  ```text
  "C:\Users\saifu\.platformio\packages\tool-esptool\esptool" \
    --chip esp32s3 --port "COM5" --baud 921600 \
    --before default-reset --after hard-reset \
    write-flash -z --flash-mode dio --flash-freq 80m --flash-size 16MB \
    0 Z:\firmware\esp32s3_csi_collector\.pio\build\esp32-s3-devkitc-1\bootloader.bin \
    0x8000 Z:\firmware\esp32s3_csi_collector\.pio\build\esp32-s3-devkitc-1\partitions.bin \
    0x10000 .pio\build\esp32-s3-devkitc-1\firmware.bin
  ```

### 4.2 Flash Execution Metrics
- **Tool Version:** `esptool v5.4.0`
- **Target Serial Port:** `COM5`
- **UART Flashing Baud Rate:** `921,600` baud
- **Flash Geometry Settings:** `--flash-mode dio --flash-freq 80m --flash-size 16MB`
- **Erase Mode:** Segment-targeted erase only (`write-flash -z`); **zero full-chip erase performed**.
- **Wrote to Flash:**
  - `0x00000000` (Bootloader): 21,120 bytes (13,767 compressed) in 0.3s (587.7 kbit/s)
  - `0x00008000` (Partition Table): 3,072 bytes (142 compressed) in 0.1s (389.2 kbit/s)
  - `0x00010000` (Factory App): 654,848 bytes (429,981 compressed) in 6.5s (800.0 kbit/s)
- **Verification Result:** `Hash of data verified.`
- **Hardware Reset:** `Hard resetting via RTS pin...`
- **Command Duration:** 53.20 seconds
- **Exit Code:** `0` (`[SUCCESS] Took 53.20 seconds`)
- **Gate C Status:** **PASSED — FIRMWARE FLASH SUCCESSFUL**

---

## 5. Gate D — Boot Verification, Root Cause Analysis, and Smoke Test

### 5.1 Serial Boot Capture
A serial monitor session connected to `COM5` at 115,200 baud captured the boot output immediately following the RTS reset:

```text
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0xc (RTC_SW_CPU_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)
Saved PC:0x4037d225
SPIWP:0xee
mode:DIO, clock div:1
load:0x3fce2820,len:0x14f0
load:0x403c8700,len:0xde4
load:0x403cb700,len:0x2f58
entry 0x403c88fc
I (29) boot: ESP-IDF 6.1.0 2nd stage bootloader
I (29) boot: compile time Oct 19 2026 21:26:59
I (29) boot: Multicore bootloader
I (29) boot: chip revision: v0.2
I (32) boot: efuse block revision: v1.4
I (36) boot.esp32s3: Boot SPI Speed : 80MHz
I (39) boot.esp32s3: SPI Mode       : DIO
I (43) boot.esp32s3: SPI Flash Size : 16MB
I (47) boot: Enabling RNG early entropy source...
I (52) boot: Partition Table:
I (54) boot: ## Label            Usage          Type ST Offset   Length
I (60) boot:  0 nvs              WiFi data        01 02 00009000 00006000
I (67) boot:  1 phy_init         RF data          01 01 0000f000 00001000
I (73) boot:  2 factory          factory app      00 00 00010000 001f0000
I (80) boot: End of partition table
I (83) esp_image: segment 0: paddr=00010020 vaddr=3c080020 size=16170h ( 90480) map
I (107) esp_image: segment 1: paddr=00026198 vaddr=3fc97b00 size=0517ch ( 20860) load
I (112) esp_image: segment 2: paddr=0002b31c vaddr=40374000 size=04cfch ( 19708) load
I (117) esp_image: segment 3: paddr=00030020 vaddr=42000020 size=70fb4h (462772) map
I (203) esp_image: segment 4: paddr=000a0fdc vaddr=40378cfc size=0edd4h ( 60884) load
I (217) esp_image: segment 5: paddr=000afdb8 vaddr=50000000 size=00024h (    36) load
I (226) boot: Loaded app from partition at offset 0x10000
I (226) boot: Disabling RNG early entropy source...
I (236) cpu_start: Multicore app
I (245) cpu_start: GPIO 44 and 43 are used as console UART I/O pins
I (245) cpu_start: Pro cpu start user code
I (246) cpu_start: cpu freq: 160000000 Hz
I (247) app_init: Application information:
I (251) app_init: Project name:     esp32s3_csi_collector
I (256) app_init: App version:      16cb232-dirty
I (260) app_init: Compile time:     Oct 19 2026 21:23:34
I (265) app_init: ELF file SHA256:  e5ace20cc...
I (270) app_init: ESP-IDF:          6.1.0
I (274) efuse_init: Min chip rev:     v0.0
I (277) efuse_init: Max chip rev:     v0.99
I (281) efuse_init: Chip rev:         v0.2
I (285) heap_init: Initializing. RAM available for dynamic allocation:
I (292) heap_init: At 3FCA03C0 len 00049350 (292 KiB): RAM
I (297) heap_init: At 3FCE9710 len 00005724 (21 KiB): RAM
I (302) heap_init: At 3FCF0000 len 00008000 (32 KiB): DRAM
I (307) heap_init: At 600FE000 len 00001FE8 (7 KiB): RTCRAM
I (313) spi_flash: detected chip: generic
I (316) spi_flash: flash io: dio
I (320) sleep_gpio: Configure to isolate all GPIO pins in sleep state
I (325) sleep_gpio: Enable automatic switching of GPIO sleep configuration
I (332) main_task: Started on CPU0
I (362) main_task: Calling app_main()
I (382) ESP32S3_CSI_COLLECTOR: Initializing ESP32-S3 Wi-Fi CSI Sensing Node...
I (382) pp: pp rom version: e7ae62f
I (382) net80211: net80211 rom version: e7ae62f
I (392) wifi:wifi driver task: 3fcec970, prio:23, stack:6656, core=0
I (402) wifi:wifi firmware version: e12a754
I (402) wifi:wifi certification version: v7.0
I (402) wifi:config NVS flash: enabled
I (402) wifi:config nano formatting: disabled
I (402) wifi:Init data frame dynamic rx buffer num: 32
I (412) wifi:Init static rx mgmt buffer num: 5
I (412) wifi:Init management short buffer num: 32
I (422) wifi:Init dynamic tx buffer num: 32
I (422) wifi:Init static tx FG buffer num: 2
I (422) wifi:Init static rx buffer size: 1600
I (432) wifi:Init static rx buffer num: 10
I (432) wifi:Init dynamic rx buffer num: 32
I (442) wifi_init: rx ba win: 6
I (442) wifi_init: accept mbox: 6
I (442) wifi_init: tcpip mbox: 32
I (452) wifi_init: udp mbox: 6
I (452) wifi_init: tcp mbox: 6
I (452) wifi_init: tcp tx win: 5760
I (452) wifi_init: tcp rx win: 5760
I (462) wifi_init: tcp mss: 1440
I (462) wifi_init: WiFi IRAM OP enabled
I (462) wifi_init: WiFi RX IRAM OP enabled
I (472) phy_init: phy_version 712,87e8c20e,Apr 13 2026,18:51:10
E (522) wifi:failed to post WiFi event=43 ret=259
I (522) wifi:mode : null
E (522) wifi:failed to post WiFi event=43 ret=259
I (522) wifi:ic_enable_sniffer
ESP_ERROR_CHECK failed: esp_err_t 0xffffffff (ESP_FAIL) at 0x42001715
file: "C:/Users/saifu/Desktop/4-1 project/firmware/esp32s3_csi_collector/main/main.c" line 100
func: init_csi
expression: esp_wifi_set_csi_config(&csi_config)
abort() was called at PC 0x4037d063 on core 0
Backtrace: 0x4037d0a5:0x3fca3db0 0x4037d06d:0x3fca3dd0 0x4037cb4d:0x3fca3df0 0x4037d063:0x3fca3e60 0x42001715:0x3fca3e90 0x420018d1:0x3fca3ec0 0x4200718b:0x3fca3f80 0x4206e842:0x3fca3fb0
ELF file SHA256: e5ace20cc...
Rebooting...
```

### 5.2 Bootloader & Partition Validation Analysis
- **ROM & 2nd Stage Bootloader:** Executed perfectly without memory corruption or timing errors.
- **Hardware Profile Confirmation:** Flash SPI speed was recognized as `80MHz`, SPI Mode as `DIO`, and SPI Flash Size as `16MB`.
- **Partition Table:** Decoded from offset `0x8000` with 0 errors. App loaded cleanly from `0x10000`.

### 5.3 Diagnostic Root Cause Analysis of Abort at `main.c:100`
1. **Source Code Sequence in `firmware/esp32s3_csi_collector/main/main.c`:**
   In `app_main()`:
   ```c
   // Line 121:
   ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_NULL));
   ESP_ERROR_CHECK(esp_wifi_start());
   ESP_ERROR_CHECK(esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE));
   ESP_ERROR_CHECK(esp_wifi_set_promiscuous(true));

   // Line 127:
   init_csi();
   ```
   In `init_csi()`:
   ```c
   // Line 89-100:
   wifi_csi_config_t csi_config = {
       .lltf_en = true,
       .htltf_en = true,
       .stbc_htltf2_en = true,
       .ltf_merge_en = true,
       .channel_filter_en = true,
       .manu_scale = false,
       .shift = 0,
       .dump_ack_en = false
   };
   ESP_ERROR_CHECK(esp_wifi_set_csi_config(&csi_config)); // Line 100
   ```
2. **Failure Mechanism in ESP-IDF 6.1.0 Wi-Fi Stack:**
   - In ESP-IDF 6.1.0, the Wi-Fi subsystem requires an operational station interface mode (`WIFI_MODE_STA`) before hardware CSI filter registers can be programmed via `esp_wifi_set_csi_config()`.
   - `esp_wifi_set_mode(WIFI_MODE_NULL)` unconfigures the station and AP MAC state machines, leaving the internal PHY CSI filter handler in an uninitialized state.
   - When `esp_wifi_set_csi_config(&csi_config)` is invoked under `WIFI_MODE_NULL`, the driver returns `ESP_FAIL` (`0xffffffff`), causing the `ESP_ERROR_CHECK` macro to invoke `abort()`.
   - The chip consequently reboots continuously, preventing Wi-Fi association and subsequent CSI telemetry streaming.

### 5.4 Wi-Fi Association and CSI Smoke Test Summary
- **Wi-Fi Association:** **FAILED / NOT REACHED** (blocked by panic in `init_csi()`).
- **Telemetry Protocol Streaming:** **0 frames transmitted** due to recurring reboot cycle.
- **Hardware Smoke Test:** **FAILED AT RUNTIME EXECUTION GATE**.
- **Physical vs Derived Subcarriers:** As no packets were transmitted, 0 physical subcarriers were observed from the live node during this boot session.
- **Gate D Status:** **FAILED — RUNTIME ABORT AT `main.c:100`**

---

## 6. Gate E — Protected Asset Invariance and Regression Verification

### 6.1 Protected Asset Cryptographic Invariance
All three protected model checkpoints and dataset metadata files were re-hashed with MD5 and compared against their invariant reference hashes:

| Protected File Path | Expected MD5 Reference Hash | Measured MD5 Hash | Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |

Zero model checkpoints were overwritten, modified, or trained. Zero dataset manifest records were altered.

### 6.2 Host Regression Test Results
1. **Firmware Configuration and Geometry Regression Suite (Phases 44, 45, 46):**
   - **Command:** `py -3.11 -m pytest backend/tests/test_phase44.py backend/tests/test_phase45.py backend/tests/test_phase46.py -v`
   - **Exit Code:** `0`
   - **Results:** 22 passed / 22 total (100% pass) in 3.44s.
2. **Format B Transport and Telemetry Parser Regression Suite (Phase 42):**
   - **Command:** `py -3.11 -m pytest backend/tests/test_phase42.py -v`
   - **Exit Code:** `0`
   - **Results:** 7 passed / 7 total (100% pass) in 2.59s.
   - Verified: `test_phase42_format_b_parser_with_known_values`, `test_phase42_format_a_parser_with_signed_iq`, and parser error handling.

- **Gate E Status:** **PASSED — ALL PROTECTED ASSETS PRISTINE, RELEVANT HOST SUITES 100% PASS**

---

## 7. Git Working Tree State and Zero Dataset Admission Confirmation

### 7.1 Working Tree Integrity
- Unrelated working tree changes from prior phases remain preserved without commits, pushes, or resets.
- Zero Git branch changes or destructive operations were performed.

### 7.2 Zero Dataset Admission Confirmation
- **Dataset Manifest:** `data/real_csi_dataset/dataset_manifest.json` remains identical to `a58e1280fb2c0a6649335a9a381d00c6`.
- **Dataset Collection Sessions:** **ZERO** new sessions collected, recorded, admitted, or staged.
- **Model Training / Held-Out Evaluation:** **ZERO** model training, adaptation, fine-tuning, or held-out test inference executed.

---

## 8. Summary of Technical Limitations and Unresolved Risks

1. **Firmware Initialization Flaw in `main.c`:**
   The firmware configuration is geometrically and syntactically valid (16 MB flash, Channel 7, valid image headers), but exhibits a logical runtime initialization flaw under ESP-IDF 6.1.0: `esp_wifi_set_mode(WIFI_MODE_NULL)` prevents `esp_wifi_set_csi_config(&csi_config)` from succeeding.
2. **Required Remediation for Subsequent Phase:**
   In a subsequent authorized firmware patch phase, `app_main()` should initialize Wi-Fi in Station mode (`WIFI_MODE_STA`) before invoking `esp_wifi_set_csi_config()`, or associate with the laboratory AP (`Tp link`) to enable physical frame reception.
3. **Hardware Health:**
   The physical ESP32-S3 module on `COM5` is in good working order. Its flash controller, SPI flash chip (16 MB ESMT), internal voltage regulators, and bootloader ROM responded reliably across multiple serial connections at both 921,600 and 115,200 baud.

---

## 9. Final Decision and Formal Status

Pursuant to Section 8 of the Phase 48 specification, the formal status is:

### **`FLASH SUCCEEDED — BOOT OR CSI SMOKE TEST FAILED`**

- **Flashing Status:** Flashing succeeded completely (exit code 0, 654,848 bytes written and hash-verified).
- **Boot Status:** ROM and secondary bootloader loaded cleanly; application entered `app_main()`.
- **Smoke Test Status:** CSI initialization aborted at `main.c:100` (`esp_wifi_set_csi_config` returned `ESP_FAIL` under `WIFI_MODE_NULL`), causing an unhandled core reboot loop.
- **Data Collection Status:** Strictly zero dataset sessions admitted. Awaiting separate authorization and firmware logic patch.
