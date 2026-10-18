# CSIFormer — Phase 22: First Verified Physical Recording & Dataset Expansion Readiness Report

## Executive Summary

Phase 22 executed and independently verified the first end-to-end physical Wi-Fi CSI data recording using the real ESP32-S3 hardware on `COM5`, successfully capturing a 4.0-second walking trial (`Participant_03`), validating physical data integrity, confirming metadata accuracy, indexing the session into `data/real_csi_dataset/dataset_manifest.json`, and expanding the physical dataset from 23 to 24 sessions and from 2 to 3 distinct participants.

Strict methodological invariants were maintained:
- **No model retraining, fine-tuning, evaluation, or weight modification was performed.**
- **No synthetic data substitution or data fabrication occurred.**
- Both production (`models/csiformer_phase13_best.pth`) and experimental (`models/csiformer_phase15_adapted.pth`) checkpoint MD5 hashes were verified to be bit-for-bit invariant before and after the recording.
- Physical raw measurements (5 complex subcarriers) are strictly separated from derived model-input representations (56 interpolated channels).

---

## 1. CLI Verification & Pre-Flight Audit

The command-line interface in `scratch/run_collection_session.py` was audited prior to running:

### Supported Options
- `--port PORT`: Serial port of ESP32-S3 (default `COM5`).
- `--verify`: Runs non-recording stream verification and diagnostics.
- `--validate`: Executes `DatasetIntegrityValidator` over all indexed manifest sessions on disk.
- `--activity {push_pull,clap,static,sit,fall,walk,unknown}`: Activity taxonomy label.
- `--participant PARTICIPANT`: Pseudonymized participant ID (e.g., `Participant_03`).
- `--duration DURATION`: Capture window duration in seconds (default `4.0`).
- `--room ROOM`: Room name / setup (default `Laboratory`).
- `--distance DISTANCE`: Transmitter–Receiver baseline distance in meters (default `2.5`).
- `--tx-pos TX_POS`: Transmitter baseline coordinate label.
- `--rx-pos RX_POS`: Receiver baseline coordinate label.
- `--orientation ORIENTATION`: Human subject orientation relative to LOS.
- `--event EVENT`: Explicit event ID (auto-generated if omitted).
- `--split {train,val,test}`: Split assignment (default `train`).
- `--confirm`: Bypasses interactive stdin prompt to confirm ground truth immediately.
- `--notes NOTES`: Observational notes.

### Exact Executed Command
```powershell
py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --room Laboratory --distance 2.5 --confirm
```
All options matched the parser arguments and parameter semantics without modification.

---

## 2. Hardware Verification & Live CSI Stream Status

Prior to recording, hardware connectivity and live physical streaming were verified using:
```powershell
py -3.11 scratch/run_collection_session.py --verify
```

### Observed Verification Telemetry
| Parameter | Observed Value | Specification / Status |
|---|---|---|
| **Port / Baud** | `COM5` @ `115200` baud | WCH CH343 USB-to-UART Bridge |
| **Diagnostic State** | `CSI_STREAM_ACTIVE` | Active streaming confirmed |
| **Connection Status** | `True` | Port opened and maintained |
| **Wi-Fi Mode & Channel** | Station (`sta`), Channel 7 ($2.442\text{ GHz}$) | Connected to AP `Tp link` (`98:ba:5f:ef:28:26`) |
| **Telemetry Protocol** | `raw_iq_stream` (Format A) | Matches running firmware output |
| **Observed Sampling Rate** | $35.0\text{ Hz}$ | Exceeds $\ge 30\text{ Hz}$ temporal Nyquist criterion |
| **Mean RSSI** | $-58.0\text{ dBm}$ | Clean indoor LOS signal |
| **Parse Errors** | `0` | $100\%$ valid frame decoding |
| **Raw CSI Dimensions** | `5` complex subcarriers | $10$ interleaved signed integers |

---

## 3. Physical Recording Execution Results

The 4.0-second physical walking session was executed with participant `Participant_03`:

