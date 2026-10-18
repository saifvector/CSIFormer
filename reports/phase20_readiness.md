# CSIFormer Phase 20 — Master Readiness Gate Report

## Executive Summary

**CSIFormer Phase 20** executes an evidence-based audit, hardware connectivity check, and split-readiness review governing future model evaluation on real ESP32-S3 Channel State Information (CSI). In strict accordance with the Phase 20 mandate:
- **No model retraining, fine-tuning, evaluation, quantization, architecture alteration, or checkpoint modification was performed.**
- **No physical data was fabricated or simulated.**
- Both reference model checkpoints were cryptographically audited before and after Phase 20 operations, confirming bit-for-bit invariance:
  - **Production Checkpoint:** [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) (MD5: `383b4d98c08f8970b0443738f170ec01`)
  - **Experimental Checkpoint:** [`models/csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) (MD5: `ab3d97a04d78edf75d807178772bc828`)

This report provides the master readiness decision for advancing to Phase 21 model evaluation. Grounded strictly in physical disk telemetry and empirical regression test output, it audits dataset totals, participant diversity, environmental distribution, held-out fall sample sizes, and concludes with an unambiguous **NO-GO** decision for Phase 21.

---

## 1. Files Changed in Phase 20

| File Path | Action | Description |
| :--- | :---: | :--- |
| [`collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) | **Enhanced** | Fixed `ROOT_DIR` and `DATASET_DIR` resolution to point to project root `data/real_csi_dataset/` rather than nested `backend/data/`. |
| [`run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py) | **Enhanced** | Added `--validate` flag integrating [`DatasetIntegrityValidator`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py) into the operator CLI and updated operational banners for Phase 20. |
| [`test_phase20.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase20.py) | **Created** | Automated unit tests covering dataset manifest integrity, CLI validation, hardware verification schema, unindexed file traceability, LOSO metrics, overwrite protection, quarantine workflow, raw subcarrier separation, and checkpoint hash invariance. |
| [`phase20_collection_execution.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase20_collection_execution.md) | **Created** | Operational collection protocol, hardware connection verification, fall safety rules, operator log template, and pilot target accounting table. |
| [`phase20_dataset_quality.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase20_dataset_quality.md) | **Created** | Empirical audit of the 23 physical sessions, packet rates ($35.6\text{ Hz}$), sequence continuity ($1.2\%$ loss), raw subcarrier counts (64 FFT bins vs. 56 interpolated channels), and unindexed trial analysis. |
| [`phase20_split_readiness.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase20_split_readiness.md) | **Created** | Formal specification of the frozen 5-participant pilot evaluation protocol (3 Train / 1 Val / 1 Test), mathematical proof of $N=2$ 3-way split infeasibility, and deficit analysis. |
| [`phase20_readiness.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase20_readiness.md) | **Created** | Master Phase 20 readiness gate review, deficit tables, and formal NO-GO decision. |

---

## 2. Actual Hardware Verification Status

The physical hardware receiver interface was tested via:
```powershell
py -3.11 scratch/run_collection_session.py --verify --port COM5
```

### Empirical Results:
- **Serial Port:** `COM5` (WCH CH343 USB-to-UART bridge)
- **Baud Rate:** `115200`
- **Serial Connection:** `True` (Port opened successfully)
- **Streaming State:** `NO_PACKETS` (0 packets received in 1.5-second test window)
- **Sampling Rate:** `0.0 Hz`
- **Mean RSSI:** `-99.0 dBm` (default initial state)
- **Status:** **PENDING TRANSMITTER ACTIVATION**. The hardware bridge is verified, but the remote Wi-Fi transmission source (`Tp link` AP / UDP probe) was inactive. No simulated data was substituted.

---

## 3. Actual Verified Physical Data Totals and New Additions

Because no physical ESP32-S3 hardware sessions were supplied by the human operator during this cycle, **0 new physical recordings were added**, preserving scientific integrity.

