# CSIFormer Phase 18 — Real-World Dataset Quality & Telemetry Audit

## Executive Summary

This report establishes the baseline dataset quality, RF telemetry, and structural integrity of the real-world ESP32-S3 CSI dataset in Phase 18. Every metric in this document is derived directly from empirical inspection of the files in `data/real_csi_dataset/` and the primary manifest [`data/real_csi_dataset/dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json).

No synthetic samples have been converted into physical labels, and no physical recordings have been fabricated.

---

## 1. Audited Dataset Inventory & Activity Breakdown

The repository contains **24 session JSON files** and **24 corresponding CSV files**, plus the versioned manifests. Of these 24 sessions, **23 are indexed** in `dataset_manifest.json`, and **1 is an unindexed trial** (`phase14_p15_real_walk_t1_1792303844_1792303844.json`, an aborted trial conducted 23 seconds before its valid replacement).

Across the 23 indexed sessions, the dataset comprises:
- **Total Physical Packets:** 3,212
- **Total Cumulative Duration:** 89.0 seconds ($3.87\text{ s}$ average duration per session)
- **Extracted Non-Overlapping Windows (Size 50):** 49 sliding windows
- **Mean Windows per Session:** 2.13

### Activity Representation Table
| Activity Label | Model Class ID | Sessions | Physical Packets | Extracted Windows | Window Share (%) |
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

The 23 sessions are divided across only two subjects:

| Participant ID | Sessions | Physical Packets | Windows | `walk` | `fall` | `sit` | `clap` | `push_pull` | `static` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Participant_01` | 12 | 1,655 | 25 | 4 | 4 | 4 | 4 | 5 | 4 |
| `Participant_02` | 11 | 1,557 | 24 | 5 | 4 | 6 | 4 | 4 | 1 |
| **Total** | **23** | **3,212** | **49** | **9** | **8** | **10** | **8** | **9** | **5** |

### Event & Fall Window Accounting
- **Total Fall Sessions:** 4 sessions (2 per participant).
- **Total Fall Events:** 4 discrete physical trials (forward breakfalls onto mats).
- **Total Fall Windows:** 8 sliding windows ($2.0$ windows per session).
- **Held-Out Test Fall Windows (2-way LOSO with `Participant_02` test):** **4 windows** (derived from 2 physical trials).

---

## 3. Subcarrier Representation & Dimensional Analysis

### 3.1 Historical Recordings (Phase 15 Sessions)
- **Raw Physical Preservation:** 0 / 23 sessions preserved raw subcarriers.
- **Stored Representation:** 56-subcarrier interpolated arrays (`amp_0` to `amp_55`).
- **Audit Observation:** Historical files did not save `raw_amplitudes` or `raw_phases`. The values stored are linear interpolations produced by `RealCSICollector._process_parsed_frame` to conform to the 56-channel input layer of CSIFormer.

### 3.2 Upgraded Collection Pipeline (Phase 17/18)
- **Raw Physical Field:** `raw_amplitudes` preserves the exact list of subcarrier amplitudes parsed from the serial packet (dynamic length $N_{\text{raw}}$, matching hardware packet output).
- **Aligned Model Field:** `amplitudes` preserves the 56-subcarrier interpolated representation for CSIFormer inference.
- **Traceability Field:** `subcarrier_alignment_method: "linear_interpolation_to_56"`.

---

## 4. Environmental & Geometric Distribution

All 23 existing recordings were gathered under a single physical configuration:
- **Room Type:** `Laboratory_Room1` (100%, 23/23 sessions).
- **Baseline Tx-Rx Distance:** 2.5 meters (100%, 23/23 sessions).
- **Antenna Heights:** ~1.0 meter above ground.
- **Obstruction State:** Line-of-Sight (LOS).
- **Participant Orientation:** Recorded as `Unknown` in legacy metadata.

### Scientific Assessment:
The current dataset has zero cross-room diversity and zero distance diversity. A model evaluated exclusively on this dataset cannot provide meaningful claims regarding generalization across different floor plans, furniture clutter, through-wall sensing (NLOS), or varying signal-to-noise geometries.

---

## 5. Radio Signal Telemetry & Packet Loss Accounting

- **Carrier Frequency:** 2.442 GHz (Channel 7, 802.11n HT20 mode).
- **Router Infrastructure:** SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`.
- **Packet Streaming Rate:** $35.6 \pm 1.8$ Hz (sustained via active UDP stimulation at 35 pulses/sec).
- **Mean RSSI:** $-58.2 \pm 2.1$ dBm (excellent signal margin, $> 20$ dB above receiver sensitivity floor).
- **Packet Loss Rate:** $1.20\%$ mean dropped packet rate, detected via non-consecutive hardware sequence numbers ($\Delta \text{seq} > 1$). No burst drops exceeding 3 packets were detected.
- **Hardware Clock Monotonicity:** Hardware microsecond timestamps (`timestamp_us`) are strictly non-decreasing across all valid trials.

---

## 6. Unknown Labels & Interruption Handling

The dataset quality gate enforces that any trial with uncertain ground truth remains labeled as `unknown`:
1. **Unconfirmed Trials:** If an operator rejects ground-truth confirmation during post-capture review, `ground_truth_confirmed` is set to `False` and `activity_label` is set to `"unknown"` (Class ID `-1`).
2. **Interrupted Captures:** If serial streaming terminates before the target duration (e.g. 10 frames captured instead of 140), `CollectionWorkflowManager.stop_session` safely writes the partial buffer, records `capture_interrupted: True`, and keeps the activity as `"unknown"` if unconfirmed.
3. **No Silent Relabeling:** The software strictly forbids converting unconfirmed or ambiguous captures into valid activity labels.

---

## 7. Pilot Milestone Progress & Gap Analysis

| Pilot Metric | Phase 18 Target | Current Audited Count | Deficit Remaining |
| :--- | :---: | :---: | :---: |
| **Total Physical Sessions** | $\ge 50$ | 23 | **-27 sessions** |
| **Total Physical Packets** | $\ge 10,000$ | 3,212 | **-6,788 packets** |
| **Valid Sliding Windows** | $\ge 150$ | 49 | **-101 windows** |
| **Distinct Participants** | $\ge 5$ | 2 | **-3 participants** |
| **Distinct Rooms** | $\ge 3$ | 1 | **-2 rooms** |
| **Held-Out Test Fall Windows** | $\ge 35$ | 4 | **-31 windows** |
| **Held-Out Distinct Fall Events** | $\ge 12$ | 2 | **-10 events** |

```
Phase 18 Pilot Milestone Attainment:
Physical Packets:       [========------------------------] 32.1% (3,212 / 10,000)
Valid Windows:          [========------------------------] 32.7% (49 / 150)
Held-Out Fall Windows:  [====----------------------------] 11.4% (4 / 35)
Participants:           [==========----------------------] 40.0% (2 / 5)
```

The dataset quality audit confirms that while the data acquisition pipeline is operational and stable, the physical dataset remains in a pilot pre-collection state.