### Session Telemetry
- **Session ID:** `phase16_real_walk_Participant_03_1792339078_1792339078`
- **Event ID:** `evt_walk_Participant_03_1792339078`
- **Participant ID:** `Participant_03`
- **Activity Label:** `walk` (Walking in LOS, `class_id: 11`)
- **Confirmation Status:** `confirmed` (`ground_truth_confirmed: True`)
- **Start Time (UTC):** `2026-10-18T15:57:58Z`
- **Actual Measured Duration:** $4.02\text{ seconds}$
- **Physical Frames Captured:** $143\text{ frames}$
- **Mean Empirical Sampling Rate:** $35.56\text{ Hz}$
- **Sequence Continuity:** Frames numbered sequence 5 to 147 (strictly monotonic, step $= 1$)
- **Packets Lost during trial:** $0$ ($0.0\%$ packet loss)
- **Mean RSSI:** $-57.60\text{ dBm}$
- **Room / Geometry:** `Laboratory`, Tx-Rx distance $2.5\text{ m}$, orientation `LOS_Facing_TxRx`
- **Saved Files:**
  - JSON: `data/real_csi_dataset/phase16_real_walk_Participant_03_1792339078_1792339078.json` ($143\text{ frames}$)
  - CSV: `data/real_csi_dataset/phase16_real_walk_Participant_03_1792339078_1792339078.csv` ($144\text{ rows}$)

---

## 4. Physical vs. Derived CSI Representation

The ESP32-S3 firmware emits 5 complex subcarriers per CSI packet. To maintain scientific integrity, the data pipeline strictly preserves original measurements:

### Data Architecture
1. **Raw Physical Measurements:**
   - Saved fields: `raw_amplitudes` (length 5), `raw_phases` (length 5), `raw_num_subcarriers: 5`.
   - Units: Euclidean magnitude $\sqrt{I^2 + Q^2}$ and radians $\text{atan2}(Q, I)$.
   - Source: Direct physical IQ measurements from ESP32-S3 Wi-Fi receiver hardware.
2. **Derived Model-Input Channels:**
   - Saved fields: `amplitudes` (length 56), `phases` (length 56), `num_subcarriers: 56`.
   - Transformation: 1D linear interpolation across subcarrier index to align with CSIFormer HT20 56-subcarrier input tensor $[50, 56]$.
   - Metadata attribution: Explicitly documented as `subcarrier_alignment_method: "linear_interpolation_to_56"`.
   - **Crucial scientific constraint:** These 56 channels represent derived model inputs, not 56 independent physical measurements. The raw 5-subcarrier measurements are never overwritten or discarded.

---

## 5. Dataset Validation & Integrity Checks

Validation was executed using `scratch/run_collection_session.py --validate` and verified via `DatasetIntegrityValidator`:

| Integrity Check | Target / Criterion | Result | Status |
|---|---|---|:---:|
| **File Existence** | JSON & CSV present on disk for all manifest sessions | All 24 files exist | **PASS** |
| **Manifest Consistency** | Declared packet counts match physical array lengths | Exact match across all sessions | **PASS** |
| **Numerical Integrity** | Finite timestamps, sequence IDs, RSSI, and amplitudes | Zero NaN, Inf, or null values | **PASS** |
| **Timestamp Monotonicity** | Strict positive time delta between consecutive frames | Strictly monotonic ($dt > 0$) | **PASS** |
| **Sequence Continuity** | Consecutive sequence increments without unaccounted drops | Zero packet loss ($loss = 0.0\%$) | **PASS** |
| **Subcarrier Dimensionality** | Exactly 56 aligned channels in `amplitudes` and 5 raw in `raw_amplitudes` | Confirmed on all 143 frames | **PASS** |
| **Metadata Attribution** | Participant, activity, room, distance, and confirmation status | Fully attributed and confirmed | **PASS** |
| **Index Verification** | Session indexed into `dataset_manifest.json` | Correctly indexed as session #24 | **PASS** |

---

## 6. Dataset Accounting & Progress Toward Targets

A strict audit was conducted comparing the dataset before and after the Phase 22 physical recording:

| Metric | Phase 21 Baseline | Phase 22 Actual | Net Change | Initial Target | Progress toward Target |
|---|---:|---:|---:|---:|---:|
| **Indexed Physical Sessions** | 23 | **24** | +1 session | 50 | 48.0% |
| **Total Physical Packets** | 3,212 | **3,355** | +143 packets | 10,000 | 33.6% |
| **Valid Non-Overlapping Windows ($T=50$)** | 49 | **51** | +2 windows | 150 | 34.0% |
| **Distinct Participants** | 2 | **3** | +1 (`Participant_03`) | 5 | 60.0% |
| **Rooms** | 1 | **1** (`Laboratory`) | 0 | 3 | 33.3% |
| **Held-Out Fall Events** | 2 | **2** | 0 | 12 | 16.7% |
| **Rejected Sessions** | 0 | **0** | 0 | 0 | Clean |

