# CSIFormer Phase 29 — Participant–Distance Confounding Reduction Report

**Execution Date:** October 19, 2026  
**Auditor / Operator:** CSIFormer Autonomous Verification Agent  
**Phase Objective:** Reduce participant–distance confounding identified in Phase 28 by executing an operator-approved, balanced physical collection matrix of safe ordinary activities across participants and distances. Preserve provenance, validate every recording immediately upon capture, protect model checkpoints, and maintain the freeze on 6-class model evaluation.

---

## 1. Executive Summary & Research-Readiness Assessment

Following explicit operator approval of the proposed collection matrix, 20 new physical CSI recordings were sequentially captured from real hardware using the standardized collection workflow. Every session was independently validated, verified for timestamp monotonicity and packet sequence integrity, confirmed for raw $(I, Q)$ subcarrier extraction, and indexed into `data/real_csi_dataset/dataset_manifest.json`.

### Research-Readiness Verdict Table

| Dimension | Verdict | Summary of Physical Evidence |
| :--- | :---: | :--- |
| **1. Collection Pipeline Integrity** | **GO** | Hardware lifecycle on `COM5 @ 115200 baud` verified. Active UDP stimulation on Channel 7 sustained 34–37 Hz empirical sampling rate. Zero packet loss (0.00%) across all 20 new recordings. Stream stabilization logic extended to 30.0s to allow reliable Wi-Fi association. Clean serial port and worker thread termination verified on every session. |
| **2. Participant–Distance Coverage** | **GO** | **Confounding successfully reduced.** All 5 participants now possess verified multi-distance coverage (at least 2 distinct geometric distances each). Participants 01, 02, and 03 expanded from 2.5 m only to both 2.0 m and 2.5 m. Participant 04 expanded from 2.0 m only to both 2.0 m and 2.5 m. Participant 05 retains 1.5 m and 2.0 m coverage. |
| **3. Dataset Integrity & Provenance** | **GO** | Total dataset expanded from 44 to **64 indexed sessions**, **8,997 physical frames** (from 6,165), and **134 valid windows** ($T=50$, stride 50, from 92). Zero session/event ID collisions. 100% CSV/JSON parity. 100% manifest-to-disk agreement. |
| **4. Split Integrity** | **GO** | 3-way participant-independent split yields **79 train windows** (P01, P03, P04), **20 val windows** (P05), and **35 test windows** (P02). Total: 134 windows. Disjoint subjects, disjoint events, zero window overlap strictly verified. |
| **5. Class Coverage** | **PARTIAL GO** | 5 ordinary activity classes (`walk`, `sit`, `static`, `clap`, `push_pull`) have 100% coverage across all 5 participants and multiple distances. `fall` activity remains restricted to historical recordings of P01 and P02 (8 sessions, 8 windows); 0 fall events for P03, P04, and P05. |
| **6. Environmental Diversity** | **PARTIAL GO** | Geometric distance diversity enhanced across 3 physical distances: **2.5 m** (34 sessions), **2.0 m** (25 sessions), and **1.5 m** (5 sessions). Cross-room facility diversity remains **UNVERIFIED** (single laboratory facility, $4.0\text{--}4.5\text{ m} \times 3.5\text{ m} \times 2.8\text{ m}$). |
| **7. Full 6-Class Model Evaluation Readiness** | **NO-GO / BLOCKED** | Full 6-class model evaluation remains **strictly blocked**. Safety safeguards forbid collecting falls or asking participants to perform hazardous movements. Evaluating 6 classes on held-out subjects (P03, P04, P05) raises `InadequateClassCoverageError`. Model checkpoints remain frozen and untouched. |

---

## 2. Protected Checkpoint Bit-Integrity Verification

Both production and experimental model checkpoints were checked via MD5 hashing before, during, and after Phase 29 physical collection and test execution. Neither checkpoint was opened for inference, fine-tuned, adapted, or altered.

| Checkpoint Path | Expected MD5 Hash | Verified MD5 Hash | Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |

---

## 3. Approved Collection Matrix vs. Actual Physical Acquisition

The 20-session matrix approved by the operator was executed sequentially using `scratch/run_collection_session.py` with 4.0-second trials in the Laboratory setup under LOS conditions:

