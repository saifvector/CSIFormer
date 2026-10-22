# CSIFormer Phase 51 — CSI Stream Integrity, Physical Subcarrier Verification, and Pilot Readiness Audit Report

**Status:** **`STREAM VALIDATED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION`**  
**Target Hardware:** ESP32-S3 (QFN56 revision v0.2, 16 MB Flash, 8 MB PSRAM) on `COM5`  
**Lab Access Point:** TP-Link Archer C6 (`Tp link`, BSSID: `98:ba:5f:ef:28:26`, Channel 7 HT20 @ 2.442 GHz)  
**Date:** October 20, 2026  
**Safety Protocol:** Zero physical flash operations; zero dataset admissions; zero model retraining; protected model checkpoints and dataset manifest preserved bit-for-bit.

---

## 1. Executive Summary

Phase 51 performed an independent, non-destructive validation of the Phase 50 hardware deployment, established the true physical CSI payload structure from the ESP32-S3 MAC layer, quantified serial transport stream reliability using real-time sequence tracking, audited host parser and adapter behaviors, and evaluated operational readiness for a separately authorized pilot collection campaign.

Over a bounded 15.04-second diagnostic read on `COM5`, 48,776 bytes and 57 complete Format B (`CSI_DATA`) frames were ingested with **zero malformed records and zero parse errors** (100% parser validity). Because the firmware increments an internal sequence counter on each hardware callback (`packet_sequence++`), packet continuity was rigorously quantified: sequence IDs 1752 through 1808 were captured sequentially with **zero dropped frames (0.00% serial transport loss)** at an average throughput rate of 3.79 Hz and an average SNR of 31.7 dB.

A deep physical payload audit established that the ESP32-S3 firmware outputs raw 64-bin (for HT20) and 128-bin (for HT40) FFT spectrum vectors directly from hardware register memory without hardware filtering. In HT20 mode, the 64-bin payload contains 52 active physical OFDM data subcarriers with genuine multipath amplitudes (mean amplitude 13.84, min 5.45, max 24.43) and continuous phase gradients, alongside 1 DC null carrier (index 0) and 11 guard/null carriers (indices 27–37). Crucially, the audit revealed that ambient co-channel transmissions (such as `18:CC:88:7E:74:71`) are currently captured by promiscuous mode alongside the target AP (`98:BA:5F:EF:28:26`), and that host `RealCSICollector` resamples non-56-subcarrier inputs down to 56 subcarriers via `np.interp`. Consequently, strict BSSID filtering and guard-subcarrier stripping must be enforced prior to any research pilot.

All 48 regression tests across Phases 42–51 passed. All protected model weights and the dataset manifest remain byte-for-byte pristine. No data was admitted to the repository dataset.

---

## 2. Evidence Reviewed

The audit cross-referenced claims from Phase 50 against raw serial captures, source code, and firmware binary disassembly:

| Artifact / Evidence Source | Claim Audited | Verification Status | Audit Finding |
| :--- | :--- | :--- | :--- |
| `reports/phase50_recovery_firmware_deployment.md` | Flashing succeeded without full erase | **VERIFIED** | ESP-IDF upload logs confirm targeted sector erase (`write-flash -z`); bootloader, partition table, and app verified via MD5/SHA256. |
| `reports/phase50_recovery_firmware_deployment.md` | CSI initialization succeeded without panic | **VERIFIED** | Live serial boot log confirmed `esp_wifi_set_csi_config()` returned `ESP_OK` (0x0). Zero panics or reboot loops observed. |
| `scratch/run_csi_smoke_test.py` | 27 packets parsed in 8.25s @ 3.27 Hz | **VERIFIED (Reproduced)** | Phase 51 diagnostic read captured 57 frames in 15.04s @ 3.79 Hz with 0 parse errors. |
| `firmware/esp32s3_csi_collector/main/main.c` | Subcarrier count is physical 64 | **QUALIFIED / REFINED** | Firmware outputs all 64 FFT bins from `info->buf`. 52 bins contain physical multipath measurements; 12 bins are DC/guard nulls (0.0). |
| `backend/app/services/real_csi_collector.py` | Subcarrier alignment to 56 | **ARCHITECTURAL RISK** | Collector applies `np.interp` to resample 64/128 bins to 56 subcarriers for model inference. Must be guarded for raw research pilots. |
| `backend/app/services/esp32_csi_adapter.py` | Cross-hardware subcarrier mapping | **VERIFIED** | Unit tests confirm cubic interpolation for Intel 5300 (30 -> 56) and decimation for Atheros (114 -> 56). |

