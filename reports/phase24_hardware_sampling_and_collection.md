# CSIFormer Phase 24 — Hardware Verification, Sampling-Rate Audit & Real CSI Data Collection Report

**Execution Date:** October 19, 2026  
**Operator Environment:** Windows (x86_64), Python 3.11.9  
**Repository Root:** `C:\Users\saifu\Desktop\4-1 project`  
**Git Working Branch:** `main` (clean working state with local audit enhancements, no uncommitted corruptions)  
**Target Hardware:** ESP32-S3 (CH343 USB-Enhanced-SERIAL @ COM5, 115200 baud)  
**Network Infrastructure:** TP-Link Archer C6 Access Point, BSSID `98:ba:5f:ef:28:26`, Channel 7 (2.442 GHz)  

---

## 1. Executive Summary & Stage-by-Stage Decisions

| Stage | Focus Area | Status | Decision | Primary Evidence |
| :--- | :--- | :---: | :---: | :--- |
| **Stage 1** | Repository & Environment Preflight | **COMPLETE** | **GO** | Python 3.11.9 active; baseline 24 sessions (3,355 frames); both checkpoint hashes verified bit-for-bit identical to baseline records. |
| **Stage 2** | Sampling-Rate Discrepancy Audit | **COMPLETE** | **GO** | Discrepancy resolved mathematically (fencepost interval division vs wall-clock duration); $(N-1)/\Delta t$ standardized; 7 deterministic tests passing in `test_sampling_rate_audit.py`. |
| **Stage 3** | Live ESP32-S3 Hardware Verification | **COMPLETE** | **GO** | COM5 opened cleanly; 56 physical packets observed across 12.0s (37.7 Hz, RSSI -60.0 dBm, 5 raw subcarriers, 0 parsing errors, status `CSI_STREAM_ACTIVE`). |
| **Stage 4** | Real Physical CSI Collection | **COMPLETE** | **GO** | Participant_03 confirmed consent; 5 physical sessions recorded (`static`, `sit`, `walk`, `clap`, `push_pull`); 718 genuine physical frames captured; 100% passed integrity validation. |
| **Stage 5** | Dataset Integrity & Split Audit | **COMPLETE** | **GO** | Dataset expanded to 29 sessions, 4,073 frames, 62 windows; 0 participant/event/window leakage in LOSO generator; model evaluation blocked due to 0 test falls. |
| **Stage 6** | Regression Tests & Checkpoint Protection | **COMPLETE** | **GO** | 109/109 tests passed across Phases 14, 16–23, safe disconnection, and sampling audit; checkpoints bit-for-bit preserved. |
| **Stage 7** | Evidence-Based Completion Report | **COMPLETE** | **GO** | Comprehensive report generated in `reports/phase24_hardware_sampling_and_collection.md`. |

---

## 2. Checkpoint Protection & Invariance Verification

As required by Mandatory Rules 5 and 6, no model training, fine-tuning, benchmark evaluation, adaptation, or weight modification was executed in Phase 24. Checkpoints were verified bit-for-bit before any operations and re-verified upon phase completion.

| Checkpoint Identifier | Physical File Path | Expected MD5 Hash | Measured Initial Hash | Measured Final Hash | Invariance Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Production Model** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **PRESERVED (MATCH)** |
| **Experimental Model** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **PRESERVED (MATCH)** |

---

## 3. Sampling-Rate Discrepancy Investigation & Resolution

### 3.1 Empirical Analysis of Session `phase16_real_walk_Participant_03_1792339078_1792339078`
Phase 23 reported a discrepancy between the stored mean sampling rate (~35.56 Hz), naively calculated rate (~35.95 Hz), and elapsed timestamp span (~3.977s) across 143 frames.

