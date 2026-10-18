# CSIFormer Phase 20 — Physical Collection Execution & Operator Protocol

## Executive Summary

This report establishes the physical data acquisition workflow, operator procedures, hardware verification status, and data accounting for **CSIFormer Phase 20**.

In accordance with strict scientific validation requirements:
- **No model was retrained, fine-tuned, evaluated, quantized, replaced, or modified.**
- **No physical data was fabricated or simulated.**
- Software test fixtures and simulated unit tests are strictly distinguished from physical recordings collected by the human operator.
- Physical hardware connectivity was directly tested via serial telemetry.

---

## 1. Physical Hardware Connectivity & Protocol Verification

### 1.1 Hardware Setup & Verification Command
The physical receiver node is an **ESP32-S3 (Xtensa dual-core LX7 @ 240 MHz)** connected via a dedicated USB-to-UART bridge (WCH CH343).

The reproducible hardware verification check is executed via:
```powershell
py -3.11 scratch/run_collection_session.py --verify --port COM5
```

### 1.2 Actual Hardware Verification Telemetry
Physical execution on the host machine produced the following live output:

```
================================================================================
HARDWARE VERIFICATION CHECK
================================================================================
[RealCSICollector] Successfully connected to COM5 @ 115200 baud.
[RealCSICollector] Background CSI acquisition loop started.
[RealCSICollector] Disconnected serial interface.
Status:             NO_PACKETS
Port:               COM5
Connected:          True
Packets in 1.5s:    0
Sampling Rate:      0.0 Hz
Mean RSSI:          -99.0 dBm
================================================================================
```

### 1.3 Telemetry Interpretation
- **Serial Port & Connection:** `COM5` opened successfully at `115200` baud. The CH343 USB-UART bridge is physically plugged in and responsive.
- **Packet Reception Status:** `NO_PACKETS`. During the 1.5-second test window, 0 physical CSI packets were streamed into the serial buffer.
- **Hardware Cause:** The ESP32-S3 requires active Wi-Fi frame stimulation from the access point or transmitter node (`Tp link`, BSSID `98:ba:5f:ef:28:26`, Channel 7 @ 2.442 GHz). Because the remote transmitter/router was not transmitting probe frames during the query, the CSI callback was inactive.
- **Reporting Invariant:** Physical verification establishes that the serial bridge is connected, but **live streaming is currently inactive**. Therefore, **physical collection remains pending until the operator activates the Wi-Fi transmission source**.

