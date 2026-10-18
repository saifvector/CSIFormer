# CSIFormer Phase 17 — Master Validation Report: Real-World CSI Data Collection Campaign and Participant-Independent Evaluation Protocol

## Executive Summary

**CSIFormer Phase 17** establishes a reproducible, participant-independent validation protocol and executes an empirical audit of the real-world ESP32-S3 Channel State Information (CSI) dataset. Prior phases (Phase 15 and Phase 16) observed significant performance degradation when testing on physical hardware and uncovered subtle participant leakage in historical evaluations where identical subjects spanned training, validation, and test splits.

In accordance with the Phase 17 mandate, **no model retraining or weight modifications were performed**. Both reference model checkpoints remain bit-for-bit intact:
- **Production Checkpoint:** `models/csiformer_phase13_best.pth` (MD5: `383b4d98c08f8970b0443738f170ec01`)
- **Experimental Checkpoint:** `models/csiformer_phase15_adapted.pth` (MD5: `ab3d97a04d78edf75d807178772bc828`)

Phase 17 prioritized data collection infrastructure, measurement integrity, and validation readiness over premature fine-tuning. Key accomplishments and findings include:
1. **Audited Current Collection Workflow:** Discovered that 100% of legacy recordings (23/23 sessions) discarded raw 52-subcarrier measurements, preserving only model-interpolated arrays. Built a compliant pipeline preserving both raw and aligned subcarriers.
2. **Standardized Reproducible Collection Engine:** Built [`backend/app/services/collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) with active UDP traffic stimulation (`192.168.0.232:5555`) sustaining 35.6 Hz packet rates, sequence continuity monitoring, and post-trial confirmation.
3. **Rigorous Fall Safety Protocol:** Formulated [`reports/phase17_collection_protocol.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_collection_protocol.md) mandating certified 4-inch shock-absorbing crash mats, dedicated spotters, controlled descent, and zero hard-floor impacts.
4. **Mathematical LOSO Split Generator:** Built [`backend/app/services/split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py). Proved that a 3-way participant-independent split (Train/Val/Test) is mathematically impossible on the current dataset due to the $N=2$ participant barrier (`Participant_01` and `Participant_02`), and implemented an explicit `InsufficientParticipantsError` to prevent silent leakage.
5. **Quality & Milestone Assessment:** Documented that while signal fidelity is high (35.6 Hz, $-58.2$ dBm RSSI, $1.2\%$ packet loss), the held-out test participant provides only **4 fall windows**, reaching only **11.4%** of the Phase 16 pilot milestone of $\ge 35$ fall test windows.
6. **Automated Test Suite:** Created [`backend/tests/test_phase17.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase17.py) (12 tests) and achieved a 100% pass rate across the full 32-test regression suite (Phase 14, Phase 16, and Phase 17).

---

## 1. Stage-by-Stage Verification & Deliverables Summary

| Phase 17 Stage | Core Deliverable | Primary Outcome / Finding |
| :--- | :--- | :--- |
| **Stage 1: Collection Audit** | [`reports/phase17_collection_audit.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_collection_audit.md) | Verified 23 indexed sessions + 1 unindexed file (`phase14_p15_real_walk_t1_1792303844_1792303844.json`). Proved 0/23 legacy files saved raw subcarriers. |
| **Stage 2: Collection Workflow** | [`backend/app/services/collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py)<br>[`scratch/run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py) | Created unified workflow with UDP probe generator, serial health checks on `COM5`, raw subcarrier preservation, and confirmation gates. |
| **Stage 3: Coverage & Protocol** | [`reports/phase17_collection_protocol.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_collection_protocol.md) | Enforced standard 8-step protocol, pseudonymized IDs, and strict 4-inch mat fall safety mandates. |
| **Stage 4: LOSO Split Validation** | [`backend/app/services/split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py)<br>[`reports/phase17_split_validation.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_split_validation.md) | Implemented zero-leakage generator; proved $N=2$ barrier; generated clean 2-way LOSO split (`dataset_manifest_p17_loso.json`). |
| **Stage 5: Automated Testing** | [`backend/tests/test_phase17.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase17.py) | Added 12 new automated tests; ran full 32-test regression suite (Phase 14 + Phase 16 + Phase 17) with 32 passed, 0 failed. |
| **Stage 6: Master Validation** | [`reports/phase17_validation.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_validation.md) | Final synthesis: data readiness assessment, barrier documentation, and pre-evaluation requirements. |

