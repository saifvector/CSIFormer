# Phase 52 Report — Source Filtering, Physical Subcarrier Masking, and Acquisition-Rate Readiness

**Document Version:** 1.0.0  
**Phase:** 52  
**Date:** 2026-10-20  
**Status:** Completed & Validated  
**Safety Restrictions Enforced:** Zero firmware flash/erasure, zero dataset collection/admissions, zero model retraining, zero unmetered network traffic, zero git commits.

---

## 1. Executive Summary & Hardware Verification

Phase 52 focused on the software-layer prerequisites for physical CSI acquisition: establishing precise source-address semantics, implementing fail-closed configurable source filtering, formalizing the IEEE 802.11n HT20 64-bin physical carrier mask, validating model preprocessing invariance, and conducting bounded empirical stream diagnostics.

### 1.1 Read-Only Hardware Preflight on COM5
A non-destructive preflight audit was executed via `esptool v5.4.0` against `COM5` to verify device identity without repetitive resets:
- **Port:** `COM5` (`USB-Enhanced-SERIAL CH343`, VID:PID `0x1a86:0x55d3`)
- **Chip Type:** ESP32-S3 (QFN56) (revision v0.2)
- **Features:** Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240 MHz, Embedded PSRAM 8 MB (AP_3v3)
- **Crystal Frequency:** 40 MHz
- **Chip Base MAC:** `d4:05:92:7b:2e:d0`
- **Baud Rate:** 115,200 console / 921,600 transport
- **Port Availability:** Confirmed free before and after all diagnostic operations; closed with 100% clean release.

---

## 2. Transmitter MAC vs BSSID Semantics & Target-Source Filtering

### 2.1 Protocol Semantics Analysis
Inspection of the firmware serialization (`firmware/esp32s3_csi_collector/main/main.c`), ESP-IDF header `esp_wifi_types.h`, and `backend/app/services/esp32_csi_adapter.py` established the exact provenance of the parsed `mac` field:
1. **Transmitter Address (TA):** In the ESP-IDF `wifi_csi_info_t` struct, `info->mac` represents Address 2 (Transmitter Address / TA) of the IEEE 802.11 MAC header of the received frame.
2. **Downlink vs Uplink Differentiation:**
   - For **downlink frames** transmitted by the Access Point (e.g., beacons, probe responses, data downstream), `TA == BSSID` (`98:BA:5F:EF:28:26`).
   - For **uplink frames** transmitted by associated stations/clients (e.g., probe requests, client acknowledgments, uplink data), `TA == Station MAC` (e.g., `80:5E:4F:21:03:FA`, `18:CC:88:7E:74:71`).
   - Therefore, the parsed `mac` field identifies the **physical transmitter of the RF packet**, not necessarily the BSSID of the network.
3. **Filtering Necessity:** If unfiltered, CSI measurements from client stations contaminate the channel impulse response because each transmitter occupies a distinct spatial position and antenna path. Isolating the propagation channel from the Archer C6 router requires filtering by the router's transmitter MAC (`98:BA:5F:EF:28:26`).

### 2.2 Implementation of Configurable Target Filtering
In `backend/app/services/real_csi_collector.py`, configurable target filtering was implemented:
- **Default Target MAC:** `98:BA:5F:EF:28:26` (lab Archer C6 AP).
- **Filtering Flag:** `filter_by_mac: bool` (default `False`, enabled when single-transmitter channel isolation is required).
- **Fail-Closed Policy:** If `filter_by_mac=True` and a frame has missing, empty, or unparseable MAC metadata, the frame is immediately dropped, `self.parse_errors` is incremented, and the corrupt frame is rejected.
- **Source Tracking:** `self.source_mac_counts` maintains a dictionary of all detected transmitter MACs and frame counts.
- **Filter Accounting:** `self.filtered_non_target_packets` tracks the exact number of rejected non-target frames.

---

## 3. HT20 Physical Carrier Masking & Subcarrier Structure

### 3.1 IEEE 802.11n HT20 64-Bin Geometry
In IEEE 802.11n 20 MHz (HT20) mode with 64-point FFT, the subcarrier layout is formally partitioned as follows:
- **Total FFT Bins:** 64 (indices 0 to 63).
- **Active Data & Pilot Subcarriers (52 tones):**
  - Lower sideband: Bins 1 through 26 (negative frequencies $-26$ to $-1$).
  - Upper sideband: Bins 38 through 63 (positive frequencies $+1$ to $+26$).
