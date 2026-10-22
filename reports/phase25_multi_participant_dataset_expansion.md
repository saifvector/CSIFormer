# CSIFormer Phase 25 — Multi-Participant Real CSI Dataset Expansion & Data Quality Assurance Report

**Execution Date:** October 19, 2026  
**Environment:** Windows (x86_64), Python 3.11.9  
**Repository Root:** `C:\Users\saifu\Desktop\4-1 project`  
**Dataset Path:** `data/real_csi_dataset/`  
**Manifest Path:** `data/real_csi_dataset/dataset_manifest.json`  
**Hardware Ingestion:** ESP32-S3 (CH343 USB-Enhanced-SERIAL @ COM5, 115200 baud)  
**Wi-Fi AP:** TP-Link Archer C6, BSSID `98:ba:5f:ef:28:26`, Channel 7 (2.442 GHz)  

---

## 1. Executive Summary & Stage Decision Matrix

| Stage | Activity | Decision | Primary Verification Evidence |
| :--- | :--- | :---: | :--- |
| **Stage 1** | Baseline Dataset Inventory | **COMPLETE** | 29 sessions, 4,073 frames, 62 windows ($T=50$), 3 participants, checkpoints verified. |
| **Stage 2** | Evidence-Based Collection Matrix | **COMPLETE** | Identified distance homogeneity (100% at 2.5m) and lack of Participant_04; operator confirmed Participant_04 @ 2.0m. |
| **Stage 3** | Live Hardware Verification | **GO** | COM5 verified: 61 packets across 12.0s @ 73.0 Hz, RSSI -71.0 dBm, 5 raw subcarriers, 0 errors, status `CSI_STREAM_ACTIVE`. |
| **Stage 4** | Physical CSI Data Acquisition | **GO** | 5 physical sessions collected for `Participant_04` in Laboratory @ 2.0m; 704 frames captured; 100% passed integrity validator. |
| **Stage 5** | Participant-Independent Split Audit | **COMPLETE** | 3-way LOSO split verified with zero participant, event, or window leakage across partitions. |
| **Stage 6** | Test Suite & Checkpoint Verification | **PASS** | 117/117 regression tests passing across 12 test suites; production and experimental checkpoint hashes bit-for-bit identical. |
| **Stage 7** | Data-Readiness Gate | **PASS / BLOCKED** | Collection Readiness: **GO**; Diversity Readiness: **PARTIAL GO**; Evaluation Readiness: **NO-GO (BLOCKED)**. |
| **Stage 8** | Phase 25 Completion Report | **COMPLETE** | Comprehensive evidence documented in `reports/phase25_multi_participant_dataset_expansion.md`. |

---

## 2. Checkpoint Protection & Bit-for-Bit Hash Invariance

In strict compliance with Rules 7 and 8, no model training, fine-tuning, adaptation, benchmark evaluation, or inference comparisons were conducted. Both model checkpoints were verified bit-for-bit before and after Phase 25.

| Checkpoint Name | File Location | Expected MD5 Hash | Measured Initial Hash | Measured Final Hash | Verification Result |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Production Model** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **BIT-FOR-BIT IDENTICAL** |
| **Experimental Model** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **BIT-FOR-BIT IDENTICAL** |

---

## 3. Baseline Dataset Inventory & Collection Matrix Analysis

### 3.1 Initial Baseline (Pre-Phase 25)
- **Indexed Sessions:** 29
- **Total Physical Frames:** 4,073
- **Total Non-Overlapping Windows ($T=50$):** 62
- **Participants:** 3 (`Participant_01`: 12 sessions, `Participant_02`: 11 sessions, `Participant_03`: 6 sessions)
- **Environments:** `Laboratory_Room1 @ 2.5m` (23 sessions), `Laboratory @ 2.5m` (6 sessions)

