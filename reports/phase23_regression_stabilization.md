# CSIFormer — Phase 23: Regression Stabilization & Controlled Physical Dataset Expansion Report

## Executive Summary

Phase 23 stabilized the regression test harness following the verified physical expansion in Phase 22, performed an in-depth identity, timing, and schema audit of the newly recorded `Participant_03` physical walking session, audited participant-independent (LOSO) split safeguards, and established an operator-guided protocol for the upcoming physical data collection campaign.

In accordance with Phase 23 instructions:
- **No model training, fine-tuning, benchmarking, or evaluation was performed.**
- **No checkpoint files were modified.** Both production (`models/csiformer_phase13_best.pth`) and experimental (`models/csiformer_phase15_adapted.pth`) MD5 hashes remain bit-for-bit invariant.
- **No synthetic data was generated or substituted.**
- All 10 historical regression failures were investigated individually and surgically repaired to reflect their true contracts, resulting in **94 passed, 0 failed** across all test suites (Phases 14–23).
- Dual Decision Ruling: Physical data acquisition pipeline is **GO**; Model evaluation remains strictly **NO-GO**.

---

## 1. Verified Dataset Baseline & Disk Reconciliation

All figures have been independently verified against the physical disk files and `data/real_csi_dataset/dataset_manifest.json`:

| Metric | Phase 22 Audit | Phase 23 Verified Baseline | Initial Milestone Target | Progress |
|---|---:|---:|---:|---:|
| **Indexed Physical Sessions** | 24 | **24** | 50 | 48.0% |
| **Total Physical Packets** | 3,355 | **3,355** | 10,000 | 33.6% |
| **Valid Non-Overlapping Windows ($T=50$)** | 51 | **51** | 150 | 34.0% |
| **Distinct Participants** | 3 | **3** (`Participant_01, 02, 03`) | 5 | 60.0% |
| **Distinct Rooms** | 1 | **1** (`Laboratory` / `Laboratory_Room1`) | 3 | 33.3% |
| **Distinct Activities** | 6 | **6** (`walk, sit, push_pull, clap, fall, static`) | 6 | 100.0% |
| **Distinct Events** | 24 | **24** | 50 | 48.0% |
| **Held-Out Fall Events** | 2 | **2** | 12 | 16.7% |

### Activity Window Distribution ($T=50$ non-overlapping frames)
- `walk`: **11 windows**
- `sit`: **10 windows**
- `push_pull`: **9 windows**
- `clap`: **8 windows**
- `fall`: **8 windows**
- `static`: **5 windows**
- **Total Valid Windows:** **51 windows**

### Disk File Reconciliation
- JSON files on disk: 26 (24 indexed sessions + `phase14_p15_real_walk_t1_1792303844_1792303844.json` unindexed trial + `dataset_manifest_p17_loso.json` snapshot).
- CSV files on disk: 25 (24 indexed sessions + `phase14_p15_real_walk_t1_1792303844_1792303844.csv`).
- Active indexed file match: $100\%$ ($0$ missing files, $0$ corrupt files).

---

## 2. In-Depth Audit of the Participant_03 Physical Session

The newly recorded session [phase16_real_walk_Participant_03_1792339078_1792339078.json](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/phase16_real_walk_Participant_03_1792339078_1792339078.json) and its CSV mirror were independently audited:

### 1. Identifier Uniqueness & Correspondence
- **Session ID:** `phase16_real_walk_Participant_03_1792339078_1792339078` is unique across all historical sessions.
- **Event ID:** `evt_walk_Participant_03_1792339078` is uniquely attributed.
- **CSV Correspondence:** [phase16_real_walk_Participant_03_1792339078_1792339078.csv](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/phase16_real_walk_Participant_03_1792339078_1792339078.csv) has 144 rows (1 header + 143 data rows). Exact timestamp, sequence number, RSSI, and subcarrier amplitude equality with the JSON frames was verified with zero numeric discrepancy.

### 2. Forensic Analysis of the Filename Prefix and Double Timestamp
- **Prefix `phase16_`:** Originates from `RealCSICollector.start_session_recording()` in `backend/app/services/real_csi_collector.py` (line 568), which was authored during Phase 16 multi-room development (similar to historical sessions having `phase14_`). This is a legacy code prefix, not a data corruption.
- **Double Timestamp `_1792339078_1792339078`:** 
  - `CollectionWorkflowManager.start_session()` created `session_name = f"real_{clean_label}_{clean_pid}_{now_ts}"` (where `now_ts = 1792339078`).
  - `RealCSICollector.start_session_recording()` then generated `self.current_session_id = f"phase16_{clean_name}_{int(time.time())}"`.
  - Because both functions were invoked in the same second, `int(time.time())` evaluated to `1792339078` both times.
  - **Verdict:** The identical numbers represent two evaluations of the Unix epoch second at session initialization; they do not represent start/end times and do not conceal a timestamp bug.