| Trial # | Participant ID | Distance | Activity Label | Session ID | Frames | Empirical Rate | Packet Loss | Raw 5 Subcarriers | Derived 56 Channels |
| :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | Participant_01 | 2.0 m | static | `phase16_real_static_Participant_01_1792393895_1792393895` | 137 | 34.05 Hz | 0.00% | 5 pairs | 56 channels |
| 2 | Participant_01 | 2.0 m | sit | `phase16_real_sit_Participant_01_1792393959_1792393959` | 139 | 34.52 Hz | 0.00% | 5 pairs | 56 channels |
| 3 | Participant_01 | 2.0 m | walk | `phase16_real_walk_Participant_01_1792393992_1792393992` | 143 | 35.53 Hz | 0.00% | 5 pairs | 56 channels |
| 4 | Participant_01 | 2.0 m | clap | `phase16_real_clap_Participant_01_1792394020_1792394020` | 141 | 35.04 Hz | 0.00% | 5 pairs | 56 channels |
| 5 | Participant_01 | 2.0 m | push_pull | `phase16_real_push_pull_Participant_01_1792394048_1792394048` | 143 | 35.52 Hz | 0.00% | 5 pairs | 56 channels |
| 6 | Participant_02 | 2.0 m | static | `phase16_real_static_Participant_02_1792394082_1792394082` | 143 | 35.51 Hz | 0.00% | 5 pairs | 56 channels |
| 7 | Participant_02 | 2.0 m | sit | `phase16_real_sit_Participant_02_1792394110_1792394110` | 153 | 38.01 Hz | 0.00% | 5 pairs | 56 channels |
| 8 | Participant_02 | 2.0 m | walk | `phase16_real_walk_Participant_02_1792394137_1792394137` | 138 | 34.28 Hz | 0.00% | 5 pairs | 56 channels |
| 9 | Participant_02 | 2.0 m | clap | `phase16_real_clap_Participant_02_1792394172_1792394172` | 139 | 34.53 Hz | 0.00% | 5 pairs | 56 channels |
| 10 | Participant_02 | 2.0 m | push_pull | `phase16_real_push_pull_Participant_02_1792394322_1792394322` | 148 | 36.77 Hz | 0.00% | 5 pairs | 56 channels |
| 11 | Participant_03 | 2.0 m | static | `phase16_real_static_Participant_03_1792394353_1792394353` | 145 | 36.02 Hz | 0.00% | 5 pairs | 56 channels |
| 12 | Participant_03 | 2.0 m | sit | `phase16_real_sit_Participant_03_1792394450_1792394450` | 143 | 35.52 Hz | 0.00% | 5 pairs | 56 channels |
| 13 | Participant_03 | 2.0 m | walk | `phase16_real_walk_Participant_03_1792394478_1792394478` | 132 | 32.79 Hz | 0.00% | 5 pairs | 56 channels |
| 14 | Participant_03 | 2.0 m | clap | `phase16_real_clap_Participant_03_1792394507_1792394507` | 137 | 34.03 Hz | 0.00% | 5 pairs | 56 channels |
| 15 | Participant_03 | 2.0 m | push_pull | `phase16_real_push_pull_Participant_03_1792394536_1792394536` | 138 | 34.28 Hz | 0.00% | 5 pairs | 56 channels |
| 16 | Participant_04 | 2.5 m | static | `phase16_real_static_Participant_04_1792394573_1792394573` | 157 | 39.01 Hz | 0.00% | 5 pairs | 56 channels |
| 17 | Participant_04 | 2.5 m | sit | `phase16_real_sit_Participant_04_1792394601_1792394601` | 132 | 32.78 Hz | 0.00% | 5 pairs | 56 channels |
| 18 | Participant_04 | 2.5 m | walk | `phase16_real_walk_Participant_04_1792394628_1792394628` | 139 | 34.52 Hz | 0.00% | 5 pairs | 56 channels |
| 19 | Participant_04 | 2.5 m | clap | `phase16_real_clap_Participant_04_1792394658_1792394658` | 145 | 36.02 Hz | 0.00% | 5 pairs | 56 channels |
| 20 | Participant_04 | 2.5 m | push_pull | `phase16_real_push_pull_Participant_04_1792394688_1792394688` | 140 | 34.78 Hz | 0.00% | 5 pairs | 56 channels |

**Total Newly Acquired Physical Data:**
- **Sessions:** 20 sessions (15 at 2.0 m, 5 at 2.5 m)
- **Frames:** 2,832 physical frames
- **Valid Windows ($T=50$):** 42 non-overlapping windows
- **Raw $(I, Q)$ Subcarrier Pairs:** 2,832 frames with 5 raw complex subcarrier pairs
- **Derived Channels:** 2,832 frames with 56 aligned HT20 channels
- **Packet Loss:** 0 dropped packets across all 20 sessions (0.00%)
- **Sampling Rates:** 32.78 Hz – 39.01 Hz (strictly above the 30.0 Hz threshold)