### Target vs. Current Attainment Table
| Metric | Baseline Count | Newly Added | Current Verified Total | Pilot Target | Remaining Deficit | Evidence File Reference |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Physical Sessions** | 23 | 0 | **23** | $\ge 50$ | **-27 sessions** | [`dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json) |
| **Physical Packets** | 3,212 | 0 | **3,212** | $\ge 10,000$ | **-6,788 packets** | Sum of `packet_count` in 23 session files |
| **Valid Sliding Windows ($T=50$)** | 49 | 0 | **49** | $\ge 150$ | **-101 windows** | Discrete non-overlapping 50-frame windows |
| **Distinct Participants** | 2 | 0 | **2** | $\ge 5$ | **-3 participants** | `Participant_01`, `Participant_02` |
| **Distinct Rooms** | 1 | 0 | **1** | $\ge 3$ | **-2 rooms** | `Laboratory_Room1` exclusively |
| **Tx-Rx Distances** | 1 | 0 | **1** | $\ge 3$ | **-2 distances** | $2.5\text{ m}$ baseline exclusively |
| **Held-Out Test Fall Windows** | 4 | 0 | **4** | $\ge 35$ | **-31 windows** | [`dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json) |
| **Held-Out Test Fall Events** | 2 | 0 | **2** | $\ge 12$ | **-10 events** | Distinct physical fall sessions in test |

*(Note: Exactly 24 session JSON files exist in [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/); 23 are indexed in the primary manifest, while 1 is an unindexed trial [`phase14_p15_real_walk_t1_1792303844_1792303844.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/phase14_p15_real_walk_t1_1792303844_1792303844.json) with 147 frames, omitted from manifest totals due to initial naming collision.)*

---

## 4. Participant, Room, Distance, and Activity Diversity

1. **Participant Diversity:**
   - Total subjects: $N=2$ (`Participant_01`: 12 sessions, 25 windows; `Participant_02`: 11 sessions, 24 windows).
   - Deficit: 3 additional participants required to achieve the intended 5-subject pilot protocol.
2. **Room Diversity:**
   - 100% of physical data was recorded in `Laboratory_Room1`. Zero trials exist in living rooms, furnished bedrooms, or corridors.
3. **Distance Diversity:**
   - 100% of data was collected at a fixed Tx-Rx separation of $2.5\text{ m}$. Variations at near range ($1.5\text{ m}$) or far range ($3.5\text{ m}$) are absent.
4. **Activity Class Diversity:**
   - All 6 classes from the CSIFormer human activity recognition taxonomy are represented:
     - `walk`: 9 windows (5 train, 4 test)
     - `fall`: 8 windows (4 train, 4 test)
     - `sit`: 10 windows (4 train, 6 test)
     - `clap`: 8 windows (4 train, 4 test)
     - `push_pull`: 9 windows (5 train, 4 test)
     - `static`: 5 windows (4 train, 1 test)

---

## 5. Held-Out Fall Window and Distinct Event Counts

Under the leakage-free 2-way Leave-One-Subject-Out (LOSO) partition (`Participant_02` held-out test):
- **Held-Out Fall Windows:** **4 windows** ($1.40\text{ s}$ duration each).
- **Held-Out Distinct Fall Events:** **2 physical events**.
- **Deficit vs. Pilot Gate:**
  - Fall Windows: $4 / 35 = \mathbf{11.4\%}$ attainment (**Deficit: -31 windows**).
  - Fall Events: $2 / 12 = \mathbf{16.7\%}$ attainment (**Deficit: -10 events**).
- **Statistical Consequence:** With only 4 test windows, each window represents $25.0\%$ of measured sensitivity. A single missed window drops recall by 25.0 percentage points. Furthermore, the 4 windows originate from only 2 physical events, meaning the statistical degrees of freedom for test falls is $N_{\text{events}} = 2$.

---

## 6. Participant-Independent Split Validation

1. **Frozen 5-Participant Target Protocol:**
   The pilot evaluation allocation has been formally specified and frozen:
   - **Training Partition ($\mathcal{P}_{\text{train}}$):** 3 participants ($P_{01}, P_{02}, P_{03}$)
   - **Validation Partition ($\mathcal{P}_{\text{val}}$):** 1 participant ($P_{04}$)
   - **Held-Out Test Partition ($\mathcal{P}_{\text{test}}$):** 1 participant ($P_{05}$, frozen prior to any future model evaluation)
2. **Mathematical Infeasibility on Current Dataset:**
   Because $|\mathcal{P}| = 2 < 3$, a 3-way partition is mathematically impossible. Calling `generate_loso_split` with both validation and test participants strictly raises `InsufficientParticipantsError`.
3. **Audited 2-Way Partition:**
   The current dataset is partitioned into a 2-way split:
   - Train: `Participant_01` (25 windows, 2 fall events)
   - Val: $\emptyset$ (0 windows)
   - Test: `Participant_02` (24 windows, 2 fall events)
4. **Leakage Verification:**
   Automated unit tests assert zero participant leakage, zero event leakage, and zero window overlap across all partition boundaries.

---

## 7. Actual Regression Test Results

The full automated regression suite was executed via pytest:
```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py -v
```

### Test Results Breakdown:
- [`test_phase14.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase14.py): **10 passed** (Hardware streaming, Format A/B parsing, inference pipeline)
- [`test_phase16.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase16.py): **10 passed** (Manifest consistency, Doppler calibration, checkpoint hashes)
- [`test_phase17.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase17.py): **12 passed** (Session lifecycle, unconfirmed trial mapping, 2-way LOSO)
- [`test_phase18.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase18.py): **12 passed** (Raw CSI dimensions, event isolation, coverage checks)
- [`test_phase19.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase19.py): **10 passed** (Session validation, overwrite protection, quarantine workflow, 5-participant split allocation)
- [`test_phase20.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase20.py): **10 passed** (Manifest disk integrity, CLI validation mode, hardware telemetry schema, unindexed file tracking, checkpoint invariance)
- **Overall Telemetry:** **64 passed, 0 failed, 4 deprecation warnings in 12.43s**

---

## 8. Before-and-After Checkpoint Hashes

Cryptographic MD5 verification confirms that both model checkpoints were preserved with zero modifications:

| Checkpoint File | Checkpoint Role | Expected MD5 Hash | Audited MD5 Hash | Verification Status |
| :--- | :--- | :---: | :---: | :---: |
| [`csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) | Production Reference | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Unchanged)** |
| [`csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) | Experimental Baseline | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Unchanged)** |

---

## 9. Remaining Physical Collection Tasks

Before opening the readiness gate for Phase 21 model evaluation, the human operator must execute the physical collection campaign using [`scratch/run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py):