Investigation of `data/real_csi_dataset/phase16_real_walk_Participant_03_1792339078_1792339078.json` yielded the following raw values:
- **Total frames captured:** $N = 143$ frames
- **Number of inter-frame intervals:** $N - 1 = 142$ intervals
- **First frame timestamp ($t_0$):** `1792339078.4786937`
- **Last frame timestamp ($t_{142}$):** `1792339082.4559603`
- **Physical timestamp span ($\Delta t$):** $t_{142} - t_0 = 3.9772666\text{ seconds}$
- **Host wall-clock duration stored in metadata ($T_{wall}$):** `4.02 seconds` (measured as `4.02137 seconds` by host `time.time()`)
- **Inter-frame interval statistics ($\Delta t_i = t_i - t_{i-1}$):**
  - Mean interval $\overline{\Delta t}$: $0.0280089\text{ s}$ ($28.009\text{ ms}$)
  - Median interval: $0.0285343\text{ s}$ ($28.534\text{ ms}$)
  - Standard deviation: $0.0298294\text{ s}$ ($29.829\text{ ms}$)
  - Minimum interval: $0.0015392\text{ s}$ ($1.539\text{ ms}$)
  - Maximum interval: $0.3034401\text{ s}$ ($303.440\text{ ms}$)
  - Sequence continuity: Sequence IDs strictly increment from 5 to 147 with step 1 (0 dropped packets)
  - Monotonicity: Strictly monotonic ($\Delta t_i > 0$ for all $i$, 0 duplicate timestamps, 0 clock reversals)

### 3.2 Root Cause Identification
The numerical discrepancy between 35.56 Hz and 35.95 Hz was caused by two distinct computational inconsistencies in prior code:

1. **Stored Metadata Rate ($35.56\text{ Hz}$):**  
   In `RealCSICollector.stop_session_recording()`, the stored rate was calculated as:
   $$\text{stored\_rate} = \frac{N}{T_{wall}} = \frac{143}{4.02137\text{ s}} \approx 35.5601\text{ Hz} \to 35.56\text{ Hz}$$
   This used the **host process wall-clock elapsed time** between `start_session_recording()` and `stop_session_recording()`. Because of ~44 ms thread invocation latency, buffer allocation, and disk lock acquisition overhead, $T_{wall} > \Delta t$, resulting in an underestimated physical rate.

2. **Naive Calculation Rate ($35.95\text{ Hz}$):**  
   Calculated by dividing frame count $N$ by the physical elapsed span $\Delta t$:
   $$\text{naive\_rate} = \frac{N}{t_{N-1} - t_0} = \frac{143}{3.9772666\text{ s}} \approx 35.9543\text{ Hz} \to 35.95\text{ Hz}$$
   This committed a classical **fencepost error**: dividing $N$ discrete points by the duration that spans only $N - 1$ intervals.

3. **True Physical Empirical Sampling Rate:**  
   The mathematically correct sampling frequency for $N$ events across $N - 1$ intervals is:
   $$f_{empirical} = \frac{N - 1}{t_{N-1} - t_0} = \frac{1}{\overline{\Delta t}} = \frac{142}{3.9772666\text{ s}} = 35.7029\text{ Hz}$$

### 3.3 Standardized Metric Implementation & Unit Testing
A standardized metric calculation function `compute_session_sampling_rate(timestamps, wall_duration_s=None)` was implemented in `backend/app/services/session_validator.py` and integrated into `RealCSICollector.stop_session_recording()`.

**Standardized Formula Definition:**
$$f_{empirical} = \begin{cases} \frac{N - 1}{t_{N-1} - t_0} = \frac{1}{\overline{\Delta t}}, & \text{if } N \ge 2, \Delta t > 0, \text{ and timestamps are strictly monotonic} \\ 0.0\text{ Hz}, & \text{otherwise (invalid session / insufficient data)} \end{cases}$$

**Deterministic Unit Test Suite (`backend/tests/test_sampling_rate_audit.py`):**
- `test_sampling_rate_regular_intervals`: Confirmed 40 Hz and 35 Hz regular sequences match exact mathematical targets.
- `test_sampling_rate_single_frame_and_empty`: Confirmed $N=0$ and $N=1$ yield 0.0 Hz with `valid=False`.
- `test_sampling_rate_duplicates_and_non_monotonic`: Confirmed rejection of duplicate timestamps and clock reversals.
- `test_sampling_rate_irregular_intervals`: Confirmed jittered intervals average to $(N-1)/\Delta t$.
- `test_sampling_rate_non_finite`: Confirmed rejection of NaN and Inf values.
- `test_sampling_rate_real_physical_session_recalculation`: Confirmed physical session yields $35.7029\text{ Hz}$ and reconciles both the $35.56\text{ Hz}$ wall rate and $35.95\text{ Hz}$ naive rate.
- `test_session_validator_returns_sampling_rate_metrics`: Confirmed validator integration returns all metrics.
- **Result:** 7/7 unit tests passing.