---

## 3. Physical Payload and Subcarrier Findings

### 3.1 End-to-End Data Path Traced
```
ESP32-S3 Baseband RF Receiver (Channel 7 @ 2.442 GHz)
   │
   ▼
Hardware CSI Extraction Buffer (info->buf, len = 128 bytes for HT20, 256 bytes for HT40)
   │
   ▼
Firmware Callback wifi_csi_cb() (main.c:40-85)
   ├─ Computes Amp = sqrt(I^2 + Q^2) and Phase = atan2(Q, I)
   └─ Serializes Format B ASCII: "CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp:phase,..."
   │
   ▼
Console UART Transmission (115,200 baud stdout)
   │
   ▼
Host Serial Framing & Ingest (RealCSICollector.parse_raw_telemetry_line)
   ├─ Splits CSV tokens; extracts MAC, RSSI, Noise, Seq, Num_Subcarriers
   └─ Parses raw_amplitudes (list of floats) and raw_phases (list of floats)
   │
   ▼
Host Post-Processing (_process_parsed_frame)
   ├─ raw_amplitudes (preserved as 64 or 128 elements in recording frame)
   └─ aligned_amp (resampled via np.interp to TARGET_SUBCARRIERS = 56 for inference window)
```

### 3.2 Physical vs Derived Subcarrier Structure
Inspection of 57 consecutive frames over the diagnostic read revealed two distinct hardware callback payload types:
1. **HT20 64-Bin Spectrum (54 / 57 frames, 94.7%):**
   - Total bins: `64` (`info->len = 128` bytes, 64 signed 8-bit I/Q pairs).
   - **Active Data Subcarriers:** Exactly **52 bins** (`indices 1–26 and 38–63`).
     - Mean amplitude across active bins: `13.84` (min `5.45`, max `24.43`).
     - Phase values: Continuous gradients from `-3.098` to `+3.142` rad.
   - **DC Center Carrier (Index 0):** Exactly `0.00:0.000` (zeroed out by 802.11 baseband filter).
   - **Guard & Null Subcarriers (Indices 27–37):** Exactly `11 bins` zeroed out (`0.00:0.000`).
2. **HT40 128-Bin Spectrum (3 / 57 frames, 5.3%):**
   - Total bins: `128` (`info->len = 256` bytes, 128 signed 8-bit I/Q pairs).
   - Active subcarriers: `108 bins`.
   - Null / Guard subcarriers: `20 bins` (indices 0, 27–37, 64, 93–99).
   - Triggered when an ambient 40 MHz channel packet is received on Channel 7.

### 3.3 Available Telemetry Metadata Fields
- **Source MAC / BSSID:** Directly extracted from 802.11 MAC frame header (`info->mac`).
- **RSSI:** Measured by receiver AGC register (`info->rx_ctrl.rssi`).
- **Noise Floor:** Measured by hardware register (`info->rx_ctrl.noise_floor`).
- **Sequence Identifier:** Incrementing packet sequence generated in firmware (`packet_sequence++`).
- **Subcarrier Count:** Derived directly from hardware buffer size (`info->len / 2`).
- **Timestamp:** High-resolution host reception timestamp (`time.time()`).
- **MIMO Streams:** Not available on ESP32-S3 single-stream 1x1 SISO hardware.