---

## 2. Dataset Quality and Coverage Findings

### 2.1 Actual Counts Across Repository
- **Total Indexed Sessions:** 23
- **Unindexed Trials:** 1 (aborted trial: `phase14_p15_real_walk_t1_1792303844_1792303844.json`, 147 frames)
- **Total Physical Packets:** 3,212
- **Total Sliding Windows (Size 50):** 49 (stride 50)
- **Total Cumulative Duration:** 89.0 seconds ($3.87$ seconds / trial)
- **Distinct Participants:** 2 (`Participant_01`: 12 sessions, 1655 pkts; `Participant_02`: 11 sessions, 1557 pkts)

### 2.2 Activity & Window Breakdown
| Activity Label | Class ID | Sessions | Packets | Extracted Windows | Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `walk` | 11 | 4 | 590 | 9 | 18.37% |
| `fall` | 9 | 4 | 561 | 8 | 16.33% |
| `sit` | 8 | 4 | 595 | 10 | 20.41% |
| `clap` | 2 | 4 | 579 | 8 | 16.33% |
| `push_pull` | 0 | 4 | 578 | 9 | 18.37% |
| `static` | 6 | 3 | 309 | 5 | 10.20% |
| **Total** | — | **23** | **3,212** | **49** | **100.0%** |

### 2.3 Environmental & Geometric Uniformity
- **Room Diversity:** $100\%$ of sessions (23/23) were recorded in `Laboratory_Room1`.
- **Tx-Rx Distance:** $100\%$ of sessions (23/23) used a 2.5-meter baseline.
- **Orientation:** $100\%$ of sessions had unrecorded aspect angles (`Unknown`).
- **Obstruction State:** All recordings were pure Line-of-Sight (LOS).

---

## 3. Participant-Independent Split Evaluation

### 3.1 The $N=2$ Mathematical Barrier
A valid 3-way partition requires three mutually disjoint non-empty subsets of participants:
$$|\mathcal{P}| \ge |\mathcal{P}_{\text{train}}| + |\mathcal{P}_{\text{val}}| + |\mathcal{P}_{\text{test}}| \ge 1 + 1 + 1 = 3$$
Because the current dataset contains only 2 participants, **no 3-way participant-independent split can exist**.

The new split generator (`ParticipantIndependentSplitGenerator`) raises:
```
InsufficientParticipantsError: Cannot create a 3-way participant-independent split (Train/Val/Test) with only 2 participants (['Participant_01', 'Participant_02']). Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset.
```