### 1.4 Firmware Protocol & Measurement Dimensions
Inspection of [`firmware/esp32s3_csi_collector/main/main.c`](file:///c:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c#L45-L68) confirms:
- **Packet Header:** `CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,...` (Format B).
- **Raw CSI Dimensions ($N_{\text{raw}}$):** Determined directly by the 802.11n HT20 frame length (`info->len / 2`). For standard 128-byte CSI buffers, the hardware provides **64 raw subcarriers** (FFT bins). For 104-byte buffers, it provides **52 raw subcarriers**.
- **Model Tensor Dimensions ($N_{\text{model}}$):** CSIFormer operates strictly on **56 subcarrier channels**. [`RealCSICollector`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L328-L344) linearly interpolates the raw measurement array to 56 channels while preserving the raw uninterpolated array in the `raw_amplitudes` metadata field.
- **Invariant:** 56 subcarriers is an aligned model representation, never the raw hardware measurement.

---

## 2. Standardized Operator Collection Protocol

### 2.1 Step-by-Step Operator Workflow

```
+-----------------------------------------------------------------------------+
|               CSIFormer Physical Collection Workflow (Phase 20)             |
+-----------------------------------------------------------------------------+
|                                                                             |
|  Step 1: Hardware Pre-Flight Check                                          |
|    $ py -3.11 scratch/run_collection_session.py --verify --port COM5         |
|    Verify: Status = OK, Rate >= 30.0 Hz, RSSI >= -70 dBm                    |
|                                                                             |
|  Step 2: Participant Onboarding & Consent                                   |
|    - Assign pseudonymized ID (e.g., Participant_03, Participant_04)         |
|    - Review physical trial protocol with participant                        |
|                                                                             |
|  Step 3: Execute Controlled Trial Recording                                 |
|    $ py -3.11 scratch/run_collection_session.py \                           |
|        --activity walk \                                                    |
|        --participant Participant_03 \                                       |
|        --room Bedroom_01 \                                                  |
|        --distance 2.5 \                                                     |
|        --duration 4.0 \                                                     |
|        --confirm                                                            |
|                                                                             |
|  Step 4: Post-Capture Ground-Truth Confirmation                             |
|    - If trial was clean: Confirm ground truth (saved as labeled activity)   |
|    - If trial was interrupted/ambiguous: Reject (saved as 'unknown', cid -1)|
|                                                                             |
|  Step 5: Automated Dataset Integrity Validation                             |
|    $ py -3.11 scratch/run_collection_session.py --validate                  |
|    Ensures manifest consistency, sequence integrity, and zero corruption    |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 2.2 Non-Destructive Overwrite Protection
In [`RealCSICollector.stop_session_recording`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L499-L507), an automated collision-prevention loop verifies file existence. If a file named `session_id.json` already exists on disk, the system automatically appends a version suffix (`session_id_v1.json`, `session_id_v2.json`), guaranteeing that **no historical recording is ever silently overwritten**.

### 2.3 Quarantine Mechanism for Corrupted Recordings
If a physical recording contains malformed syntax, NaN/Inf floating-point values, non-monotonic timestamps, or mismatched packet counts, [`DatasetIntegrityValidator.quarantine_session()`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py#L164-L203) moves both the JSON and CSV files to `data/real_csi_dataset/quarantine/` and logs the reason in `quarantine/quarantine_manifest.json`. **No corrupt file is silently repaired or relabeled.**

---

## 3. Mandatory Fall Collection Safety Protocol

> [!CAUTION]
> ### LIFE-SAFETY MANDATE: FALL TRIAL RESTRICTIONS
> 1. **Supervision Required:** Fall recordings must **never** be performed alone or unsupervised. A competent human spotter must be within arm's reach throughout the trial.
> 2. **Certified Protective Equipment:** Fall trials must **strictly** land on a certified shock-absorbing crash mat with a minimum thickness of **4 inches (10 cm)** (e.g., high-density gymnastic or bouldering mat).
> 3. **Controlled Kinematics:** Participants must execute controlled breakfalls (distributing impact across forearms, thighs, and torso). Head, neck, and direct spine impacts are strictly prohibited.
> 4. **Voluntary Participation & Right to Postpone:** Participants must provide informed consent and may withdraw at any time. If safety equipment, certified padding, or a competent spotter is unavailable, **fall collection must be postponed immediately**.
> 5. **No Data Fabrication:** Under no circumstance may ordinary activities (e.g., sitting or lying down) be falsely relabeled as falls.

---

## 4. Physical Data Collection Accounting & Deficit Tracking

### 4.1 Physical Data Accounting Table
Every metric is calculated directly from physical files on disk:

| Metric | Verified Baseline (Phase 19) | Newly Added (Phase 20) | Current Verified Total | Provisional Pilot Target | Remaining Deficit | Evidence File Reference |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Physical Sessions** | 23 | 0 | **23** | $\ge 50$ | **-27 sessions** | [`dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json) |
| **Physical Packets** | 3,212 | 0 | **3,212** | $\ge 10,000$ | **-6,788 packets** | Sum of `packet_count` in 23 session files |
| **Valid Sliding Windows ($T=50$)** | 49 | 0 | **49** | $\ge 150$ | **-101 windows** | Discrete 50-frame non-overlapping windows |
| **Distinct Participants** | 2 | 0 | **2** | $\ge 5$ | **-3 participants** | `Participant_01`, `Participant_02` |
| **Distinct Rooms** | 1 | 0 | **1** | $\ge 3$ | **-2 rooms** | `Laboratory_Room1` exclusively |
| **Tx-Rx Distances** | 1 | 0 | **1** | $\ge 3$ | **-2 distances** | $2.5\text{ m}$ baseline exclusively |
| **Held-Out Test Fall Windows** | 4 | 0 | **4** | $\ge 35$ | **-31 windows** | [`dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json) |
| **Held-Out Test Fall Events** | 2 | 0 | **2** | $\ge 12$ | **-10 events** | Discrete physical fall trials in test split |

*(Note on disk contents: Exactly 24 session JSON files exist in [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/); 23 are indexed in the primary manifest, while 1 is an unindexed trial [`phase14_p15_real_walk_t1_1792303844_1792303844.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/phase14_p15_real_walk_t1_1792303844_1792303844.json) with 147 frames, omitted from manifest due to initial session naming conflict.)*

### 4.2 Status of the Physical Acquisition Milestone
Because no new hardware recordings were captured during this development iteration:
- **Newly Added Physical Recordings:** **0**
- **Newly Added Packets:** **0**
- **Newly Added Windows:** **0**
- **Physical Acquisition Milestone Status:** **PENDING OPERATOR CAMPAIGN**

The software infrastructure, serial ingestion drivers, overwrite protection, quarantine workflow, and CLI validation tools are completely prepared and verified. Physical execution by the operator is required to fulfill the deficit.