---

## 4. Serial Stream Integrity Assessment

A 15.04-second diagnostic read was conducted via `scratch/audit_phase51_stream_integrity.py` on `COM5`:

### 4.1 Transport Reliability Metrics
- **Measurement Duration:** `15.04 s`
- **Total Ingested Data:** `48,776 bytes`
- **Total Lines Processed:** `57 lines`
- **Valid Format B Records:** `57` (100.0%)
- **Malformed Lines:** `0` (0.00%)
- **Sequence Span:** First sequence `1752`, Last sequence `1808` (total span = 57 frames).
- **Sequence Gaps / Dropped Records:** `0` instances (0 dropped frames).
- **Packet Loss Rate over UART:** **`0.00%`** (Denominator: 57 sequentially incremented frames).
- **Serial Port Release:** Verified closed and released (`ser.is_open == False`).

### 4.2 Temporal Dynamics and Ingest Rate
- **Mean Ingest Rate:** `3.79 Hz` (reflecting beacon and broadcast traffic rate on Channel 7).
- **Mean Inter-Arrival Time:** `249.74 ms`.
- **Interval Standard Deviation (Jitter):** `420.65 ms`.
- **Min / Max Interval:** `0.00 ms` (burst frames) / `1749.52 ms` (beacon intervals).

### 4.3 Co-Channel Transmitter Distribution
Promiscuous mode captured traffic from two transmitters on Channel 7:
1. **Lab Target AP (`98:BA:5F:EF:28:26`):** `38 frames (66.7%)`, RSSI `-61 dBm`, HT20 (64 bins).
2. **Ambient Station / Router (`18:CC:88:7E:74:71`):** `19 frames (33.3%)`, RSSI `-64 dBm`, mixed HT20/HT40.

---

## 5. Parser and Adapter Behavior

### 5.1 Host Parser Validation
`RealCSICollector.parse_raw_telemetry_line()` was subjected to synthetic edge case fixtures:
- Truncated headers (< 6 tokens): **Strictly rejected (`None`)**.
- Corrupted non-numeric RSSI / Noise / Sequence: **Strictly rejected (`None`)**.
- Non-CSI lines (bootloader logs, system banners): **Ignored safely without exceptions (`None`)**.
- Physical vs Derived: `raw_amplitudes` stores the exact un-interpolated hardware subcarrier readings; `aligned_amp` holds the resampled 56-subcarrier representation.

### 5.2 Architectural Observation on Subcarrier Resampling
In `real_csi_collector.py:453-457`, when `len(raw_amps) != 56`, the collector resamples the array using linear interpolation (`np.interp`). For 64-bin HT20 inputs, this interpolates across the 12 zeroed DC and guard bins. For a rigorous research pilot, a dedicated extraction filter should select the 52 active data carriers and 4 pilot carriers rather than interpolating across guard nulls.

---

## 6. Targeted Regression Test Results

All relevant tests across Phases 42–51 were executed via pytest:

```powershell
py -3.11 -m pytest backend/tests/test_phase42.py backend/tests/test_phase43.py backend/tests/test_phase44.py backend/tests/test_phase45.py backend/tests/test_phase46.py backend/tests/test_phase49.py backend/tests/test_phase50.py backend/tests/test_phase51.py -v
```

### Execution Summary

| Test File | Description | Assertions | Result |
| :--- | :--- | :--- | :--- |
| `test_phase42.py` | Transport budget, parser, pilot isolation | 7 | **7 PASSED** |
| `test_phase43.py` | Port discovery, provenance contract, subcarriers | 5 | **5 PASSED** |
| `test_phase44.py` | Toolchain, build artifacts, flash offsets | 8 | **8 PASSED** |
| `test_phase45.py` | Pre-flash configuration audit | 7 | **7 PASSED** |
| `test_phase46.py` | Flash geometry, channel realignment | 7 | **7 PASSED** |
| `test_phase49.py` | CSI enablement, source safeguards | 5 | **5 PASSED** |
| `test_phase50.py` | Deployment verification, Format B telemetry | 4 | **4 PASSED** |
| `test_phase51.py` | Physical subcarrier structure, parser resilience, embargo | 5 | **5 PASSED** |
| **Combined Suite** | **Phases 42 through 51** | **48** | **48 / 48 PASSED (4.20s)** |