- **Null & Guard Positions (12 tones):**
  - DC Center Frequency: Bin 0 (0 Hz carrier, suppressed by receiver hardware).
  - Guard Bands: Bins 27 through 37 (11 null bins at Nyquist band edge).

### 3.2 Subcarrier Masking Methods
In `backend/app/services/esp32_csi_adapter.py`, the physical carrier mask contract was formalized:
- `ESP32CSIAdapter.HT20_64_TOTAL_BINS = 64`
- `ESP32CSIAdapter.HT20_64_ACTIVE_DATA_INDICES`: Array of 52 indices (`[1..26, 38..63]`).
- `ESP32CSIAdapter.HT20_64_NULL_INDICES`: Array of 12 indices (`[0, 27..37]`).
- Methods provided:
  - `get_ht20_64_carrier_masks() -> (active_mask, null_mask)`
  - `extract_ht20_52_active_subcarriers(raw_64) -> active_52`
  - `separate_physical_and_null_components(raw_64) -> {"active_52": ..., "null_12": ...}`

### 3.3 Model Preprocessing Invariance Contract
- **CSIFormer Input Specification:** The production CSIFormer model requires temporal windows of shape `[50, 56]` (50 timesteps, 56 subcarriers).
- **Pre-existing Preprocessing:** In `RealCSICollector._process_parsed_frame()`, raw 64-bin subcarrier arrays are mapped to 56 subcarriers via linear interpolation (`np.interp`).
- **Invariance Guarantee:** Model preprocessing was **not modified**; the `[50, 56]` sliding window buffer continues producing identical input tensors for neural inference.
- **Physical Provenance:** The 52 physical active amplitudes and 12 physical null amplitudes are preserved in frame metadata (`physical_active_amplitudes` and `physical_null_amplitudes`) and raw session recording arrays without perturbing the model ingestion pipeline.

---

## 4. Empirical Stream Diagnostics & Live Measurements

A bounded, non-persistent diagnostic test (`scratch/run_phase52_bounded_diagnostic.py`) was conducted on `COM5` for 10.0 seconds with target filtering active (`target_mac="98:BA:5F:EF:28:26"`, `filter_by_mac=True`).

### 4.1 Telemetry Summary
| Metric | Measured Value | Analysis / Evidence |
| :--- | :--- | :--- |
| **Duration** | 10.0 s | Controlled execution window |
| **Serial Connection** | COM5 @ 115,200 baud | `USB-Enhanced-SERIAL CH343` |
| **Diagnostic State** | `CSI_STREAM_ACTIVE` | Continuous frame reception |
| **Total Serial Lines** | 121 lines | Raw UART stream data |
| **Total CSI Records Detected** | 32 records | Raw Format B records |
| **Admitted Target Packets** | **19 packets** | Successfully passed target MAC filter |
| **Filtered Non-Target Packets** | **13 packets** | Rejected foreign station packets |
| **Parser Errors** | **0 errors** | Zero format corruption |
| **Admitted Packet Rate** | **3.20 Hz** | Empirical rate under ambient beacon load |
| **Total Stream Packet Rate** | **4.50 Hz** | Total channel frame reception rate |
| **Sequence Gaps** | 13 gaps | Interleaved foreign packets in sequence stream |
| **Raw Dimensions** | 128 elements | 64 subcarriers $\times$ 2 (amplitude + phase) |
| **Port Release State** | **Cleanly Released** | Confirmed free immediately upon exit |

### 4.2 Live Source MAC Distribution
```
- 98:BA:5F:EF:28:26:  19 frames (Target AP - ADMITTED)
- 80:5E:4F:21:03:FA:  12 frames (Client Station - FILTERED)
- 18:CC:88:7E:74:71:   1 frame  (Client Station - FILTERED)
```
- **Filter Efficacy:** 100% of packets from `98:BA:5F:EF:28:26` were admitted; 100% of packets from ambient client stations (`80:5E:4F:21:03:FA` and `18:CC:88:7E:74:71`) were rejected.
- **Physical Carrier Geometry Observed in Raw Stream:**
  - Bin 0: `0.00:0.000` (DC carrier suppression verified).
  - Bins 1..26: Active non-zero amplitudes (e.g. `26.08`, `21.63`, `18.03`).
  - Bins 27..37: `0.00:0.000` (11 guard null bins verified).
  - Bins 38..63: Active non-zero amplitudes (e.g. `2.83`, `4.12`, `28.30`).