1. **Recruit 3 Additional Participants:**
   Recruit `Participant_03`, `Participant_04`, and `Participant_05` across diverse heights and body masses.
2. **Execute Multi-Room Recordings:**
   Collect trials in at least two new rooms (e.g., Living Room with furniture, Office Room B) to break the single-room multipath bias.
3. **Vary Tx-Rx Baselines:**
   Record sessions at $1.5\text{ m}$ (near-field) and $3.5\text{ m}$ (far-field) distances.
4. **Conduct Supervised Fall Collection:**
   Under strict supervision on a certified $\ge 4$-inch crash mat with a spotter, record at least 15 additional fall sessions ($\ge 31$ fall windows) across the new participants.
5. **Validate and Index:**
   Run `py -3.11 scratch/run_collection_session.py --validate` to verify zero corruptions, then generate the 3-way partition using [`split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py).

---

## 10. Final Readiness Decision for Phase 21 Model Evaluation

> [!IMPORTANT]
> ### READINESS GATE VERDICT: **NO-GO FOR PHASE 21 MODEL EVALUATION OR RETRAINING**
>
> **Core Justification:**
> 1. **Data Quantity Deficit:** The physical dataset has 23 of 50 sessions (46.0%), 3,212 of 10,000 packets (32.1%), and 49 of 150 windows (32.7%).
> 2. **Critical Fall Deficit:** Only 4 held-out fall windows exist from 2 physical events (target: $\ge 35$ windows, $\ge 12$ events). Evaluation on 4 windows is statistically meaningless.
> 3. **Mathematical Split Barrier:** With $N=2$ participants, a 3-way Train/Val/Test split cannot be constructed without data leakage. Zero validation windows are available.
> 4. **Zero Domain Diversity:** All data originates from a single room at a single Tx-Rx distance.
>
> **Actionable Next Step:** The operator must perform physical collection with the ESP32-S3 hardware using `scratch/run_collection_session.py` to fulfill the deficits before opening the Phase 21 gate.

---

## 11. Safety and Clinical Disclaimer

> [!CAUTION]
> **CSIFormer is an experimental academic research prototype.**
> It has **NOT** undergone clinical validation, medical trials, or regulatory certification under FDA, CE-MDR, or equivalent life-safety standards. It must **NEVER** be deployed as a safety-critical fall detector, emergency dispatch trigger, or medical monitoring device in residential, healthcare, or industrial environments.
