# Phase 58 Stage 1: Passive Baseline Capture Report

**Execution Timestamp:** 2026-10-21T07:36:12Z to 2026-10-21T07:36:42Z (UTC)  
**Host Environment:** Windows (Antigravity IDE / Python 3.11.9)  
**Hardware Node:** ESP32-S3 on `COM5` (CH343 USB-to-UART bridge)  
**Target BSSID:** `98:BA:5F:EF:28:26` (TP-Link Archer C6, 2.4 GHz, Channel 7)  
**Operational Scope:** 30.0-second passive, read-only serial capture; zero network traffic, zero firmware flashing, zero model execution.  
**Final Status:** **COMPLETED**

---

## 1. Executive Summary

Phase 58 Stage 1 has been executed on the physical ESP32-S3 hardware without rebooting, resetting, re-flashing, or transmitting active network traffic. Exactly one 30-second passive capture was completed on `COM5` at 115200 baud with read-only controls (`dtr=False, rts=False`).

The physical stream confirms:
1. **Telemetry Protocol:** Emits standard Format B v1 `CSI_DATA` frames (`CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,<amp:phase>...`). Extended `CSI_DATA_V2` fields, hardware microsecond timestamps (`hw_timestamp_us`), and 802.11 MAC sequence numbers (`rx_seq`) are **absent** from the deployed firmware.
2. **Empirical Acquisition Rate:** The target router BSSID (`98:BA:5F:EF:28:26`) generated **107 valid records** over 30.0044 seconds, yielding an empirical target acquisition rate of **3.566 Hz** (mean inter-arrival: 277.63 ms, median: 149.90 ms). This closely matches the passive baseline observed in Phase 54 (~3.8 Hz) and Phase 56 audits (~1.66–3.8 Hz).
3. **Aggregate Over-the-Air Traffic:** The receiver captured **316 valid frames** across all transmitters (10.532 Hz aggregate rate), with ambient nodes (predominantly `00:2D:F4:5B:4B:7D` at 64.9%) interleaving with target router traffic (33.9%).
4. **UART Transport Integrity:** Across 318 expected callback records, only **2 sequence gaps** were detected (`firmware_sequence_gaps: 2`), proving a **99.37% UART transport delivery rate** with zero out-of-order packets and zero counter resets.
5. **Port Release:** `COM5` was closed and released cleanly at the end of the 30.0044-second capture window.

---

## 2. Preflight Hardware & Serial Configuration

| Parameter | Observed Value | Verification Method |
|---|---|---|
| **Port Present** | `COM5` | `serial.tools.list_ports.comports()` |
| **Device Description** | `USB-Enhanced-SERIAL CH343 (COM5)` | Windows USB Driver Telemetry |
| **Hardware ID (HWID)** | `USB VID:PID=1A86:55D3 SER=5C93073863 LOCATION=1-2` | Physical Device Descriptor |
| **Manufacturer** | `wch.cn` | Driver Identity |
| **Configured Baud Rate** | `115200` baud | `serial.Serial` Configuration |
| **Flow Control Lines** | `dtr=False`, `rts=False` configured prior to `open()` | PySerial Win32 DCB setup |
| **Reset Prevention** | Zero RTS pulses, zero DTR drops | Hardware Protection Verified |
| **Bus State Modification** | Zero bytes transmitted (`write()` never called) | Pure Passive Listening |

---

## 3. Physical Capture Timing & Execution

| Metric | Target Specification | Actual Measured Value |
|---|---|---|
| **Target Duration** | 30.000 s | 30.000 s |
| **Actual Measured Duration** | 30.000 s | **30.0044 s** |
| **Start Time (Wall Clock UTC)** | — | 2026-10-21T07:36:12Z (`1792568172.263`) |
| **Stop Time (Wall Clock UTC)** | — | 2026-10-21T07:36:42Z (`1792568202.268`) |
| **Serial Handle State Post-Capture** | Closed | `ser.is_open == False` |
| **Port Released** | Confirmed | **True** |

---

## 4. Observed Telemetry Format & Physical Structure

### 4.1 Telemetry Header & Format Classification
- **Detected Protocol:** `structured_csi_data` (Format B v1)
- **Extended Protocol (`CSI_DATA_V2`):** **False** (absent)
- **Hardware Timestamps (`hw_timestamp_us`):** **False** (absent)
- **802.11 MAC Sequence (`rx_seq`):** **False** (absent)

### 4.2 Raw Telemetry Line Samples (Observed from COM5)
```text
CSI_DATA,00:2D:F4:5B:4B:7D,-61,-93,6128,64,0.00:0.000,7.28:2.863,6.08:-2.976,5.00:3.142,4.47:2.678,3.16:2.820,2.24:2.678...
CSI_DATA,98:BA:5F:EF:28:26,-55,-93,6129,128,0.00:0.000,17.49:0.540,14.87:0.738,14.87:0.738,14.21:0.686,14.21:0.686,14.21...
CSI_DATA,98:BA:5F:EF:28:26,-52,-93,6130,64,0.00:0.000,23.77:-2.886,23.77:-2.886,23.35:-2.969,20.22:-2.993,17.12:-3.024...
CSI_DATA,00:2D:F4:5B:4B:7D,-65,-93,6131,64,0.00:0.000,6.40:2.246,6.40:2.246,5.00:2.214,4.47:2.034,4.12:1.816,4.00:1.571...
```