### 3.2 Identified Dataset Gaps
1. **Geometric/Distance Homogeneity:** 100% of the baseline dataset recordings were conducted at a single fixed distance of $2.5\text{ m}$. No variations (e.g. $2.0\text{ m}$, $1.5\text{ m}$) existed.
2. **Participant Representation:** Only 3 participants were present. Expanding to a 4th participant provides true 4-way cross-validation capability and multi-participant partitioning (e.g. 2 Train, 1 Val, 1 Test).
3. **Activity Balance:** Ordinary activities (`walk`, `sit`, `clap`, `push_pull`, `static`) required reinforcement under varied distance geometries.

### 3.3 Operator Confirmation & Collection Protocol
The operator was presented with the gap analysis and confirmed:
- **Participant:** `Participant_04` (consenting; expands dataset to 4 distinct individuals).
- **Environment:** `Laboratory @ 2.0 meters` (introducing the first geometric distance variation).
- **Activities:** `static`, `sit`, `walk`, `clap`, `push_pull` (4.0 seconds duration each).
- **Safety Protocol:** Strictly zero falls or dangerous movements.

---

## 4. Hardware Verification Evidence

Verification was executed via the supported CLI tool prior to session recording:  
`py -3.11 scratch/run_collection_session.py --verify`

```
================================================================================
PHASE 21 — HARDWARE VERIFICATION & DIAGNOSTIC CHECK
================================================================================
Testing port COM5 for 12.0s...
[RealCSICollector] Successfully connected to COM5 @ 115200 baud.
[RealCSICollector] Background CSI acquisition loop started.
[RealCSICollector] Disconnected serial interface. Port released: True
Status:             OK
Diagnostic State:   CSI_STREAM_ACTIVE
Port:               COM5 @ 115200 baud
Connected:          True
Test Duration:      12.0s
Serial Bytes:       10596
Lines Received:     233
Records Detected:   61
Valid CSI Packets:  61
Parsing Errors:     0
CSI Dimensions:     5
Observed Rate:      73.0 Hz
Mean RSSI:          -71.0 dBm
Detected Protocol:  raw_iq_stream

Recent Firmware Messages / Boot Telemetry:
  > I (781) wifi:set rx beacon pti, rx_bcn_pti: 0, bcn_timeout: 25000, mt_pti: 0, mt_time: 10000
  > I (791) wifi:<ba-add>idx:1 (ifx:0, 98:ba:5f:ef:28:26), tid:0, ssn:1, winSize:64
  > I (831) wifi:AP's beacon interval = 102400 us, DTIM period = 1
  > CSI callback: ESP_OK
  > CSI Receiver Started

Diagnostic State Summary:
  [SUCCESS] Valid physical CSI packets are actively streaming from ESP32-S3.
================================================================================
```

---

## 5. Incremental Physical CSI Collection (Phase 25)

Five distinct physical sessions were captured from the live hardware, finalized atomically, validated against quality gates, and indexed.

### 5.1 Recorded Session Table

| Session Identifier | Activity | Class ID | Duration | Packet Count | Empirical Rate | Timestamp Span | Loss Rate | Validation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `phase16_real_static_Participant_04_1792389853_1792389853` | `static` | 6 | 4.02s | 144 | 36.00 Hz | 3.9723s | 0.00% | **PASSED** |
| `phase16_real_sit_Participant_04_1792389881_1792389881` | `sit` | 8 | 4.02s | 137 | 34.24 Hz | 3.9722s | 0.00% | **PASSED** |
| `phase16_real_walk_Participant_04_1792389907_1792389907` | `walk` | 11 | 4.02s | 142 | 35.49 Hz | 3.9725s | 0.00% | **PASSED** |
| `phase16_real_clap_Participant_04_1792389936_1792389936` | `clap` | 2 | 4.02s | 139 | 34.74 Hz | 3.9724s | 0.00% | **PASSED** |
| `phase16_real_push_pull_Participant_04_1792389966_1792389966` | `push_pull` | 0 | 4.02s | 142 | 35.49 Hz | 3.9726s | 0.00% | **PASSED** |