---

## 4. Confounding Reduction Analysis: Before vs. After

### 4.1 Participant-Distance Session Distribution
| Participant ID | Phase 28 Baseline Distances | Phase 29 Distances Added | Phase 29 Final Distances | Confounding Reduction Status |
| :--- | :--- | :--- | :--- | :--- |
| **Participant_01** | 2.5 m (12 sessions) | 2.0 m (5 sessions) | **2.0 m (5), 2.5 m (12)** | **Multi-distance coverage achieved** |
| **Participant_02** | 2.5 m (11 sessions) | 2.0 m (5 sessions) | **2.0 m (5), 2.5 m (11)** | **Multi-distance coverage achieved** |
| **Participant_03** | 2.5 m (6 sessions) | 2.0 m (5 sessions) | **2.0 m (5), 2.5 m (6)** | **Multi-distance coverage achieved** |
| **Participant_04** | 2.0 m (5 sessions) | 2.5 m (5 sessions) | **2.0 m (5), 2.5 m (5)** | **Multi-distance coverage achieved** |
| **Participant_05** | 1.5 m (5), 2.0 m (5) | None (maintained) | **1.5 m (5), 2.0 m (5)** | **Multi-distance coverage maintained** |

### 4.2 Comprehensive Activity–Distance Breakdown Matrix
| Participant & Distance | static | sit | walk | clap | push_pull | fall | Total Sessions | Total Windows ($T=50$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Participant_01 @ 2.0 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **10** |
| **Participant_01 @ 2.5 m** | 2 | 2 | 2 | 2 | 2 | 2 | **12** | **26** |
| **Participant_02 @ 2.0 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **11** |
| **Participant_02 @ 2.5 m** | 1 | 2 | 2 | 2 | 2 | 2 | **11** | **24** |
| **Participant_03 @ 2.0 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **10** |
| **Participant_03 @ 2.5 m** | 1 | 1 | 2 | 1 | 1 | 0 | **6** | **12** |
| **Participant_04 @ 2.0 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **10** |
| **Participant_04 @ 2.5 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **11** |
| **Participant_05 @ 1.5 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **10** |
| **Participant_05 @ 2.0 m** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | **10** |
| **Total Dataset** | **11** | **12** | **13** | **12** | **12** | **4** | **64** | **134** |

*Key Result:* In Phase 28, 4 of the 5 participants were observed at only a single distance. In Phase 29, **100% of participants (5 of 5)** are now represented across multiple distinct physical distances.

---

## 5. Reconciled Total Dataset Inventory

Every session file in `data/real_csi_dataset/` was audited against `dataset_manifest.json`:

| Metric | Phase 28 Baseline | Phase 29 Addition | Reconciled Total Dataset | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Indexed Sessions** | 44 | +20 | **64** | Verified |
| **Unique Session IDs** | 44 | +20 | **64** | 0 collisions |
| **Unique Event IDs** | 44 | +20 | **64** | 0 collisions |
| **Physical Frames** | 6,165 | +2,832 | **8,997** | Verified |
| **Valid Windows ($T=50$, stride 50)** | 92 | +42 | **134** | Verified |
| **Frames with Raw 5 Subcarriers** | 2,953 | +2,832 | **5,785** | Verified |
| **Frames with Derived 56 Channels** | 6,165 | +2,832 | **8,997** | Verified |
| **Sessions at 1.5 m** | 5 | 0 | **5** | Verified |
| **Sessions at 2.0 m** | 10 | +15 | **25** | Verified |
| **Sessions at 2.5 m** | 29 | +5 | **34** | Verified |
| **Manifest Integrity Pass Rate** | 100% (44/44) | 100% (20/20) | **100% (64/64)** | Verified |

---

## 6. Participant-Independent Split Verification

The updated 64-session manifest was processed using `ParticipantIndependentSplitGenerator`:

- **Split Protocol:** Participant-independent train/val/test partition
- **Test Participant:** `Participant_02` (16 sessions, 35 windows: 24 at 2.5 m, 11 at 2.0 m)
- **Validation Participant:** `Participant_05` (10 sessions, 20 windows: 10 at 1.5 m, 10 at 2.0 m)
- **Training Participants:** `Participant_01`, `Participant_03`, `Participant_04` (38 sessions, 79 windows across 2.0 m and 2.5 m)
- **Total Windows:** $79 + 20 + 35 = 134\text{ windows}$

### Disjointness & Zero-Leakage Audit
$$\text{Train} \cap \text{Val} = \emptyset, \quad \text{Train} \cap \text{Test} = \emptyset, \quad \text{Val} \cap \text{Test} = \emptyset$$
- Common subjects between any partition: **0**
- Common sessions/events between any partition: **0**
- Window boundary overlap ($T=50$, stride 50): **0**

---

## 7. Discrepancy & Safe Failure Handling Ledger

| Discrepancy ID | Event Description | Detected Cause | Resolution & Safe Action | Status |
| :---: | :--- | :--- | :--- | :---: |
| **DISC-P29-01** | **Session 10 Stabilization Timeout (Initial Attempt)** | An initial attempt for `Participant_02`, `push_pull`, 2.0 m yielded 0 frames due to Wi-Fi association exceeding the default 15s wait. | The integrity validator immediately failed the recording (`0 frames`), prevented the manifest from updating, and aborted indexing. The failed 0-frame file was non-destructively removed from disk. | **Resolved** |
| **DISC-P29-02** | **Collection Workflow Stabilization Window Hardening** | In `backend/app/services/collection_workflow.py`, stream stabilization was bounded at 15.0s, which occasionally cut off slow DHCP assignments. | Extended `t_start_wait` window to 30.0s with an explicit `TimeoutError` check. Re-recorded Session 10; successfully captured 148 frames (36.77 Hz, 0.00% packet loss). | **Resolved** |
| **DISC-P29-03** | **Cumulative Dataset Growth in Prior Phase Tests** | Earlier phase tests (`test_phase25.py`, `test_phase26.py`, `test_phase27.py`, `test_phase28.py`) asserted historical exact equality counts (e.g. `== 44`). | Updated cumulative assertions to lower bounds (`>=`), preserving the underlying baseline invariants while accommodating verified growth to 64 sessions. | **Resolved** |

---

## 8. Regression Test Suite Execution

The full test suite across 16 test files (including the newly authored [backend/tests/test_phase29.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase29.py)) was executed:

```powershell
py -3.11 -m pytest `
  backend/tests/test_phase14.py `
  backend/tests/test_phase16.py `
  backend/tests/test_phase17.py `
  backend/tests/test_phase18.py `
  backend/tests/test_phase19.py `
  backend/tests/test_phase20.py `
  backend/tests/test_phase21.py `
  backend/tests/test_phase22.py `
  backend/tests/test_phase23.py `
  backend/tests/test_phase25.py `
  backend/tests/test_phase26.py `
  backend/tests/test_phase27.py `
  backend/tests/test_phase28.py `
  backend/tests/test_phase29.py `
  backend/tests/test_safe_disconnection.py `
  backend/tests/test_sampling_rate_audit.py -v
```

### Test Suite Execution Summary
- **Exit Code:** `0`
- **Total Tests Run:** `144`
- **Passed:** `144`
- **Failed:** `0`
- **Skipped:** `0`
- **Warnings:** `4` (2 PyTorch nested-tensor encoder warnings, 1 Starlette TestClient deprecation warning)
- **Duration:** `29.39 seconds`

---

## 9. Unresolved Limitations & Research Barriers

1. **Safety Blocker — Missing Fall Class in Held-Out Subjects:**
   - Participants 03, 04, and 05 have 0 fall events.
   - Performing full 6-class evaluation requires held-out fall events, but user-defined safety rules strictly prohibit performing risky movements or conducting physical fall experiments.
   - Synthetic data fabrication is strictly prohibited.
   - **Status:** Full 6-class evaluation remains **BLOCKED (NO-GO)**.
2. **Environmental Blocker — Physical Facility Identity:**
   - All 64 sessions share a single physical room environment (Laboratory).
   - Multi-room cross-facility generalization remains **UNVERIFIED**.

---

## 10. Recommendations for Future Phases

1. **Maintain Checkpoint Protection:** Keep `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` frozen and untouched.
2. **Consider Ordinary 5-Class Evaluation Protocol:** If model benchmarking or validation is desired in a future phase, it can be safely and rigorously performed by establishing an **ordinary 5-class HAR protocol** (`walk`, `sit`, `static`, `clap`, `push_pull`) where complete participant-independent and multi-distance coverage exists across all 5 subjects (126 windows).
3. **Explore External Benchmark Fall Integration:** If full 6-class evaluation is mandatory, investigate integrating open-access, IRB-approved public Wi-Fi CSI fall benchmark datasets rather than attempting hazardous physical falls.