---

## 7. Protected Checksum Audit

| Resource | Expected Cryptographic MD5 | Measured Cryptographic MD5 | Verification |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **PRISTINE** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **PRISTINE** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **PRISTINE** |

- **Dataset Admissions:** 0 records admitted to production manifest.
- **Model Retraining:** 0 training steps executed.
- **Inference Runs:** 0 held-out test evaluations.

---

## 8. Unresolved Risks and Pilot Blockers

1. **Ambient Transmitter Interception:** In promiscuous mode on Channel 7, 33.3% of captured packets originated from a non-target transmitter (`18:CC:88:7E:74:71`). A pilot collector must implement strict BSSID filtering on `98:BA:5F:EF:28:26` to reject ambient multipath interference.
2. **Variable Subcarrier Ingestion (64 vs 128):** Occasional HT40 packets trigger 128-subcarrier callbacks. The ingestion pipeline must enforce strict HT20 filtering so that only 64-bin packets from the target AP are processed.
3. **Guard-Band Interpolation vs Active Subcarrier Masking:** Currently, `RealCSICollector` resamples all 64 bins (including the zeroed DC and guard carriers) down to 56 subcarriers via `np.interp`. While mathematically smooth, masking or stripping the 12 null bins directly preserves physical subcarrier alignment with the 56 HT20 active tones.
4. **Passive Capture Rate (3.8 Hz):** Passive beacon snooping yields ~3.8 Hz. A dedicated traffic generator (e.g., ping or UDP broadcast at 30–50 Hz) from a connected client to the AP is recommended to achieve the 30 Hz target rate for high-velocity activity recognition.

---

## 9. Pilot-Readiness Checklist

The following checklist must be satisfied before any research pilot session:

- [x] **Firmware Operational:** Recovery firmware booted, stable, zero panics or reboot loops.
- [x] **CSI Extraction Active:** Hardware CSI driver extracts valid complex I/Q frames from Channel 7.
- [x] **Serial Transport Reliable:** 0.00% packet loss over serial stream, 100% Format B parser success.
- [x] **Protected Assets Intact:** Checkpoints and dataset manifest verified pristine.
- [ ] **BSSID Filter Configured:** Filtering restricted exclusively to Lab AP `98:BA:5F:EF:28:26`.
- [ ] **Subcarrier Masking Standardized:** Direct indexing of the 52/56 active tones without interpolating over guard nulls.
- [ ] **Traffic Injection Active:** Dedicated ping/UDP generator ensuring continuous >= 30 Hz sampling rate.
- [ ] **Isolated Pilot Output Directory:** Staging recordings in `data/pilot_recordings/` with strict manifest separation.
- [ ] **Human Activity Protocol & Consent:** Pre-defined motion protocol (sitting, standing, walking, falling) with participant consent.
- [ ] **Separate Pilot Authorization:** Explicit user authorization granted before executing the first recording session.

---

## 10. Final Disposition and Exact Next Action

**Final Status:** **`STREAM VALIDATED — AWAITING SEPARATE DATA-COLLECTION AUTHORIZATION`**

### Recommended Next Action
Do not collect research data automatically. In the subsequent phase, with explicit user authorization:
1. Implement the BSSID filter (`98:BA:5F:EF:28:26`) and active subcarrier mask in a dedicated pilot ingestion service.
2. Verify >= 30 Hz packet rate using active traffic generation on the Archer C6 network.
3. Solicit explicit user authorization for Phase 52 hardware pilot data collection.
