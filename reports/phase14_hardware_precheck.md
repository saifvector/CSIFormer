# CSIFormer Phase 14 — Stage 0 Hardware Pre-Check & Verification Report

**Audit Timestamp:** 2026-10-18T05:28:00Z  
**Auditor:** Principal Wireless Sensing Research Scientist & Embedded Systems Auditor  
**Hardware Target:** Espressif ESP32-S3 Wi-Fi CSI Receiver Node  
**Host System:** Windows Laptop (x86_64, Windows 11)  

---

## 1. Executive Pre-Connection Checklist

| Item | Status | Verification Evidence / Technical Findings |
| :--- | :---: | :--- |
| **0.1 Physical Connection & Port** | **VERIFIED** | Detected `USB-Enhanced-SERIAL CH343 (COM5)` (`USB\VID_1A86&PID_55D3\5C93073863`). Status: `OK` (`CM_PROB_NONE`). Accessible and operational on Windows. |
| **0.1 USB Data Capability** | **VERIFIED** | Successfully transmitted ROM bootloader telemetry and active firmware application logs over serial at 115,200 baud. Cable is confirmed bi-directional data, not charge-only. |
| **0.2 ESP32-S3 Board Model** | **VERIFIED** | Captured hardware ROM bootloader: `ESP-ROM:esp32s3-20210327`, Chip Revision `v0.2`, eFuse Block `v1.4`, Dual-Core Xtensa LX7 @ 160 MHz (`cpu freq: 160000000 Hz`). |
| **0.2 Memory & Storage** | **VERIFIED** | Detected physical SPI Flash: `16,384 KB (16 MB)` DIO mode @ 80 MHz (binary image header configured for 2 MB). Internal SRAM available: `~334 KiB`. MAC: `d4:05:92:7b:2e:d0`. |
| **0.3 Current Firmware State** | **VERIFIED** | Board is running compiled ESP-IDF v5.5.5 firmware (`csi_receiver`, build Sep 9 2026 20:55:39). Actively triggers `wifi_csi_cb` with `LEN=128` (64 OFDM subcarrier IQ pairs). |
| **0.3 Firmware CSI Payload Format**| **BLOCKED** | Running firmware truncates serial telemetry to 5 subcarriers (`RSSI=-55 LEN=128 CSI:0,0,-17,-4,...`). Model expects full 56 subcarriers (HT20) with sequence numbers and timestamps. |
| **0.4 Wi-Fi Router Connection** | **VERIFIED** | Board is actively associated with `Tp link` (BSSID: `98:ba:5f:ef:28:26`), Channel 7 (2.4 GHz HT20/BW20), RSSI: `-55 dBm`, IP: `192.168.0.232`. |
| **0.4 Local Network Reachability**| **VERIFIED** | Laptop is connected to `Tp link_5G` (BSSID: `98:ba:5f:ef:28:28`, Gateway: `192.168.0.1`). ICMP ping from laptop to ESP32-S3 (`192.168.0.232`) verified with 8–11 ms round-trip time. |
| **0.4 Controlled Traffic Source** | **VERIFIED** | Active AP beaconing (`bi: 102400 us`) and local ICMP/UDP pinging provides sustained packet transmission rate across Channel 7. |

---

## 2. Detailed Hardware & Interface Telemetry

### 2.1 PnP USB Serial Interface
```
Class                       : Ports
FriendlyName                : USB-Enhanced-SERIAL CH343 (COM5)
InstanceId                  : USB\VID_1A86&PID_55D3\5C93073863
HardwareID                  : USB\VID_1A86&PID_55D3&REV_0445
Manufacturer                : wch.cn
Driver Service              : CH343SER_A64
Status                      : OK (Device working properly)
```

### 2.2 ESP32-S3 Hardware ROM & Bootloader Telemetry
Captured via non-destructive serial reset at 115,200 baud:
```
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)
SPIWP:0xee
mode:DIO, clock div:1
load:0x3fce2820,len:0x14f0
load:0x403c8700,len:0xd24
load:0x403cb700,len:0x2eec
entry 0x403c8924
I (24) boot: ESP-IDF v5.5.5 2nd stage bootloader
I (25) boot: compile time Sep  9 2026 20:56:00
I (25) boot: Multicore bootloader
I (25) boot: chip revision: v0.2
I (28) boot: efuse block revision: v1.4
I (31) boot.esp32s3: Boot SPI Speed : 80MHz
I (35) boot.esp32s3: SPI Mode       : DIO
I (39) boot.esp32s3: SPI Flash Size : 2MB
I (43) boot: Enabling RNG early entropy source...
I (254) cpu_start: Multicore app
I (262) cpu_start: GPIO 44 and 43 are used as console UART I/O pins
I (263) cpu_start: cpu freq: 160000000 Hz
I (269) app_init: Project name:     csi_receiver
I (273) app_init: App version:      v5.5.5
I (286) app_init: ESP-IDF:          v5.5.5
I (308) heap_init: Dynamic RAM available: ~334 KiB
W (335) spi_flash: Detected size(16384k) larger than binary header(2048k).
```

### 2.3 Wi-Fi Network & RF Environment
```
Wi-Fi State                 : Connected (STA Mode)
SSID                        : Tp link
BSSID                       : 98:ba:5f:ef:28:26
Radio Type                  : 802.11b/g/n (phy: bgn)
Channel                     : 7 (2.442 GHz, HT20 / 20 MHz bandwidth)
RSSI                        : -55 dBm to -60 dBm
Cipher                      : WPA2-PSK (CCMP)
IP Address                  : 192.168.0.232
Gateway                     : 192.168.0.1
Subnet Mask                 : 255.255.255.0
Beacon Interval             : 102,400 us (~9.76 Hz beacon baseline)
```

---

## 3. Discovered Firmware Limitations & Critical Blockers

1. **Subcarrier Truncation in Running Firmware:**
   The firmware currently flashed on the board logs:
   ```
   === CSI CALLBACK FIRED ===
   RSSI=-55 LEN=128 CSI:0,0,-17,-4,-17,-4,-14,-3,-9,-3,
   ```
   While the hardware radio extracts the complete `LEN=128` (64 subcarriers $\times$ 2 bytes for $I$ and $Q$), the `printf` loop only prints the first 5 subcarriers (10 values).
   The Phase 13 production model expects **56 subcarriers (HT20)** across 50 temporal frames (`[B, 50, 56]`).

2. **Repository Firmware Availability:**
   A full, complete C firmware implementation that outputs all 56 subcarriers with sequence numbers, MAC addresses, RSSI, and noise floor is already present in the repository at [`firmware/esp32s3_csi_collector/main/main.c`](file:///c:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c).

3. **Serial Library Prerequisite:**
   `pyserial` is required in the Python 3.11 environment to enable `RealCSICollector` and `ESP32HardwareManager` to stream serial packets asynchronously into the model pipeline.

---

## 4. Verification Conclusion & Safe Operational Pathway

- **Hardware Status:** The ESP32-S3 board is verified, powered, connected to the laptop on `COM5`, and actively capturing Wi-Fi packets from the local router.
- **Safety Directive:** In strict accordance with Phase 14 constraints, **no firmware flash or erase will be executed without user explanation and explicit approval.**
- **Immediate Next Action:** Execute Stage 1 (Complete Repository Audit) and generate [`reports/phase14_audit.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase14_audit.md).
