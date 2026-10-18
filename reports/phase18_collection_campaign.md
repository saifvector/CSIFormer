# CSIFormer Phase 18 — Real-World CSI Collection Campaign & Quality Control Specification

## Executive Summary

Phase 18 establishes a fortified, scientifically auditable collection campaign protocol for physical Channel State Information (CSI) acquisition on the ESP32-S3 Wi-Fi sensing platform. In Phase 16 and Phase 17, audits revealed that historical evaluations suffered from participant identity leakage (only 2 participants in the dataset) and that legacy recordings (Phase 15) stored only interpolated 56-subcarrier arrays without preserving raw physical subcarriers.

This report establishes:
1. **Physical Measurement vs. Model Feature Clarification:** Explicit differentiation between raw physical subcarriers extracted from hardware registers and model-aligned interpolated arrays.
2. **Firmware & Parser Reality:** Examination of actual ESP-IDF firmware (`firmware/esp32s3_csi_collector/main/main.c`) output formats and subcarrier counts.
3. **Reproducible Operator Campaign Checklist:** Standardized, step-by-step procedure for physical data collection.
4. **Event-Level Traceability:** Unique `event_id` assignment ensuring windows from the same physical movement event never cross evaluation partitions.
5. **Rigorous Fall Safety Mandates:** Non-negotiable protective protocols requiring certified crash mats, competent spotters, participant consent, and immediate postponement rules.
6. **Physical Target Tracking:** Transparent accounting of actual dataset counts versus Phase 18 pilot targets.

---

## 1. Raw Physical Measurements vs. Model Features

A critical scientific finding from the Phase 17 and Phase 18 audits is the distinction between **raw physical measurements** and **interpolated model features**:

### 1.1 The Physical Signal Reality
In 802.11n Wi-Fi OFDM transmissions at 20 MHz bandwidth (HT20):
- The Fast Fourier Transform (FFT) consists of 64 subcarrier bins indexed $-32$ to $+31$.
- In standard HT-LTF / LLTF reception on the ESP32-S3, the radio baseband extracts complex IQ pairs $(I, Q)$ for each subcarrier bin.
- Depending on the firmware configuration (`rx_filter_len`, `channel_filter_en`, and packet modulation), the raw buffer length (`info->len`) typically contains 128 bytes ($64$ complex pairs) or 112 bytes ($56$ active pairs).
- **Rule:** The software must never label interpolated values as raw physical measurements, and must never claim a fixed 52 raw subcarriers unless the actual serial data format and packet parser verify that specific count.

### 1.2 The Model Alignment Layer
The CSIFormer production checkpoint (`models/csiformer_phase13_best.pth`) expects a fixed input tensor of shape:
$$\mathbf{X} \in \mathbb{R}^{B \times 50 \times 56}$$
Where 50 represents temporal frames (1.66 seconds at 30 Hz nominal / ~1.40 seconds at 35.6 Hz sustained), and 56 represents subcarrier channels.
- When raw packets arrive with $N_{\text{raw}}$ subcarriers (e.g., 64 or 52), `RealCSICollector._process_parsed_frame` applies 1D linear interpolation (`np.interp`) across subcarrier indices to map from $N_{\text{raw}}$ to exactly 56 channels.
- In Phase 18, both representations are strictly preserved:
  - `raw_amplitudes`: Unmodified list of floats of length $N_{\text{raw}}$ as parsed directly from the hardware packet.
  - `raw_phases`: Unmodified phase angles ($\text{atan2}(Q, I)$) of length $N_{\text{raw}}$.
  - `raw_num_subcarriers`: Explicit integer recording $N_{\text{raw}}$.
  - `amplitudes`: Aligned 56-channel array for model ingestion.
  - `subcarrier_alignment_method`: Recorded in metadata as `"linear_interpolation_to_56"`.

---

## 2. Firmware Telemetry & Serial Format Audit

Review of `firmware/esp32s3_csi_collector/main/main.c` confirms the hardware output structure:
```c
int num_subcarriers = info->len / 2; // Each subcarrier has I (int8) and Q (int8)
int8_t *csi_raw = (int8_t *)info->buf;

// Formats telemetry string: CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,...
```
The firmware emits two recognized telemetry formats:
1. **Format A (Raw IQ Stream):** `RSSI=-55 LEN=128 CSI:0,0,-17,-4,-14,-3,...` (raw byte stream from legacy builds).
2. **Format B (Structured CSV):** `CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,<amp_0:phase_0>,...`

The packet parser (`RealCSICollector.parse_raw_telemetry_line`) dynamically extracts `num_subcarriers` from `tokens[5]` in Format B or from `len(nums) // 2` in Format A. It never imposes an artificial 52-subcarrier assumption upon the hardware stream.

---

## 3. Operator Collection Campaign Checklist