---

## 4. Live ESP32-S3 Hardware Verification Evidence

Verification was executed via the project's supported CLI command:  
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
Serial Bytes:       10093
Lines Received:     222
Records Detected:   56
Valid CSI Packets:  56
Parsing Errors:     0
CSI Dimensions:     5
Observed Rate:      37.7 Hz
Mean RSSI:          -60.0 dBm
Detected Protocol:  raw_iq_stream

Recent Firmware Messages / Boot Telemetry:
  > I (711) wifi:set rx beacon pti, rx_bcn_pti: 0, bcn_timeout: 25000, mt_pti: 0, mt_time: 10000
  > I (721) wifi:AP's beacon interval = 102400 us, DTIM period = 1
  > I (2051) wifi:<ba-add>idx:1 (ifx:0, 98:ba:5f:ef:28:26), tid:0, ssn:1, winSize:64
  > CSI callback: ESP_OK
  > CSI Receiver Started

Diagnostic State Summary:
  [SUCCESS] Valid physical CSI packets are actively streaming from ESP32-S3.
================================================================================
```

### Hardware Verification Verification Summary
- **Serial Port Existence & Opening:** `COM5` opened cleanly @ 115200 baud; CH343 driver confirmed.
- **Bytes Received:** 10,093 bytes across 12.0 seconds observation.
- **Valid Packets:** 56 valid CSI packets parsed with 0 parsing errors.
- **Measured Subcarriers:** 5 raw complex subcarriers ($I/Q$ pairs), exactly preserving physical measurement fidelity.
- **Packet Rate:** 37.7 Hz (exceeds the 30.0 Hz minimum threshold).
- **RSSI:** -60.0 dBm average across Wi-Fi channel 7.
- **Wi-Fi Association:** Connected to TP-Link Archer C6 (`98:ba:5f:ef:28:26`), 2.442 GHz.
- **Port Release:** Cleanly disconnected and released serial port resource.

---

## 5. Physical CSI Data Collection Campaign (Phase 24)

### 5.1 Protocol, Safety & Consent
- **Participant:** `Participant_03` (authorized pseudonymized identifier).
- **Consent:** Operator confirmed participant consent and readiness for ordinary activities.
- **Environment:** `Laboratory`, baseline line-of-sight (LOS) configuration, $2.5\text{ m}$ Tx-Rx distance.
- **Safety Rule 9 Enforcement:** Fall activities were strictly prohibited during this campaign; only low-risk, ordinary activities were captured.

### 5.2 Recorded Physical Sessions

| Session Identifier | Activity | Class ID | Duration (s) | Frame Count | Empirical Rate | Timestamp Span | Loss Rate | Validation Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `phase16_real_static_Participant_03_1792388605_1792388605` | `static` | 6 | 4.02s | 141 | 35.25 Hz | 3.9716s | 0.00% | **PASSED** |
| `phase16_real_sit_Participant_03_1792388631_1792388631` | `sit` | 8 | 4.02s | 152 | 38.04 Hz | 3.9699s | 0.00% | **PASSED** |
| `phase16_real_walk_Participant_03_1792388657_1792388657` | `walk` | 11 | 4.02s | 139 | 34.74 Hz | 3.9725s | 0.00% | **PASSED** |
| `phase16_real_clap_Participant_03_1792388686_1792388686` | `clap` | 2 | 4.02s | 145 | 36.25 Hz | 3.9723s | 0.00% | **PASSED** |
| `phase16_real_push_pull_Participant_03_1792388712_1792388712` | `push_pull` | 0 | 4.04s | 141 | 34.98 Hz | 4.0024s | 0.00% | **PASSED** |

### 5.3 Physical Session Artifacts
For each session, both JSON (primary recording with metadata and raw subcarriers) and CSV (tabular mirror) files were atomically written, flushed, validated by `DatasetIntegrityValidator`, indexed into `dataset_manifest.json`, and the serial interface cleanly released.

- `data/real_csi_dataset/phase16_real_static_Participant_03_1792388605_1792388605.json` (141 frames)
- `data/real_csi_dataset/phase16_real_static_Participant_03_1792388605_1792388605.csv`
- `data/real_csi_dataset/phase16_real_sit_Participant_03_1792388631_1792388631.json` (152 frames)
- `data/real_csi_dataset/phase16_real_sit_Participant_03_1792388631_1792388631.csv`
- `data/real_csi_dataset/phase16_real_walk_Participant_03_1792388657_1792388657.json` (139 frames)
- `data/real_csi_dataset/phase16_real_walk_Participant_03_1792388657_1792388657.csv`
- `data/real_csi_dataset/phase16_real_clap_Participant_03_1792388686_1792388686.json` (145 frames)
- `data/real_csi_dataset/phase16_real_clap_Participant_03_1792388686_1792388686.csv`
- `data/real_csi_dataset/phase16_real_push_pull_Participant_03_1792388712_1792388712.json` (141 frames)
- `data/real_csi_dataset/phase16_real_push_pull_Participant_03_1792388712_1792388712.csv`

---

## 6. Raw vs. Interpolated Subcarrier Representation Disclosure

In compliance with Rule 4, the distinction between physical measurement payloads and derived model-input tensors is explicitly maintained:

- **Raw Physical Measurement Payload:**
  - Firmware extracts raw complex $I/Q$ subcarrier pairs from the ESP32-S3 Wi-Fi baseband hardware.
  - The physical packets contain **5 complex subcarriers** (10 real-valued floating-point numbers per frame).
  - Stored under `raw_amplitudes` and `raw_phases` in each frame object.
- **Derived Model Representation:**
  - Model input requirements (`csiformer`) expect a 56-subcarrier representation aligned with standard IEEE 802.11n HT20 subcarriers.
  - Derived via linear interpolation from the 5 measured physical subcarriers (`subcarrier_alignment_method: "linear_interpolation_to_56"`).
  - Stored under `amplitudes` and `phases` (length 56) in each frame object.

---

## 7. Dataset Integrity & Participant-Independent Split Audit

### 7.1 Dataset Evolution (Before vs. After Phase 24)

| Metric | Baseline (End of Phase 23) | Post-Collection (Phase 24) | Delta | Reconciliation Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Indexed Sessions** | 24 | **29** | +5 | 5 newly collected physical sessions for Participant_03. |
| **Physical Packets / Frames** | 3,355 | **4,073** | +718 | 141 (static) + 152 (sit) + 139 (walk) + 145 (clap) + 141 (push_pull). |
| **Valid Non-overlapping Windows ($T=50$)** | 51 | **62** | +11 | +2 (static), +3 (sit), +2 (walk), +2 (clap), +2 (push_pull). |
| **Distinct Participants** | 3 | **3** | 0 | `Participant_01`, `Participant_02`, `Participant_03`. |
| **Distinct Events** | 24 | **29** | +5 | Each physical recording assigned unique event ID. |
| **Valid Sessions** | 24 | **29** | +5 | 100% of sessions pass `DatasetIntegrityValidator`. |
| **Rejected / Quarantined Sessions** | 0 | **0** | 0 | 0 corrupted or non-compliant recordings detected. |

### 7.2 Activity Window Distribution ($T=50$ non-overlapping frames)

| Activity Label | Class ID | Baseline Windows | Phase 24 Windows | Total Windows | Fall Safety Compliance |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `walk` | 11 | 11 | +2 | **13** | Normal movement |
| `sit` | 8 | 10 | +3 | **13** | Normal movement |
| `push_pull` | 0 | 9 | +2 | **11** | Normal movement |
| `clap` | 2 | 8 | +2 | **10** | Normal movement |
| `fall` | 9 | 8 | +0 | **8** | **Strictly preserved; 0 hazardous movements** |
| `static` | 6 | 5 | +2 | **7** | Stationary baseline |
| **Total** | — | **51** | **+11** | **62** | — |

### 7.3 Participant Breakdown & LOSO Split Audit
- **`Participant_01`:** 12 sessions, 1,655 packets, 25 windows (`walk`: 4, `fall`: 4, `sit`: 4, `clap`: 4, `push_pull`: 5, `static`: 4).
- **`Participant_02`:** 11 sessions, 1,557 packets, 24 windows (`walk`: 5, `fall`: 4, `sit`: 6, `clap`: 4, `push_pull`: 4, `static`: 1).
- **`Participant_03`:** 6 sessions, 861 packets, 13 windows (`walk`: 4, `static`: 2, `sit`: 3, `clap`: 2, `push_pull`: 2, `fall`: 0).

**Leave-One-Subject-Out (LOSO) Partitioning Analysis:**
1. **Participant Isolation:**
   When generating LOSO splits with `Participant_02` held out for testing:
   - `train_participants`: `['Participant_01', 'Participant_03']` (18 sessions, 38 windows).
   - `test_participants`: `['Participant_02']` (11 sessions, 24 windows).
   - **Participant Leakage:** Exactly 0.0% (zero subject overlap).
   - **Event Leakage:** Exactly 0.0% (all windows from an event remain in that event's split).
   - **Window Leakage:** Exactly 0.0% (non-overlapping window slicing).
2. **Fall Coverage Limitation Barrier:**
   Because Participant_03 has 0 fall records (strictly adhering to safety rule 9):
   - Participant_03 **cannot** serve as an independent held-out test participant for fall detection evaluation (`InadequateClassCoverageError` is correctly raised by `ParticipantIndependentSplitGenerator(strict_coverage=True)`).
   - In accordance with Stage 5 requirements, model evaluation on Participant_03 remains **STRICTLY BLOCKED**.

---

## 8. Regression Test Suite Execution

The complete regression test suite covering Phase 14 through Phase 24 was executed using Python 3.11:  
`py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py backend/tests/test_phase22.py backend/tests/test_phase23.py backend/tests/test_safe_disconnection.py backend/tests/test_sampling_rate_audit.py -v`

### Test Summary
- **Total Test Files:** 11 test modules
- **Tests Executed:** 109
- **Passed:** **109** (100.0%)
- **Failed:** **0**
- **Skipped:** **0**
- **Execution Duration:** 19.98 seconds
- **Warnings:** 4 (harmless upstream deprecation notices from PyTorch nested tensor and FastAPI/Starlette testclient)

---

## 9. Git Working Tree & Secret Auditing

A thorough inspection of `git diff` and `git status` confirmed:
1. **No Checkpoint Alterations:** Checkpoint binaries `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` were untouched and remain byte-for-byte identical.
2. **No Historical Rewrites:** No historical dataset records, timestamps, or session IDs were rewritten.
3. **No Secrets Exposed:** No Wi-Fi passwords, tokens, API keys, or credentials were committed or logged.
4. **No Git Commit or Push:** In adherence to Rule 10, no Git commits or remote pushes were executed.

---

## 10. Limitations, Blockers & Recommended Next Actions

### Current Limitations
1. **Fall Class Imbalance on Participant_03:** Participant_03 has full coverage for all 5 ordinary activities (`static`, `sit`, `walk`, `clap`, `push_pull`), but has 0 fall trials due to mandatory safety rules.
2. **Model Evaluation Barrier:** Evaluation of participant-independent generalization using Participant_03 as the held-out test subject remains safely blocked until a certified, spotter-supervised breakfall protocol is formally approved and conducted.

### Recommended Next Actions (Phase 25)
1. **Maintain Checkpoint Protection:** Keep production (`phase13_best`) and experimental (`phase15_adapted`) weights frozen.
2. **Certified Fall Campaign Preparation:** If fall data collection for Participant_03 is required, establish a certified shock-absorbing mat setup with an active spotter prior to acquisition.
3. **Multi-Environment Expansion:** Once single-environment coverage is complete, expand physical recordings to Office and Bedroom environments with explicit participant consent.

---

## 11. Final Phase 24 Completion Sign-off

- [x] Sampling-rate discrepancy investigated, mathematically resolved ($(N-1)/\Delta t$), and covered by 7 unit tests.
- [x] Live ESP32-S3 hardware connection verified on COM5 with 56 valid packets @ 37.7 Hz, RSSI -60.0 dBm, 5 raw subcarriers, and 0 parsing errors.
- [x] 5 real physical CSI sessions collected with Participant_03, fully validated, and cleanly indexed.
- [x] Raw (5 subcarriers) versus derived (56 subcarriers) features strictly separated.
- [x] Full dataset integrity audit completed (29 sessions, 4,073 frames, 62 windows, 0 leakage).
- [x] Full regression test suite passing (109/109 tests passed).
- [x] Checkpoint weights verified byte-for-bit identical to baseline records.
- [x] Model training, adaptation, and evaluation strictly withheld.

**Phase 24 Status:** **COMPLETE & VERIFIED**