### 5.2 Signal Quality & Timing Integrity
- **Total Physical Frames Captured:** 704 frames.
- **Dropped Packets:** 0 across all 5 recordings (continuous step 1 sequence counter).
- **Duplicate Timestamps:** 0.
- **Timestamp Monotonicity:** Strictly monotonic increasing.
- **CSV Mirrors:** 100% correspond row-for-row with JSON files (144, 137, 142, 139, 142 data rows + header).
- **Validation Failures / Partial Sessions:** None (0 quarantined, 0 rejected).

---

## 6. Raw Measurements vs. Derived Model Features

In compliance with Rule 3:
- **Raw Measurements:** Each frame stores the actual baseband hardware reading under `raw_amplitudes` and `raw_phases` with **5 complex subcarrier pairs** (10 scalars per frame).
- **Derived Model Features:** Each frame stores a derived **56-channel tensor** under `amplitudes` and `phases`, linearly interpolated to the standard IEEE 802.11n HT20 subcarrier grid.
- **Dataset Audit:** Across the entire dataset, 1,565 frames carry raw 5-subcarrier measurements (Phase 22, Phase 24, and Phase 25), while all 4,777 frames maintain 56 aligned channels.

---

## 7. Dataset Reconciliation (Before vs. After Phase 25)

| Metric | Phase 24 Baseline | Phase 25 Result | Delta | Reconciliation Verification |
| :--- | :---: | :---: | :---: | :--- |
| **Total Indexed Sessions** | 29 | **34** | +5 | 5 newly collected physical sessions for Participant_04. |
| **Total Physical Frames** | 4,073 | **4,777** | +704 | 144 (static) + 137 (sit) + 142 (walk) + 139 (clap) + 142 (push_pull). |
| **Non-overlapping Windows ($T=50$)** | 62 | **72** | +10 | +2 (static), +2 (sit), +2 (walk), +2 (clap), +2 (push_pull). |
| **Distinct Participants** | 3 | **4** | +1 | `Participant_01`, `Participant_02`, `Participant_03`, `Participant_04`. |
| **Distinct Event IDs** | 29 | **34** | +5 | Each physical trial assigned a distinct UUID event. |
| **Distance Environments** | 1 (2.5m only) | **2** (2.5m and 2.0m) | +1 | First geometric diversity in dataset. |
| **All Sessions Valid** | True | **True** | 0 | 34 out of 34 pass `DatasetIntegrityValidator`. |
| **Quarantined / Rejected Files** | 0 | **0** | 0 | 0 corrupted recordings. |

### Activity Window Distribution Breakdown ($T=50$)

| Activity Label | Baseline Windows | Phase 25 Added Windows | Total Windows | Class Integrity Notes |
| :--- | :---: | :---: | :---: | :--- |
| `walk` | 13 | +2 | **15** | Represented across all 4 participants |
| `sit` | 13 | +2 | **15** | Represented across all 4 participants |
| `push_pull` | 11 | +2 | **13** | Represented across all 4 participants |
| `clap` | 10 | +2 | **12** | Represented across all 4 participants |
| `static` | 7 | +2 | **9** | Represented across all 4 participants |
| `fall` | 8 | +0 | **8** | **Strictly preserved; 0 hazardous movements** |
| **Total** | **62** | **+10** | **72** | — |

---

## 8. Participant-Independent Split Audit (Zero Leakage)

With 4 distinct participants, `ParticipantIndependentSplitGenerator` supports true 3-way Leave-One-Subject-Out partitioning:

### Partition Allocation Example
- **Training Partition:** `['Participant_01', 'Participant_03']` (18 sessions, 38 windows, 2 fall events)
- **Validation Partition:** `['Participant_04']` (5 sessions, 10 windows, 0 fall events)
- **Testing Partition:** `['Participant_02']` (11 sessions, 24 windows, 2 fall events)