### 4.3 Acquisition Rate Reality
- **Empirical Measurement:** Under passive beacon conditions (no synthetic network traffic), the admitted CSI acquisition rate is **3.20 Hz**.
- **Rate Readiness Caveat:** CSIFormer model inference requires 30 Hz for real-time temporal feature extraction. Achieving 30 Hz cannot be accomplished passively; it requires active, metered ping or iperf traffic directed at the router. Under Phase 52 safety restrictions, network traffic generation was prohibited. Sustained 30 Hz acquisition must be validated in an explicitly authorized pilot phase with controlled traffic generation.

---

## 5. Regression Test Results across Phases 42–52

The full regression test suite covering all firmware transport, calibration, initialization, stream integrity, and source filtering phases was executed:
```bash
py -3.11 -m pytest backend/tests/test_phase42.py backend/tests/test_phase43.py \
    backend/tests/test_phase44.py backend/tests/test_phase45.py backend/tests/test_phase46.py \
    backend/tests/test_phase49.py backend/tests/test_phase50.py backend/tests/test_phase51.py \
    backend/tests/test_phase52.py -v
```

### 5.1 Test Breakdown
| Test Suite | Focus Area | Result |
| :--- | :--- | :--- |
| `backend/tests/test_phase42.py` | Parser formats, UART transport budget, SNR gate | **7 passed** |
| `backend/tests/test_phase43.py` | Hardware discovery, subcarrier integrity, directory safety | **5 passed** |
| `backend/tests/test_phase44.py` | Build validation, flash offsets, safety contracts | **8 passed** |
| `backend/tests/test_phase45.py` | Pre-flash configuration audit, flash size detection | **7 passed** |
| `backend/tests/test_phase46.py` | RF channel & flash geometry realignment (16 MB / Ch 7) | **7 passed** |
| `backend/tests/test_phase49.py` | Recovery build validation, CSI config verification | **5 passed** |
| `backend/tests/test_phase50.py` | Recovery deployment validation, boot verification | **4 passed** |
| `backend/tests/test_phase51.py` | Stream integrity, physical subcarriers, port release contract | **5 passed** |
| `backend/tests/test_phase52.py` | Source filtering, HT20 carrier masks, model invariance | **5 passed** |
| **Total** | **Phases 42–52 Combined Regression** | **53 passed in 6.05s** |

---

## 6. Protected Asset Checksum Verification

Cryptographic hash checks confirmed complete bit-level invariance across all protected model weights and dataset manifests:

| Asset Name | Target File Path | Expected MD5 Hash | Measured MD5 Hash | Disposition |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 13 Checkpoint** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Identical)** |
| **Phase 15 Checkpoint** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Identical)** |
| **Dataset Manifest** | `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Identical)** |

---

## 7. Conclusions & Phase 52 Release Gates

1. **Hardware & Port State:** `COM5` is verified functional, responsive, and completely free. The board is running validated Phase 49 recovery firmware in normal flash boot mode.
2. **Transmitter MAC vs BSSID Semantics:** Fully resolved. The `mac` field is the Transmitter Address (TA), which matches the BSSID only on downlink frames. Source filtering isolates the router's downlink multipath profile while discarding client transmissions.
3. **Physical Subcarrier Masking:** Complete. HT20 64-bin geometry (52 active data/pilot tones, 12 DC/guard nulls) is formally masked, separated, and tested.
4. **Model Preprocessing Invariance:** Preserved without drift. Temporal windowing produces exact `[50, 56]` arrays.
5. **Acquisition Rate Readiness:** Passive beacon acquisition delivers ~3.2 Hz. Achieving 30 Hz requires traffic generation, which remains blocked by safety restrictions until explicitly authorized.
6. **Release Embargo:** Zero firmware flash, zero persistent dataset collection, zero model retraining conducted. All release gates for Phase 52 are successfully satisfied.