### Activity Window Breakdown ($T=50$ non-overlapping frames)
- `walk`: **11 windows** (increased from 9)
- `sit`: **10 windows**
- `push_pull`: **9 windows**
- `clap`: **8 windows**
- `fall`: **8 windows** (held-out / test split)
- `static`: **5 windows**
- **Total Valid Windows:** **51 windows**

### Unindexed Files on Disk Audit
- `phase14_p15_real_walk_t1_1792303844_1792303844.json`: Historical unindexed test session from Phase 14 (preserved for forensic reference).
- `dataset_manifest_p17_loso.json`: Historical Phase 17 LOSO manifest snapshot.
- All 24 active sessions in `dataset_manifest.json` have valid JSON and CSV files on disk.

---

## 7. Regression Test Suite Execution

Regression test execution was run across the test suites:

### 1. New Phase 22 Test Suite (`backend/tests/test_phase22.py`)
Command: `py -3.11 -m pytest backend/tests/test_phase22.py -v`
- `test_phase22_checkpoint_hash_invariance`: **PASSED**
- `test_phase22_saved_session_file_existence_and_integrity`: **PASSED**
- `test_phase22_physical_vs_derived_subcarrier_representation`: **PASSED**
- `test_phase22_manifest_indexing_and_packet_counts`: **PASSED**
- `test_phase22_dataset_integrity_validator_full_pass`: **PASSED**
- `test_phase22_participant_diversity_expansion`: **PASSED**
- `test_phase22_3way_loso_split_feasibility`: **PASSED**
- `test_phase22_csv_mirror_consistency`: **PASSED**
- **Total Phase 22 Suite:** **8 passed, 0 failed** in 0.74s.

### 2. Historical Test Suites (`test_phase14.py` through `test_phase21.py`)
Command: `py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py -v`
- **Result:** **71 passed, 10 failed**.
- **Root Cause of Failures:** All 10 failed assertions were hardcoded checks expecting exactly 23 sessions and exactly 2 participants (`assert res["total_sessions"] == 23` and `assert len(generator.participants) == 2`). Because Phase 22 successfully expanded the dataset to 24 sessions and 3 participants, these historical baseline equality checks failed.
- In strict adherence to Phase 22 guidelines ("Do not alter tests just to obtain a passing result"), the historical test files were left completely unchanged.

---

## 8. Checkpoint Bit-for-Bit Hash Invariance

Model weights were audited before and after execution to guarantee zero model evaluation, retraining, or parameter drift:

| Model Checkpoint | File Path | Invariant MD5 Hash | Measured Post-Phase 22 Hash | Status |
|---|---|---|---|:---:|
| **Production Model** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (INVARIANT)** |
| **Experimental Model** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (INVARIANT)** |

---

## 9. Dataset Expansion Plan

Following the first verified recording, a structured dataset expansion campaign should proceed systematically:

### Participant Diversity
1. Recruit and onboard 2 additional consenting participants (`Participant_04`, `Participant_05`) to achieve the initial target of 5 participants.
2. Maintain strict pseudonymized identifiers (`Participant_XX`).

### Activity Prioritization & Safety Protocol
1. **Priority 1 (Ordinary Activities):** Collect walking, sitting, standing/static, and clapping across multiple angles and baselines ($1.5\text{ m}, 2.5\text{ m}, 3.5\text{ m}$).
2. **Priority 2 (Padded Falls):**
   - Strictly require certified 4-inch shock-absorbing crash mats.
   - Require a dedicated spotter.
   - Restrict fall trials to trained participants executing breakfall techniques.
   - Rejection gate: Any fall trial without certified mats or spotter must be postponed.

### Multi-Room Expansion
1. Expand from `Laboratory` to `Office` and `Bedroom` environments to evaluate cross-environment domain transfer.
2. Document physical room geometry ($L \times W \times H$) in session metadata.

---

## 10. Final Decision & Readiness Ruling

| Decision Axis | Readiness Status | Evidence Rationale |
|---|:---:|---|
| **Physical Acquisition Pipeline** | **GO** | End-to-end hardware pipeline (ESP32-S3 $\to$ serial $\to$ parser $\to$ validator $\to$ manifest) verified and operational. First real session saved, inspected, validated, and indexed. |
| **Model Evaluation & Comparison** | **NO-GO** | Dataset currently stands at 24 sessions (target: 50), 3,355 packets (target: 10,000), 51 windows (target: 150), and 2 held-out fall events (target: 12). Participant-independent test power is insufficient for definitive statistical benchmarking. |

Physical data collection may proceed. Model evaluation remains strictly blocked until all data-readiness criteria are satisfied.