### 3. Timestamp and Rate Internal Consistency
- First physical frame timestamp: `1792339078.4786937`
- Last physical frame timestamp: `1792339082.4559603`
- Elapsed physical duration: $3.977\text{ seconds}$
- Wall-clock recorded duration in metadata: $4.02\text{ seconds}$ ($\Delta = 0.043\text{ s}$)
- Captured frames: $143\text{ frames}$
- Empirical frame rate: $143 / 3.977 = 35.95\text{ Hz}$ (metadata declared: $35.56\text{ Hz}$)
- Timestamps: Strictly monotonic ($dt > 0$ on all consecutive frame pairs)
- Sequences: Sequence IDs run continuously from 5 to 147 ($step = 1$, $0$ packet loss).
- Physical CSI: Raw measurements strictly preserve 5 complex subcarriers (`raw_num_subcarriers: 5`), while model inputs derive 56 channels via linear interpolation.

---

## 3. Investigation and Resolution of All 10 Historical Test Failures

The regression test run following Phase 22 produced 71 passes and 10 failures. Every failure was inspected individually:

| # | Test Identifier | Category | Root Cause | Surgical Remediation |
|---|---|---|---|---|
| **1** | `test_phase16.py::test_dataset_manifest_integrity` | Live Dataset Assumption | Hardcoded `assert len(sessions) == 23` | Changed assertion to invariant: `assert len(sessions) >= 23`. Retained strict per-session file existence and packet matching. |
| **2** | `test_phase16.py::test_sliding_window_non_overlap` | Live Dataset Assumption | Hardcoded `assert len(windows) == 49` and `assert len(hashes) == 49` | Changed assertion to invariant: `assert len(windows) >= 49` and `assert len(hashes) == len(windows)` (strictly verifying zero duplicate windows across the expanding dataset). |
| **3** | `test_phase17.py::test_insufficient_participants_error_on_3way_split` | Missing Deterministic Fixture | Pointed to live `MANIFEST_PATH` to test 2-participant error boundary. Failed when dataset gained Participant_03. | Updated test to use `tmp_path` fixture with an isolated 2-participant manifest, ensuring deterministic verification of `InsufficientParticipantsError`. |
| **4** | `test_phase18.py::test_insufficient_participants_error` | Missing Deterministic Fixture | Pointed to live `MANIFEST_PATH` to test 2-participant error boundary. | Updated test to use `tmp_path` fixture with an isolated 2-participant manifest. |
| **5** | `test_phase19.py::test_session_validator_clean_manifest` | Live Dataset Assumption | Hardcoded `total_sessions == 23`, `total_packets == 3212`, `total_windows == 49`, etc. | Updated assertions to verify valid manifest status and monotonic invariants: `total_sessions >= 23`, `total_packets >= 3212`, `total_windows >= 49`, with baseline participants present. |
| **6** | `test_phase19.py::test_insufficient_participants_3way_error_phase19` | Missing Deterministic Fixture | Pointed to live `MANIFEST_PATH` to test 2-participant error boundary. | Updated test to use `tmp_path` fixture with an isolated 2-participant manifest. |
| **7** | `test_phase20.py::test_phase20_dataset_manifest_integrity` | Live Dataset Assumption | Hardcoded exact Phase 20 counts (23 sessions, 3212 packets, 49 windows). | Updated assertions to invariants: `total_sessions >= 23`, `total_packets >= 3212`, `total_windows >= 49`, and verified all baseline activity window minimums. |
| **8** | `test_phase20.py::test_phase20_loso_split_metrics` | Missing Deterministic Fixture | Pointed to live `MANIFEST_PATH` to verify exact 2-participant split counts (25 train, 24 test). When Participant_03 was added to train, counts shifted. | Repointed generator to `dataset_manifest_p17_loso.json` (the preserved 23-session manifest snapshot) to test the exact Phase 20 split contract deterministically. |
| **9** | `test_phase20.py::test_phase20_insufficient_participants_barrier` | Missing Deterministic Fixture | Pointed to live `MANIFEST_PATH` to test 2-participant error boundary. | Updated test to use `tmp_path` fixture with an isolated 2-participant manifest. |
| **10** | `test_phase21.py::test_phase21_dataset_baseline_preservation` | Live Dataset Assumption | Asserted `total_sessions == 23` rather than verifying that historical sessions are preserved within the expanded dataset. | Updated assertions to invariant: `total_sessions >= 23`, `total_packets >= 3212`, and `{"Participant_01", "Participant_02"}.issubset(distinct_participants)`. |

**Verdict:** Zero failures represented broken production code. All 10 failures were caused either by coupling unit error-boundary tests to the live manifest instead of isolated fixtures, or by asserting strict equality on dataset size rather than preservation invariants.

---

## 4. Full Regression Test Results

Execution of the entire regression suite across Phases 14 through 23:
```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py backend/tests/test_phase22.py backend/tests/test_phase23.py -v
```

### Execution Summary
- **Phase 14:** 11 passed
- **Phase 16:** 10 passed
- **Phase 17:** 12 passed
- **Phase 18:** 12 passed
- **Phase 19:** 10 passed
- **Phase 20:** 10 passed
- **Phase 21:** 17 passed
- **Phase 22:** 8 passed
- **Phase 23:** 5 passed
- **Total:** **94 passed, 0 failed, 4 warnings in 10.40s**

