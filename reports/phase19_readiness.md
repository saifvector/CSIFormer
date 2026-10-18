# CSIFormer Phase 19 — Master Readiness Gate Report

## Executive Summary

**CSIFormer Phase 19** conducts an evidence-based physical data acquisition and split-readiness review governing future model evaluation on real ESP32-S3 Channel State Information (CSI). In strict compliance with the Phase 19 mandate, **no model retraining, fine-tuning, architecture alteration, or checkpoint modification was performed**.

Both reference model checkpoints were cryptographically audited before and after all Phase 19 operations, confirming bit-for-bit invariance:
- **Production Checkpoint:** [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) (MD5: `383b4d98c08f8970b0443738f170ec01`)
- **Experimental Checkpoint:** [`models/csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) (MD5: `ab3d97a04d78edf75d807178772bc828`)

This report provides the master readiness decision for advancing to Phase 20 model evaluation. Grounded strictly in physical disk telemetry, it audits data totals, participant diversity, environmental distribution, held-out fall sample sizes, regression testing, and concludes with an explicit **NO-GO** decision for Phase 20.

---

## 1. Files Changed in Phase 19

The following software, test, and documentation artifacts were created or enhanced in Phase 19:

| File Path | Action | Description |
| :--- | :---: | :--- |
| [`backend/app/services/session_validator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py) | **Created** | Comprehensive `DatasetIntegrityValidator` enforcing manifest-to-file consistency, numerical validity (NaN/Inf checks), timestamp monotonicity, sequence loss tracking, duplicate detection, and a quarantine workflow. |
| [`backend/app/services/real_csi_collector.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) | **Enhanced** | Added non-destructive overwrite protection with automatic version suffixing (`_v1`, `_v2`), preserving historical physical sessions. |
| [`backend/app/services/collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) | **Enhanced** | Integrated `event_id` tracking, explicit confirmation status (`confirmed`/`rejected`), and multi-directory data routing. |
| [`backend/app/services/split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py) | **Enhanced** | Added pairwise participant and event leakage assertions across all partition pairs ($\text{Train} \leftrightarrow \text{Test}$, $\text{Train} \leftrightarrow \text{Val}$, $\text{Val} \leftrightarrow \text{Test}$). |
| [`scratch/run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py) | **Enhanced** | Added CLI flags for `--event`, geometric positioning (`--tx-pos`, `--rx-pos`), and strict padded-mat fall safety protocols. |
| [`reports/phase19_collection_execution.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase19_collection_execution.md) | **Created** | Standardized operator protocol, fall safety checklist, operator log template, and pilot target accounting table. |
| [`reports/phase19_dataset_quality.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase19_dataset_quality.md) | **Created** | Empirical audit of the 23 physical sessions, packet rates ($35.6\text{ Hz}$), loss rates ($1.2\%$), and unindexed file analysis. |
| [`reports/phase19_split_readiness.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase19_split_readiness.md) | **Created** | Formal specification of the frozen 5-participant pilot evaluation protocol, mathematical limitations of $N=2$, and deficit analysis. |
| [`reports/phase19_readiness.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase19_readiness.md) | **Created** | Master Phase 19 readiness gate review and formal GO/NO-GO decision. |
| [`backend/tests/test_phase19.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase19.py) | **Created** | Automated unit tests covering session validation, overwrite protection, quarantine workflow, and 5-participant split allocation. |

---

## 2. Actual Verified Physical Data Totals and New Additions

In adherence to scientific integrity, **no physical recordings were fabricated or simulated**. In this development iteration, without physical hardware connection from the operator:
- **Newly Added Physical Recordings:** **0**
- **Newly Added Physical Packets:** **0**
- **Newly Added Physical Windows:** **0**

The current repository dataset remains the baseline established in prior phases:
- **Total Physical Session Files on Disk:** 24 (23 indexed in manifest, 1 unindexed aborted trial).
- **Total Indexed Sessions:** 23
- **Total Valid Physical Packets:** 3,212
- **Total Valid Sliding Windows ($T=50$):** 49

### Target vs. Current Attainment Table
| Metric | Baseline Count | Newly Added | Current Verified Total | Pilot Target | Remaining Deficit | Evidence Reference |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Physical Sessions** | 23 | 0 | 23 | $\ge 50$ | **-27 sessions** | `data/real_csi_dataset/dataset_manifest.json` |
| **Physical Packets** | 3,212 | 0 | 3,212 | $\ge 10,000$ | **-6,788 packets** | Sum of `packet_count` in 23 session files |
| **Valid Sliding Windows** | 49 | 0 | 49 | $\ge 150$ | **-101 windows** | Total non-overlapping 50-frame windows |
| **Distinct Participants** | 2 | 0 | 2 | $\ge 5$ | **-3 participants** | `Participant_01`, `Participant_02` |
| **Distinct Rooms** | 1 | 0 | 1 | $\ge 3$ | **-2 rooms** | `Laboratory_Room1` exclusively |
| **Tx-Rx Distances** | 1 | 0 | 1 | $\ge 3$ | **-2 distances** | $2.5\text{ m}$ baseline exclusively |
| **Held-Out Test Fall Windows** | 4 | 0 | 4 | $\ge 35$ | **-31 windows** | `dataset_manifest_p17_loso.json` |
| **Held-Out Test Fall Events** | 2 | 0 | 2 | $\ge 12$ | **-10 events** | Distinct physical fall trials in test |

---

## 3. Participant, Room, Distance, and Class Diversity

1. **Participant Diversity:**
   - Total Subjects: $N=2$ (`Participant_01`: 12 sessions, 25 windows; `Participant_02`: 11 sessions, 24 windows).
   - Deficit: 3 additional subjects required to achieve the intended 5-subject pilot protocol.
2. **Room Diversity:**
   - Single environment: `Laboratory_Room1` (100% of data).
   - Static multipath profile remains completely unperturbed across different room geometries, furniture densities, or wall materials.
3. **Distance Diversity:**
   - Single geometric baseline: $2.5\text{ m}$ Tx-Rx distance (100% of data).
   - Variations at close range ($1.5\text{ m}$) or extended range ($3.5\text{ m}$) are absent.
4. **Activity Class Coverage:**
   - All 6 classes from the CSIFormer human activity recognition taxonomy are represented:
     - `push_pull`: 9 windows (5 train, 4 test)
     - `clap`: 8 windows (4 train, 4 test)
     - `static`: 5 windows (4 train, 1 test)
     - `sit`: 10 windows (4 train, 6 test)
     - `fall`: 8 windows (4 train, 4 test)
     - `walk`: 9 windows (4 train, 5 test)

---

## 4. Held-Out Fall Window and Distinct Event Counts

Evaluating fall detection sensitivity under participant independence is the core scientific requirement:
- **Test Fall Windows:** Exactly **4 windows** ($1.40\text{ s}$ duration each).
- **Test Fall Events:** Exactly **2 discrete physical fall trials**.
- **Deficit Against Pilot Targets:**
  - Fall Windows: 4 attained vs. 35 required (**11.4% attainment, -31 deficit**).
  - Fall Events: 2 attained vs. 12 required (**16.7% attainment, -10 deficit**).

### Statistical Implication:
Measuring model performance on 4 windows from 2 events yields extreme discrete variance:
$$\text{Recall} \in \{0\%, 25\%, 50\%, 75\%, 100\%\}$$
A single missed window drops recall by 25.0 percentage points. Furthermore, consecutive windows within a single 4-second fall recording are temporally autocorrelated, meaning the effective statistical sample size is $N_{\text{events}} = 2$.

---

## 5. Participant-Independent Split Validation

1. **Frozen 5-Participant Pilot Allocation:**
   The target design is frozen:
   - $\mathcal{P}_{\text{train}} = \{P_{01}, P_{02}, P_{03}\}$ (3 participants)
   - $\mathcal{P}_{\text{val}} = \{P_{04}\}$ (1 participant)
   - $\mathcal{P}_{\text{test}} = \{P_{05}\}$ (1 participant, frozen test set)
2. **Mathematical Infeasibility on Current Data:**
   Because $|\mathcal{P}| = 2$, a 3-way partition ($\text{Train} / \text{Val} / \text{Test}$) is impossible ($2 < 3$). Calling `generate_loso_split` with both test and val participants strictly raises `InsufficientParticipantsError`.
3. **Active 2-Way Partition:**
   The current clean partition (`dataset_manifest_p17_loso.json`) allocates:
   - Train: `Participant_01` (25 windows, 2 fall events)
   - Val: $\emptyset$ (0 windows)
   - Test: `Participant_02` (24 windows, 2 fall events)
4. **Leakage Audit:**
   Automated verification confirms:
   - Zero participant overlap: $\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset$
   - Zero event overlap: $\mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{test}} = \emptyset$
   - Zero window overlap: All windows constructed strictly within session boundaries.

---

## 6. Regression Test Results

The full automated regression suite was executed:
```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py -v
```

### Telemetry Summary:
- **Phase 14 Tests:** 10 passed (Hardware streaming, window sliding, inference pipeline)
- **Phase 16 Tests:** 10 passed (Manifest consistency, Doppler calibration, checkpoint hashes)
- **Phase 17 Tests:** 12 passed (Session lifecycle, unconfirmed trial mapping, 2-way LOSO)
- **Phase 18 Tests:** 12 passed (Raw CSI dimensions, event isolation, coverage checks)
- **Phase 19 Tests:** 10 passed (Session validation, overwrite protection, quarantine workflow, 5-participant split allocation)
- **Total Tests:** **54 passed, 0 failed** in ~12 seconds.

---

## 7. Before-and-After Checkpoint Hashes

Cryptographic MD5 verification confirms that model weights were preserved with zero alterations:

| Checkpoint Path | Purpose | Expected MD5 Hash | Audited MD5 Hash | Verification |
| :--- | :--- | :---: | :---: | :---: |
| [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) | Production Reference | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Bit-for-Bit)** |
| [`models/csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) | Experimental Baseline | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Bit-for-Bit)** |