To ensure full reproducibility across physical collection sessions, operators must follow this standardized checklist:

### Pre-Flight Verification
- [ ] Connect ESP32-S3 receiver via USB to the host computer (`COM5`).
- [ ] Verify active Wi-Fi router broadcasting on Channel 7 (2.442 GHz, SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`).
- [ ] Verify UDP stimulation link (`192.168.0.232:5555`).
- [ ] Run automated hardware check:
  ```powershell
  py -3.11 scratch/run_collection_session.py --verify --port COM5
  ```
  *Requirement:* Status `OK`, packet rate $\ge 30.0$ Hz, Mean RSSI $\ge -65$ dBm.

### Environmental & Geometric Setup
- [ ] Select and document room type (e.g. `Laboratory`, `Office_Room_B`, `Living_Room`).
- [ ] Position transmitter (Tx) and receiver (Rx) at designated height (1.0m above floor).
- [ ] Measure and record baseline distance:
  - Short distance: 1.5 m
  - Nominal distance: 2.5 m
  - Extended distance: 3.5 m / 4.5 m
- [ ] Record Tx position (`--tx-pos`) and Rx position (`--rx-pos`).
- [ ] Assign non-reversible pseudonymized participant ID (`Participant_03`, `Participant_04`, etc.).

### Trial Execution
- [ ] Execute trial recording with activity label, participant ID, duration, and event ID:
  ```powershell
  py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --room Laboratory --distance 2.5 --tx-pos "Origin_0_0" --rx-pos "Node_2.5_0" --confirm
  ```
- [ ] Post-trial ground-truth confirmation:
  - If trial proceeded without stumbles, hesitation, or external interruptions: confirm (`y`).
  - If trial was interrupted or participant hesitated: reject (`n`). Unconfirmed trials are saved with activity `"unknown"` (Class ID `-1`).

---

## 4. Strict Fall Safety Mandate

> [!CAUTION]
> **CRITICAL LIFE SAFETY DIRECTIVE FOR PHYSICAL FALL COLLECTION**
> 
> Collecting real fall data involves inherent physical risk to participants. The following safety measures are mandatory:
> 
> 1. **Certified Shock-Absorbing Mat:** All fall trials must be executed onto a certified gymnastics or martial arts crash mat of **at least 4 inches (10 cm) thickness**.
> 2. **Never Fall on Hard Floors:** Falling onto bare concrete, tile, linoleum, or hardwood floors is **strictly forbidden**.
> 3. **Trained Spotter Present:** A minimum of two people (the participant and a trained spotter) must be present. The spotter must be positioned adjacent to the mat to assist deceleration if needed.
> 4. **Controlled Breakfalls Only:** Participants must execute deliberate, low-impact breakfalls with head tucked and arms decelerating on the mat. High-impact uncontrolled falls, head impacts, or extended wrist impacts are prohibited.
> 5. **Participant Consent & Discretion:** Participants must be informed of the risks and must give uncoerced consent. Any participant may decline or halt fall trials at any point without explanation.
> 6. **Postponement Rule:** If certified crash mats, competent spotters, or willing participants are unavailable, fall collection **must be postponed**. The software must never pressure an operator to execute unsafe trials.

---

## 5. Physical Target Tracking: Actual vs. Pilot Goals

| Milestone Criterion | Phase 18 Pilot Target | Actual Audited Dataset | Target Attainment | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Physical Sessions** | $\ge 50$ sessions | **23 sessions** | $46.0\%$ | **Pending Physical Campaign** |
| **Physical Packets** | $\ge 10,000$ packets | **3,212 packets** | $32.1\%$ | **Pending Physical Campaign** |
| **Quality-Checked Windows** | $\ge 150$ windows | **49 windows** | $32.7\%$ | **Pending Physical Campaign** |
| **Distinct Participants** | $\ge 5$ participants | **2 participants** | $40.0\%$ | **Barrier ($N=2$)** |
| **Distinct Rooms** | $\ge 3$ rooms | **1 room** | $33.3\%$ | **Domain Gap** |
| **Tx-Rx Distance Variations** | $\ge 3$ distances | **1 distance (2.5m)** | $33.3\%$ | **Domain Gap** |
| **Held-Out Test Fall Windows** | $\ge 35$ windows | **4 windows** | **$11.4\%$** | **Critical Deficit (-31)** |
| **Distinct Fall Events (Held-Out)** | $\ge 12$ events | **2 events** | **$16.7\%$** | **Critical Deficit (-10)** |

### Conclusion on Physical Data:
While the acquisition software, active UDP stimulation, serial driver, and metadata tracking are fully implemented and verified, **the physical data collection targets have not yet been met**. In accordance with Phase 18 guidelines, targets are not marked achieved until real physical files are captured and audited.