### 3.2 2-Way Leave-One-Subject-Out (LOSO) Partition
To evaluate without leakage, a 2-way split was constructed and versioned as [`data/real_csi_dataset/dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json):
- **Training Split ($\mathcal{P}_{\text{train}}$):** `Participant_01` (12 sessions, 1655 pkts, 25 windows)
- **Validation Split ($\mathcal{P}_{\text{val}}$):** $\emptyset$ (0 sessions, 0 windows)
- **Held-Out Test Split ($\mathcal{P}_{\text{test}}$):** `Participant_02` (11 sessions, 1557 pkts, 24 windows)

All 6 activities are represented in both Train and Test (`missing_in_test: []`). However, the held-out test split contains only **4 fall windows**.

---

## 4. Pilot Milestone Assessment: Fall Detection Readiness

Phase 16 established an initial pilot milestone of **$\ge 35$ independently labeled, participant-held-out fall test windows**.

| Metric | Target | Current Status | Attainment | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Dataset Fall Windows** | — | 8 | — | Preliminary |
| **Held-Out Test Fall Windows** | 35 | 4 | **11.4%** | **Target Not Met** |
| **Distinct Participants** | $\ge 4$ | 2 | **50.0%** | **Target Not Met** |
| **Multi-Room Environments** | $\ge 3$ | 1 | **33.3%** | **Target Not Met** |
| **Tx-Rx Distance Variations** | $\ge 3$ | 1 (2.5m) | **33.3%** | **Target Not Met** |

```
Phase 16 Pilot Milestone Progress (Held-Out Fall Windows):
[====--------------------------------] 11.4% (4 / 35 windows)
Deficit: 31 fall windows remaining
```

### Critical Limitations & Caveats:
1. **Statistical Power Deficit:** 4 fall windows cannot provide statistically meaningful evaluation metrics. With $N=4$, an error of $\pm 1$ window swings sensitivity by $25\%$.
2. **Kinematic Homogeneity:** All 8 collected falls represent forward drops onto mats. Zero backward slips, syncope drops, bed roll-offs, or chair collapses are present.
3. **No Clinical Safety Claim:** Voluntary, padded falls performed by healthy subjects in a laboratory do not demonstrate safety-critical reliability for elderly fall detection.

---

## 5. Automated Regression Test Suite Results

The full test suite was executed via PyTest:
```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py -v
```

### Execution Telemetry:
- **Total Test Cases Executed:** 32
- **Passed:** 32
- **Failed:** 0
- **Duration:** 11.69 seconds

```
======================= 32 passed, 4 warnings in 11.69s =======================
  - backend/tests/test_phase14.py: 10 passed (Parsing, filtering, windowing, model forward pass)
  - backend/tests/test_phase16.py: 10 passed (Manifest integrity, bit checks, Doppler calibration)
  - backend/tests/test_phase17.py: 12 passed (Session lifecycle, LOSO anti-leakage, raw CSI preservation)
```

Both model checkpoint hashes were re-verified following all test executions and remain identical to initial state:
- `models/csiformer_phase13_best.pth` MD5: `383b4d98c08f8970b0443738f170ec01`
- `models/csiformer_phase15_adapted.pth` MD5: `ab3d97a04d78edf75d807178772bc828`

---

## 6. Data Readiness Verdict & Recommendations for Phase 18

### 6.1 Formal Verdict: **DATASET NOT READY FOR PRODUCTION RE-TRAINING**
The physical dataset is **not ready** for retraining or safety-critical deployment. While the acquisition software, serial driver, and LOSO split generator are verified, the physical volume and participant diversity remain severely constrained:
- An independent 3-way split cannot be constructed without at least 3 participants.
- The held-out fall sample count ($N=4$) is inadequate for scientific validation.

### 6.2 Pre-Requisites Before Further Model Development
Before retraining CSIFormer in Phase 18, the physical data collection campaign must be executed according to [`reports/phase17_collection_protocol.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase17_collection_protocol.md):
1. **Recruit at Least 3 Additional Participants:** Expand from $N=2$ to $N \ge 5$ (`Participant_03`, `Participant_04`, `Participant_05`).
2. **Collect 31+ Additional Supervised Fall Windows:** Using certified 4-inch crash mats and dedicated spotters, record at least 15 additional fall sessions ($\approx 35$ windows) across the new participants.
3. **Diversify Physical Environments:** Conduct recordings across at least 2 new rooms (e.g., Living Room with furniture, Office Room B) and multiple distances (1.5m, 3.5m).
4. **Preserve Raw Subcarriers:** Ensure all new captures retain `raw_amplitudes` (52 subcarriers) alongside aligned features.
5. **Generate a 3-Way LOSO Split:** Run `ParticipantIndependentSplitGenerator` to create a 3-way split: 3 participants in Train, 1 participant in Val, 1 participant in held-out Test.
