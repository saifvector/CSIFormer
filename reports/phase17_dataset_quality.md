# CSIFormer Phase 17 — Dataset Quality & Collection Progress Report

## Executive Summary

This report establishes the baseline dataset quality and collection progress for the CSIFormer project in Phase 17. Synthesizing telemetry from all session recordings in `data/real_csi_dataset/`, this document provides an empirical audit of participant diversity, activity representation, environmental variation, RF signal fidelity, raw subcarrier preservation, and progress toward the Phase 16 pilot milestone of $\ge 35$ independently labeled fall test windows.

The empirical findings confirm that while the existing 23 sessions achieve a stable 35.6 Hz packet rate and low packet loss (1.2%), the dataset suffers from three severe bottlenecks:
1. **Participant Scarcity:** Only 2 participants exist (`Participant_01` and `Participant_02`), precluding 3-way participant-independent splitting.
2. **Zero Raw Subcarrier Preservation in Legacy Data:** 100% of historical sessions (23/23) discarded raw 52-subcarrier measurements, preserving only the 56-subcarrier interpolated arrays.
3. **Severe Fall Window Deficit:** Only 8 total fall windows exist across the entire dataset (4 per participant). Under a strict Leave-One-Subject-Out split, the held-out test participant provides only 4 fall windows—achieving only **11.4%** of the 35-window pilot target.

---

## 1. Participant & Activity Distribution

Across the 23 indexed sessions in `dataset_manifest.json`, the dataset contains **3,212 physical Wi-Fi packets** yielding **49 sliding windows** (window size: 50 packets, non-overlapping evaluation stride):

| Activity Label | Model Class ID | Sessions | Physical Packets | Extracted Windows | Windows / Session | Class Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `walk` | 11 | 4 | 590 | 9 | 2.25 | 18.37% |
| `fall` | 9 | 4 | 561 | 8 | 2.00 | 16.33% |
| `sit` | 8 | 4 | 595 | 10 | 2.50 | 20.41% |
| `clap` | 2 | 4 | 579 | 8 | 2.00 | 16.33% |
| `push_pull` | 0 | 4 | 578 | 9 | 2.25 | 18.37% |
| `static` | 6 | 3 | 309 | 5 | 1.67 | 10.20% |
| **Total** | — | **23** | **3,212** | **49** | **2.13** | **100.0%** |

### Unindexed Session File Audit
An unindexed trial file was identified in `data/real_csi_dataset/`:
- `phase14_p15_real_walk_t1_1792303844_1792303844.json` (147 frames, 2 windows).
- **Audit Finding:** This file represents an aborted trial conducted 23 seconds before the indexed trial `phase14_p15_real_walk_t1_1792303867_1792303867.json`. It is correctly excluded from the primary manifest to prevent double-counting.

---

## 2. Participant Coverage Breakdown

| Participant ID | Total Sessions | Total Packets | Total Windows | `walk` | `fall` | `sit` | `clap` | `push_pull` | `static` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `Participant_01` | 12 | 1,655 | 25 | 4 | 4 | 4 | 4 | 5 | 4 |
| `Participant_02` | 11 | 1,557 | 24 | 5 | 4 | 6 | 4 | 4 | 1 |
| **Total** | **23** | **3,212** | **49** | **9** | **8** | **10** | **8** | **9** | **5** |

### Key Observation:
Each participant contributed exactly 4 fall windows. In a clean 2-way Leave-One-Subject-Out evaluation (`Participant_01` train, `Participant_02` test), the evaluation is conducted on exactly **4 fall test windows**.

---

## 3. Environmental and Geometric Diversity Audit

The physical collection conditions across all 23 sessions are summarized below:

| Condition Parameter | Distribution in Dataset | Assessment & Limitation |
| :--- | :--- | :--- |
| **Room Type / Layout** | `Laboratory_Room1` (100%, 23/23) | **Zero Cross-Room Diversity.** The model has never been tested in living rooms, bedrooms, hallways, or bathrooms. |
| **Tx-Rx Distance** | 2.5 meters (100%, 23/23) | **Fixed Geometry.** Path loss, multipath delay spread, and SNR variations at 1.0m, 4.0m, or 6.0m are completely unrepresented. |
| **Participant Orientation** | `Unknown` (100%, 23/23) | **Uncontrolled Aspect Angle.** Relative angle between participant velocity vector and Tx-Rx baseline was unrecorded in legacy metadata. |
| **Obstruction State** | Line-of-Sight (LOS) | **Zero NLOS Coverage.** Through-wall or furniture-occluded sensing is uncharacterized. |

---

## 4. Signal Fidelity & Radio Telemetry

- **RF Carrier:** 2.442 GHz (Channel 7, 802.11n HT20 mode).
- **Target Router:** SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`.
- **Packet Reception Rate:** $35.6 \pm 1.8$ Hz (sustained via active UDP stimulation).
- **Mean RSSI:** $-58.2 \pm 2.1$ dBm (excellent signal strength; well above the $-82$ dBm sensitivity threshold).
- **Packet Loss Rate:** $1.20\%$ mean dropped packet rate, detected via hardware sequence number gaps. No multi-packet burst drops exceeding 3 consecutive frames were observed.
- **Raw CSI Preservation Status:**
  - Historical sessions (Phase 15): **0 / 23 sessions (0.0%)** preserved raw 52-subcarrier measurements.
  - Phase 17 Collector Pipeline: **100% compliant.** Both `raw_amplitudes` (52 values) and `amplitudes` (56 values) are preserved.

---

## 5. Pilot Milestone Evaluation: Fall Test Windows

Phase 16 defined an initial pilot milestone of **$\ge 35$ independently labeled fall test windows** to assess whether CSIFormer can reliably detect falls on real hardware.

$$\text{Total Fall Windows in Dataset} = 8$$
$$\text{Held-Out Unseen Participant Fall Windows (Test)} = 4$$
$$\text{Pilot Milestone Target} = 35$$
$$\text{Current Attainment (Total)} = \frac{8}{35} = 22.86\%$$
$$\text{Current Attainment (Held-Out Test)} = \frac{4}{35} = 11.43\%$$
$$\text{Deficit Remaining (Held-Out Test)} = 31\text{ windows}$$

```
Pilot Target Attainment (Held-Out Fall Windows):
[====--------------------------------] 11.4% (4 / 35 windows)
```

### Gap Analysis & Statistical Implications:
1. **High Variance in Metrics:** With only 4 fall test windows, one false negative drops recall from 100% to 75%; two false negatives drop recall to 50%. No statistically valid ROC-AUC or F1-score can be asserted.
2. **Missing Fall Topologies:** All 8 recorded falls are forward drops. Zero lateral falls, backwards slips, roll-offs from a sitting position, or slow stumbles have been collected.
3. **Safety Requirement:** Expanding the fall dataset by 31+ windows requires at least 4 additional participants performing supervised trials onto certified 4-inch shock-absorbing crash mats.