---

## 5. Quantitative Metric Counts & Rates

### 5.1 Telemetry Counts

| Metric Counter | Count | Description / Notes |
|---|---|---|
| `total_raw_lines` | **333** | Total newline-delimited lines received from UART buffer |
| `candidate_records` | **318** | Lines matching `CSI_DATA` prefix |
| `valid_records_parsed` | **316** | Fully validated subcarrier frames |
| `parse_errors` | **2** | Buffer boundary split artifacts during initial read sync |
| `target_records` (`98:BA:5F:EF:28:26`) | **107** | Target router frames matching configured BSSID |
| `filtered_non_target_records` | **209** | Valid ambient Wi-Fi frames from unassociated sources |

### 5.2 Source MAC Distribution (Over-the-Air Spectrum)

| Source MAC Address | Packet Count | Proportion | Identity / Classification |
|---|---|---|---|
| `00:2D:F4:5B:4B:7D` | 205 | 64.9% | Ambient node / neighbouring AP or client |
| `98:BA:5F:EF:28:26` | 107 | 33.9% | **Target Router (TP-Link Archer C6, Ch 7)** |
| `18:CC:88:7E:74:71` | 3 | 0.9% | Ambient node |
| `80:5E:4F:21:03:FA` | 1 | 0.3% | Ambient node |
| **Total Valid Records** | **316** | **100.0%** | Full receiver capture |

---

## 6. Sequence Integrity & Transport Health

| Sequence Metric | Value | Technical Interpretation |
|---|---|---|
| `firmware_sequence_gaps` | **2** | Observed callback sequence discontinuities across all physical arrivals |
| Total Expected Callback Frames | 318 | 316 parsed + 2 sequence gaps |
| **UART Delivery Success Rate** | **99.37%** | 316 / 318 frames successfully delivered across serial interface |
| **Observed Transport Loss Rate** | **0.63%** | 2 / 318 lost in serial buffer or FIFO |
| `duplicate_packets` | **0** | No repeated sequence numbers received |
| `out_of_order_packets` | **0** | Monotonic sequence delivery confirmed |
| `counter_resets` | **0** | No device reboots or counter wrap events occurred |
| `target_sequence_gaps` | **206** | Sequence gaps in target-only stream caused by interleaving non-target traffic |

---

## 7. Arrival Timing & Acquisition Rates

All interval statistics are calculated using high-resolution host monotonic clocks (`time.perf_counter()`).

| Timing Parameter | Target Traffic (`98:BA:5F:EF:28:26`) | Aggregate Traffic (All Sources) |
|---|---|---|
| **Sample Count** | 107 frames | 316 frames |
| **Empirical Sampling Rate** | **3.566 Hz** | **10.532 Hz** |
| **Mean Inter-Arrival Time** | 277.63 ms | 94.76 ms |
| **Standard Deviation** | 242.18 ms | 38.10 ms |
| **Minimum Inter-Arrival Time** | 72.19 ms | 63.38 ms |
| **Median (P50) Inter-Arrival** | 149.90 ms | 72.22 ms |
| **95th Percentile (P95)** | 806.84 ms | 144.58 ms |
| **Maximum Inter-Arrival Time** | 1607.07 ms | 354.17 ms |

### Key Arrival Dynamics Observation:
- When only passive beacon/management frames are emitted by the target router without active traffic, the router transmits at a baseline beacon rate with occasional bursts (min interval 72.19 ms, median 149.90 ms), yielding an effective rate of **~3.57 Hz**.
- This proves that the ~3.8 Hz rate observed in Phase 54 and Phase 56 audits was not a collector bug, but represents the physical passive packet arrival rate of the TP-Link Archer C6 on Channel 7 when no network stimulation is present.
- The historical dataset rate of **~35–39 Hz** cannot be achieved through passive listening alone without active network stimulation or high-rate traffic flow.

---

## 8. Safety & Integrity Audit

- **Network Stimulation:** Zero packets transmitted (no UDP ping, no ICMP echo, no router traffic generated).
- **Firmware Integrity:** No code compiled, built, or flashed. The existing deployed firmware was preserved untouched.
- **Model Integrity:** Zero training epochs, zero fine-tuning runs, zero forward inference passes.
- **Dataset Manifest:** `data/real_csi_dataset/dataset_manifest.json` was not modified.

### Cryptographic Hash Verification:

| Asset | Expected MD5 | Post-Capture MD5 | Status |
|---|---|---|---|
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH** |

---

## 9. Conclusion and Next Steps

1. **Status:** Phase 58 Stage 1 is **COMPLETED**.
2. **Summary of Findings:**
   - The ESP32-S3 node on `COM5` is alive, running the Format B v1 `CSI_DATA` recovery firmware from Phase 50, and cleanly acquiring physical over-the-air CSI.
   - The passive target arrival rate is empirically measured at **3.566 Hz** (107 packets in 30.0044 s).
   - The UART transport layer is highly stable, exhibiting **99.37% frame delivery** with only 2 callback sequence gaps across 30 seconds.
   - Hardware timestamps (`hw_timestamp_us`) and extended headers (`CSI_DATA_V2`) do not exist on the current firmware.
3. **Stage 2 Status:** Stage 2 (and all subsequent calibration or active stimulation steps) remains **STRICTLY ON HOLD** pending explicit user review and authorization.