---

## 8. Remaining Physical Collection Tasks

Before Phase 20 model evaluation or fine-tuning can proceed, the human operator must execute the physical collection campaign using the tools verified in Phase 19:

1. **Recruit 3 Additional Participants:**
   Recruit `Participant_03`, `Participant_04`, and `Participant_05` across diverse heights and body masses.
2. **Execute Multi-Room Recordings:**
   Collect trials in at least two new rooms (e.g., Living Room with furniture, Office Room B).
3. **Vary Tx-Rx Distances:**
   Record sessions at $1.5\text{ m}$ and $3.5\text{ m}$ baselines.
4. **Conduct Supervised Fall Collection:**
   Under strict supervision on a certified $\ge 4$-inch crash mat with a spotter, record at least 15 additional fall sessions ($\ge 31$ fall windows) across the new participants.
5. **Run Dataset Integrity Validator:**
   Execute `DatasetIntegrityValidator.validate_dataset_manifest()` to verify zero corruptions.
6. **Generate 5-Participant 3-Way Split:**
   Run `ParticipantIndependentSplitGenerator.generate_loso_split(test_participant="Participant_05", val_participant="Participant_04")` to produce the frozen evaluation partitions.

---

## 9. Final Readiness Decision for Phase 20

> [!IMPORTANT]
> ### READINESS GATE VERDICT: **NO-GO FOR PHASE 20 MODEL EVALUATION**
>
> **Core Justification:**
> 1. **Data Gates Unmet:** The physical dataset has 23 of 50 sessions (46%), 3,212 of 10,000 packets (32.1%), and 49 of 150 windows (32.7%).
> 2. **Critical Fall Deficit:** Only 4 held-out fall windows exist from 2 physical events (target: $\ge 35$ windows, $\ge 12$ events). Evaluation on 4 windows is statistically meaningless.
> 3. **Mathematical Split Barrier:** With $N=2$ participants, a 3-way Train/Val/Test split cannot be constructed without data leakage. Zero validation windows are available.
> 4. **Zero Domain Diversity:** All data originates from a single room at a single Tx-Rx distance.
>
> **Actionable Next Step:** The operator must perform physical collection with the ESP32-S3 hardware using `scratch/run_collection_session.py` to fulfill the deficits before opening the Phase 20 gate.

---

## 10. Safety and Clinical Disclaimer

> [!CAUTION]
> **CSIFormer is an experimental academic research prototype.**
> It has **NOT** undergone clinical validation, medical trials, or regulatory certification under FDA, CE-MDR, or equivalent life-safety standards. It must **NEVER** be deployed as a safety-critical fall detector, emergency dispatch trigger, or medical monitoring device in residential, healthcare, or industrial environments.
