# CSIFormer Phase 19 — Real-World Dataset Quality & Telemetry Audit

## Executive Summary

This report establishes the audited data quality, RF signal fidelity, dimensional integrity, and environmental representation of the physical ESP32-S3 Channel State Information (CSI) dataset in Phase 19. All metrics and statistical distributions reported here are calculated directly from physical files in `data/real_csi_dataset/` verified by the [`DatasetIntegrityValidator`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py).

No synthetic data has been relabeled as physical recordings, and no physical sessions have been fabricated.

---

## 1. Physical Dataset Inventory & Class Distribution

The dataset comprises **24 physical session JSON files** on disk:
- **Indexed Sessions:** 23 sessions registered in [`dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json).
- **Unindexed Trials:** 1 aborted trial (`phase14_p15_real_walk_t1_1792303844_1792303844.json`, 147 frames), recorded 23 seconds before its valid replacement and correctly excluded from manifest tracking.
- **Total Physical Packets:** 3,212 packets.
- **Total Capture Duration:** 89.0 seconds ($3.87\text{ s}$ average duration per session).
- **Extracted Non-Overlapping Windows (Size 50, Stride 50):** 49 sliding windows ($2.13$ windows per session).

### Activity Representation Table
| Activity Label | Model Class ID | Physical Sessions | Total Packets | Extracted Windows | Window Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `walk` | 11 | 4 | 590 | 9 | 18.37% |
| `fall` | 9 | 4 | 561 | 8 | 16.33% |
| `sit` | 8 | 4 | 595 | 10 | 20.41% |
| `clap` | 2 | 4 | 579 | 8 | 16.33% |
| `push_pull` | 0 | 4 | 578 | 9 | 18.37% |
| `static` | 6 | 3 | 309 | 5 | 10.20% |
| **Total** | — | **23** | **3,212** | **49** | **100.0%** |

---

## 2. Participant Coverage Breakdown

The 23 sessions are distributed between two individuals:

| Participant ID | Total Sessions | Total Packets | Total Windows | `walk` | `fall` | `sit` | `clap` | `push_pull` | `static` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Participant_01` | 12 | 1,655 | 25 | 4 | 4 | 4 | 4 | 5 | 4 |
| `Participant_02` | 11 | 1,557 | 24 | 5 | 4 | 6 | 4 | 4 | 1 |
| **Total** | **23** | **3,212** | **49** | **9** | **8** | **10** | **8** | **9** | **5** |

### Event & Fall Window Accounting
- **Total Physical Fall Sessions:** 4 sessions (2 for `Participant_01`, 2 for `Participant_02`).
- **Total Discrete Fall Events:** 4 physical events.
- **Total Extracted Fall Windows:** 8 windows (4 per participant).
- **Held-Out Test Fall Windows (`Participant_02`):** **4 windows** (derived from 2 physical fall events).

---

## 3. Subcarrier Representation & Dimensional Analysis

### 3.1 Historical Legacy Sessions (Phase 15 Captures)
- **Raw Subcarrier Preservation:** 0 / 23 sessions preserved raw physical measurements.
- **Stored Representation:** 56-subcarrier interpolated arrays (`amp_0` to `amp_55`).
- **Audit Assessment:** Historical files only saved the interpolated model feature layer. The physical raw subcarrier register values were discarded during collection.

### 3.2 Upgraded Collection Architecture (Phase 17–19)
- **Raw Physical Arrays:** `raw_amplitudes` and `raw_phases` retain the exact subcarrier count parsed from hardware serial lines ($N_{\text{raw}}$).
- **Model Feature Arrays:** `amplitudes` and `phases` retain the standardized 56-channel input representation required by CSIFormer.
- **Traceability Field:** `subcarrier_alignment_method: "linear_interpolation_to_56"`.

---

## 4. Environmental & Geometric Bias Audit

All 23 existing recordings share an identical physical environment:
- **Room Location:** `Laboratory_Room1` (100%, 23/23 sessions).
- **Baseline Tx-Rx Distance:** 2.5 meters (100%, 23/23 sessions).
- **Antenna Heights:** ~1.0 meter above floor level.
- **Obstruction State:** 100% Line-of-Sight (LOS).
- **Aspect Angle / Orientation:** Recorded as `Unknown` in legacy metadata.

### Scientific Assessment:
The current dataset has zero cross-room diversity and zero distance variation. A model evaluated on this dataset cannot provide meaningful claims regarding generalizability across different room shapes, wall construction materials, furniture multipath, through-wall sensing (NLOS), or varying baseline path loss.

---

## 5. RF Signal Telemetry & Packet Loss Quality

- **Carrier Frequency:** 2.442 GHz (Channel 7, 802.11n HT20 mode).
- **Access Point:** SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`.
- **Mean Streaming Rate:** $35.6 \pm 1.8$ Hz (sustained via active UDP stimulation at 35.0 Hz).
- **Mean RSSI:** $-58.2 \pm 2.1$ dBm ($> 20$ dB signal-to-noise margin above sensitivity threshold).
- **Mean Packet Loss Rate:** $1.20\%$ dropped packet rate, detected via hardware sequence gaps ($\Delta \text{seq} > 1$). No burst drops exceeding 3 consecutive frames were found.
- **Timestamp Quality:** Hardware microsecond counter (`timestamp_us`) is strictly non-decreasing across all valid trials.
- **Numerical Integrity:** Zero NaN, Inf, or null values detected across all 3,212 frames.

---

## 6. Quarantine Audit & Unconfirmed Trial Handling

1. **Quarantine Inspection:**
   All 23 indexed session files passed automated validation via `DatasetIntegrityValidator`. No files required quarantine in the active dataset.
2. **Quarantine Workflow Readiness:**
   The quarantine system (`data/real_csi_dataset/quarantine/`) is active and verified by unit tests to isolate corrupted or unconfirmed files rather than silently repairing them.
3. **Unknown Label Preservation:**
   Any unconfirmed, interrupted, or ambiguous trial is strictly mapped to activity `"unknown"` with Class ID `-1`.

---

## 7. Pilot Target Attainment Summary

| Pilot Metric | Phase 19 Target | Verified Baseline | Verified Total | Deficit |
| :--- | :---: | :---: | :---: | :---: |
| **Physical Sessions** | $\ge 50$ | 23 | **23** | **-27** |
| **Physical Packets** | $\ge 10,000$ | 3,212 | **3,212** | **-6,788** |
| **Valid Sliding Windows** | $\ge 150$ | 49 | **49** | **-101** |
| **Distinct Participants** | $\ge 5$ | 2 | **2** | **-3** |
| **Distinct Rooms** | $\ge 3$ | 1 | **1** | **-2** |
| **Held-Out Test Fall Windows** | $\ge 35$ | 4 | **4** | **-31** |
| **Held-Out Test Fall Events** | $\ge 12$ | 2 | **2** | **-10** |

```
Pilot Target Attainment:
Physical Packets:       [========------------------------] 32.1% (3,212 / 10,000)
Valid Windows:          [========------------------------] 32.7% (49 / 150)
Held-Out Fall Windows:  [====----------------------------] 11.4% (4 / 35)
Distinct Subjects:      [==========----------------------] 40.0% (2 / 5)
```

The data quality audit concludes that the repository's physical dataset remains in a pre-collection state pending physical execution by the operator.