---

## 5. Participant-Independent Split Safeguards Audit

The participant-independent split generator was reviewed to verify partition leakage prevention:

1. **Participant Separation:**
   - Evaluated 3-way partition: Train (`Participant_01`), Val (`Participant_03`), Test (`Participant_02`).
   - Verified that $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$.
2. **Event & Window Grouping:**
   - All windows within each session and event are strictly assigned to the participant's assigned partition.
   - Zero event overlap across splits:
     `train_events.isdisjoint(test_events) == True`
     `train_events.isdisjoint(val_events) == True`
     `val_events.isdisjoint(test_events) == True`
3. **Non-Overlapping Windows:**
   - Window extraction enforces $T=50$ non-overlapping stride ($packet\_count // 50$). No sliding overlapping windows are used across splits.
4. **Feasibility vs. Statistical Readiness:**
   - Structurally, $N=3$ participants enables a 3-way split.
   - Statistically, `Participant_03` currently has only 1 session (activity: `walk`).
   - If `Participant_03` is assigned as the held-out test participant, `InadequateClassCoverageError` is raised immediately because the test partition contains 0 falls and lacks 5 activity classes.
   - **Conclusion:** A 3-way split is structurally feasible, but model evaluation remains invalid until all participants have balanced activity coverage.

---

## 6. Checkpoint Bit-for-Bit Hash Invariance

Cryptographic MD5 verification was performed before and after Phase 23 test repairs:

| Checkpoint Identifier | File Location | Expected MD5 Hash | Measured MD5 Hash | Status |
|---|---|---|---|:---:|
| **Production Model** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (INVARIANT)** |
| **Experimental Model** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (INVARIANT)** |

---

## 7. Next Physical Data Collection Campaign Plan

With the pipeline stabilized and tests passing, the collection campaign is prepared for controlled physical expansion:

### A. Priority 1: Balance Ordinary Activities for Participant_03
To achieve class balance for `Participant_03`, collect the following ordinary trials under operator supervision:
1. `sit` (Sitting transition): 4 trials @ 4.0s (1.5m, 2.5m, 3.5m Tx-Rx distances)
2. `static` (Standing / background): 3 trials @ 4.0s
3. `clap` (Two-hand clapping): 4 trials @ 4.0s
4. `push_pull` (Arm push and pull): 4 trials @ 4.0s
5. `walk` (Walking in LOS): 3 additional trials varying approach angle (0°, 45°, 90°)

### B. Priority 2: Onboard Consenting Participant_04 and Participant_05
- Goal: Expand participant diversity to $N=5$ (achieving the initial 5-participant milestone).
- Collect standard 5-activity baseline per participant before considering any fall trials.

### C. Standardized Operator Execution Protocol
For each physical session:
1. **Pre-flight Stream Check:** Run `py -3.11 scratch/run_collection_session.py --verify` to ensure `CSI_STREAM_ACTIVE` and $\ge 30\text{ Hz}$.
2. **Execute Recording:**
   ```powershell
   py -3.11 scratch/run_collection_session.py --activity <activity> --participant <ID> --duration 4.0 --room Laboratory --distance <dist>
   ```
3. **Operator Ground-Truth Gate:** Inspect the trial and confirm ground-truth activity (or reject if trial was flawed).
4. **Validation Check:** Run `py -3.11 scratch/run_collection_session.py --validate` after each collection batch.

### D. Safety Protocols for High-Risk Fall Trials
- Fall trials remain strictly postponed until ordinary activities across participants are complete.
- When scheduled, fall trials mandate:
  1. A certified minimum 4-inch (10 cm) shock-absorbing crash mat.
  2. A dedicated competent spotter.
  3. Controlled breakfall execution.
  4. Explicit operator confirmation gate.

---

## 8. Unresolved Issues & Explicit Limitations

1. **Subcarrier Dimensionality:** The ESP32-S3 firmware emits 5 complex subcarriers over UART to prevent FIFO overflow at 115200 baud. The 56 channels used by the model are linearly interpolated inputs.
2. **Room Diversity:** All 24 current sessions are gathered in `Laboratory`. Office and Bedroom environments remain to be collected.
3. **Statistical Power for Cross-Subject Testing:** At 51 valid windows across 3 participants (with Participant_03 only having 2 walk windows), statistical power remains insufficient for meaningful model comparison.

---

## 9. Readiness Decision

| Decision Axis | Readiness Status | Evidence Rationale |
|---|:---:|---|
| **Physical Acquisition & Regression Harness** | **GO** | End-to-end hardware pipeline verified, test suite 100% green (94 passed), session audit passed, dataset accounting validated. Physical data collection may proceed. |
| **Model Evaluation & Comparison** | **NO-GO** | Dataset currently stands at 24/50 sessions, 3,355/10,000 packets, 51/150 windows, and 2/12 held-out falls. Model evaluation remains strictly blocked until all data-readiness criteria are demonstrably satisfied. |