### Safeguards Verification
1. **Subject Isolation:** `train_participants`, `val_participants`, and `test_participants` are strictly disjoint sets (0% subject overlap).
2. **Event Isolation:** All windows belonging to an event remain entirely within that event's split (0% event leakage).
3. **Window Independence:** Windows are non-overlapping slices ($T=50$ frames), preventing sliding temporal leakage.

---

## 9. Regression Test Suite Execution

The full regression suite comprising 12 test modules was executed:

**Command:**  
`py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py backend/tests/test_phase22.py backend/tests/test_phase23.py backend/tests/test_phase25.py backend/tests/test_safe_disconnection.py backend/tests/test_sampling_rate_audit.py -v`

### Summary
- **Total Test Files:** 12 modules
- **Tests Executed:** 117
- **Passed:** **117** (100.0%)
- **Failed:** **0**
- **Skipped:** **0**
- **Duration:** 18.97 seconds
- **Warnings:** 4 (upstream PyTorch and FastAPI testclient notices)

---

## 10. Data-Readiness Gate Assessment

| Evaluation Dimension | Readiness Status | Evidence & Barrier Analysis |
| :--- | :---: | :--- |
| **Collection Readiness** | **GO (PASSED)** | Hardware verified live @ 73 Hz on COM5; atomic JSON/CSV write confirmed; validator reports 100% pass on all 34 sessions; serial interface cleanly released. |
| **Dataset Diversity Readiness** | **PARTIAL GO (CONDITIONAL)** | Expanded to 4 distinct participants; added first distance variation (2.0m); all 5 ordinary activities have multi-subject coverage. Limitation: `fall` class is absent from `Participant_03` and `Participant_04` due to safety constraints. |
| **Model-Evaluation Readiness** | **NO-GO (BLOCKED)** | Strict Leave-One-Subject-Out evaluation on `Participant_03` or `Participant_04` raises `InadequateClassCoverageError` due to missing fall class. Research evaluation remains safely on hold until certified crash-mat fall protocols are executed. |

---

## 11. Git Working Tree & Secret Auditing

1. **No Checkpoint Changes:** `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` are bit-for-bit unchanged.
2. **No Historical Rewrites:** No historical sessions or metadata were modified; changes consist only of additions and non-breaking test improvements.
3. **No Secrets Exposed:** Wi-Fi credentials, tokens, and sensitive strings were omitted from code and logs.
4. **No Git Commit or Push:** In adherence to Rule 10, no Git commits or remote pushes were executed.

---

## 12. Remaining Limitations & Recommended Next Steps

### Limitations
1. **Fall Class Imbalance:** `Participant_03` and `Participant_04` have 0 fall recordings.
2. **Model Evaluation Barrier:** Generalization benchmarks against `Participant_03` or `Participant_04` are blocked pending supervised fall trials.

### Recommended Next Actions (Phase 26)
1. **Multi-Environment Expansion:** Conduct recordings in an Office or Bedroom environment with consenting participants.
2. **Certified Spotter Protocol:** If fall data is required for new participants, prepare a certified crash mat with a designated spotter.
3. **Preserve Checkpoint Freezing:** Keep existing model weights frozen.

---

## 13. Final Acceptance Verdict

- [x] Baseline dataset established and gap analysis conducted.
- [x] Hardware connection verified live on COM5 with 61 valid packets @ 73 Hz.
- [x] Real CSI recordings acquired from consenting `Participant_04` in Laboratory @ 2.0m.
- [x] Raw (5 subcarriers) vs. derived (56 subcarriers) features preserved.
- [x] Manifest and physical files reconciled (34 sessions, 4,777 frames, 72 windows).
- [x] 3-way LOSO split verified with zero participant, event, or window leakage.
- [x] Regression test suite passing (117/117 tests passed).
- [x] Checkpoints verified bit-for-bit unchanged.
- [x] Model training, adaptation, and evaluation strictly withheld.

**Phase 25 Status:** **COMPLETE & VERIFIED (EVALUATION SAFELY BLOCKED)**
