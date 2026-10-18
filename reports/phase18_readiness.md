# CSIFormer Phase 18 — Master Readiness Gate Report

## Executive Summary

**CSIFormer Phase 18** establishes an auditable quality and readiness gate governing future model evaluations on physical ESP32-S3 Channel State Information (CSI). In accordance with the Phase 18 mandate, **no model retraining, fine-tuning, or checkpoint modifications were performed**. 

Both reference checkpoints remain bit-for-bit identical before and after Phase 18 execution:
- **Production Checkpoint:** [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) (MD5: `383b4d98c08f8970b0443738f170ec01`)
- **Experimental Checkpoint:** [`models/csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) (MD5: `ab3d97a04d78edf75d807178772bc828`)

This report provides the formal evaluation of the readiness gate, comparing actual physical dataset metrics against declared pilot targets, analyzing participant-independent split integrity, summarizing the 44-test regression suite, and rendering a definitive **GO / NO-GO** decision for Phase 19.

---

## 1. Actual Physical Data Counts vs. Pilot Targets

The dataset stored in [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/) was comprehensively audited:

| Evaluation Metric | Phase 18 Pilot Target | Current Audited Count | Attainment (%) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Physical Sessions** | $\ge 50$ | 23 | 46.0% | **Target Not Met** |
| **Physical Packets** | $\ge 10,000$ | 3,212 | 32.1% | **Target Not Met** |
| **Valid Sliding Windows (50 frames)** | $\ge 150$ | 49 | 32.7% | **Target Not Met** |
| **Distinct Participants** | $\ge 5$ | 2 | 40.0% | **Barrier ($N=2$)** |
| **Distinct Rooms** | $\ge 3$ | 1 (`Laboratory_Room1`) | 33.3% | **Domain Gap** |
| **Tx-Rx Distances** | $\ge 3$ | 1 ($2.5\text{ m}$) | 33.3% | **Domain Gap** |
| **Held-Out Test Fall Windows** | $\ge 35$ | 4 | **11.4%** | **Critical Deficit (-31)** |
| **Held-Out Test Fall Events** | $\ge 12$ | 2 | **16.7%** | **Critical Deficit (-10)** |
| **Packet Sampling Rate** | $\ge 30\text{ Hz}$ | $35.6\text{ Hz}$ | 100.0% | **Passed** |
| **Packet Loss Rate** | $< 5.0\%$ | $1.2\%$ | 100.0% | **Passed** |

```
Pilot Target Attainment:
Physical Packets:       [========------------------------] 32.1% (3,212 / 10,000)
Valid Windows:          [========------------------------] 32.7% (49 / 150)
Held-Out Fall Windows:  [====----------------------------] 11.4% (4 / 35)
Distinct Subjects:      [==========----------------------] 40.0% (2 / 5)
```

---

## 2. Participant-Independent Split Status

1. **3-Way Split Infeasibility at $N=2$:**
   Because the dataset contains only two subjects (`Participant_01` and `Participant_02`), partitioning into three mutually disjoint subsets ($\mathcal{P}_{\text{train}}, \mathcal{P}_{\text{val}}, \mathcal{P}_{\text{test}}$) is mathematically impossible ($|\mathcal{P}| = 2 < 3$). Calling `generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")` strictly raises `InsufficientParticipantsError`.
2. **2-Way LOSO Partition:**
   The only valid participant-independent split is a 2-way partition (`Participant_01` train, `Participant_02` test) versioned as [`data/real_csi_dataset/dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json).
   - Train Split: 12 sessions, 1,655 packets, 25 windows, 2 fall events, 4 fall windows.
   - Validation Split: 0 sessions, 0 windows ($\emptyset$).
   - Test Split: 11 sessions, 1,557 packets, 24 windows, 2 fall events, 4 fall windows.
3. **Leakage Verification:**
   All 12 training events and 11 test events are completely disjoint. Zero participant overlap exists.
4. **5-Participant Architecture Prepared:**
   [`split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py) has been upgraded and verified to support 5-participant allocations (e.g. 3 Train, 1 Val, 1 Test) with event-level isolation as soon as physical recruitment reaches $N \ge 5$.

---

## 3. Automated Test Suite Results

The complete regression test suite spanning Phase 14, Phase 16, Phase 17, and Phase 18 was executed:
```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py -v
```

### Telemetry Summary:
- **Total Test Cases:** 44
- **Passed:** 44
- **Failed:** 0
- **Execution Time:** 10.13 seconds

```
======================= 44 passed, 4 warnings in 10.13s =======================
  - backend/tests/test_phase14.py: 10 passed (Hardware streaming, window construction, inference pipeline)
  - backend/tests/test_phase16.py: 10 passed (Manifest integrity, Doppler calibration, checkpoint hashes)
  - backend/tests/test_phase17.py: 12 passed (Session lifecycle, unconfirmed trial mapping, 2-way LOSO)
  - backend/tests/test_phase18.py: 12 passed (Format A/B subcarrier parsing, event isolation, coverage checks)
```

---

## 4. Checkpoint Integrity Verification (Before vs. After)

Both checkpoints were verified bit-for-bit using MD5 hashing before and after all Phase 18 operations:

| Checkpoint File | Role | Expected MD5 Hash | Audited MD5 Hash | Status |
| :--- | :--- | :---: | :---: | :---: |
| `models/csiformer_phase13_best.pth` | Production Reference | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **Unchanged** |
| `models/csiformer_phase15_adapted.pth` | Experimental Baseline | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **Unchanged** |

---

## 5. Formal Readiness Gate Decision

> [!IMPORTANT]
> ### READINESS GATE VERDICT: **NO-GO FOR PHASE 19 MODEL EVALUATION OR RETRAINING**
> 
> **Decision Justification:**
> 1. **Insufficient Held-Out Fall Data:** The test partition contains only **4 fall windows** from **2 discrete physical events**. Evaluating or comparing models on $N=4$ fall windows is statistically meaningless; an error of 1 window shifts observed recall by 25.0%.
> 2. **Zero Validation Capacity:** The 2-participant constraint leaves 0 samples for validation. Tuning classification thresholds or early-stopping criteria without a validation partition guarantees either test-set overfitting or blind training.
> 3. **Severe Environmental Overfitting Risk:** 100% of the dataset was recorded in a single room at a single 2.5m distance. Any model fine-tuned on this data will overfit to the static multipath profile of `Laboratory_Room1`.
> 
> **Software vs. Hardware Distinction:** The collection software, serial driver, UDP stimulation engine, and LOSO split generator are **100% READY**. However, the **physical dataset itself is NOT READY**.

---

## 6. Outstanding Physical Collection Tasks Before Phase 19

Before proceeding to Phase 19 model evaluation or retraining, the physical collection campaign must be executed:

1. **Recruit 3 Additional Participants:**
   Expand the participant pool to at least five distinct individuals (`Participant_03`, `Participant_04`, `Participant_05`) spanning different heights and body masses.
2. **Conduct Supervised Fall Collection Campaign:**
   Under strict adherence to [`reports/phase18_collection_campaign.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase18_collection_campaign.md):
   - Utilize a certified $\ge 4$-inch shock-absorbing crash mat and dedicated spotter.
   - Record at least 15 additional fall sessions ($\ge 31$ fall windows) across the new subjects.
3. **Multi-Room & Distance Diversity:**
   - Record sessions in at least two new rooms (e.g. Living Room with furniture, Office Room B).
   - Gather trials at 1.5m and 3.5m baselines.
4. **Generate 3-Way LOSO Split (3 Train, 1 Val, 1 Test):**
   Execute `ParticipantIndependentSplitGenerator.generate_loso_split` to create a true 3-way partition:
   - Train: `Participant_01`, `Participant_02`, `Participant_03`
   - Val: `Participant_04`
   - Test: `Participant_05` (Frozen)

---

## 7. Safety & Regulatory Disclaimer

> [!CAUTION]
> **CSIFormer is a research-stage wireless sensing prototype.**
> It has **NOT** undergone clinical evaluation, medical trials, or regulatory certification (FDA, CE-MDR). It must **NEVER** be deployed as a safety-critical life-safety system, elderly emergency monitoring device, or medical diagnostic instrument.
