# CSIFormer Phase 20 — Participant-Independent Split Readiness Report

## Executive Summary

This report assesses the readiness of the physical dataset partitions for **CSIFormer Phase 20** and evaluates the mathematical constraints governing participant-independent (Leave-One-Subject-Out / LOSO) model evaluation.

In wireless sensing, Channel State Information (CSI) measures fine-grained electromagnetic scattering influenced by individual human anthropometry (e.g., body mass, stature, dielectric torso absorption). When data from the same participant appears in both training and test sets, deep neural networks easily memorize subject-specific RF signatures rather than generalizable kinematic dynamics, producing deceptively high test scores that collapse on unseen users.

Phase 20 evaluates the frozen **5-participant pilot partition design** (3 Train / 1 Val / 1 Test), audits the active **2-way LOSO split** necessitated by the $N=2$ dataset barrier, and provides formal statistical proof of why model evaluation remains strictly blocked.

---

## 1. Frozen 5-Participant Pilot Evaluation Architecture

The target evaluation framework for future CSIFormer physical validation is structured as follows:

```
+-----------------------------------------------------------------------------+
|             CSIFormer 5-Participant Target Evaluation Protocol              |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ Training Split: 3 Participants (60%) ]                                   |
|    - Target Participants: P_01, P_02, P_03                                  |
|    - Purpose: Learn domain-invariant spatio-temporal representations        |
|      across diverse body builds and walking cadences.                       |
|                                                                             |
|  [ Validation Split: 1 Participant (20%) ]                                  |
|    - Target Participant: P_04                                               |
|    - Purpose: Unbiased checkpoint selection, early stopping, and            |
|      hyperparameter regularization without test contamination.              |
|                                                                             |
|  [ Held-Out Test Split: 1 Participant (20%) — FROZEN ]                      |
|    - Target Participant: P_05                                               |
|    - Purpose: Final unbiased evaluation of participant-independent          |
|      generalization and fall detection sensitivity.                         |
|    - STRICT INVARIANT: Frozen prior to model evaluation. Never used to      |
|      tune preprocessing filters, Doppler thresholds, or network weights.    |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 1.1 Formal Partition Invariant Rules
The partition generator ([`ParticipantIndependentSplitGenerator`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py)) enforces five mathematical invariants:

1. **Pairwise Participant Invariance (Zero Identity Overlap):**
   $$\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{val}} = \emptyset, \quad \mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset, \quad \mathcal{P}_{\text{val}} \cap \mathcal{P}_{\text{test}} = \emptyset$$
   Participants are the fundamental partitioning unit. Under no circumstances may data from any individual cross partition boundaries.

2. **Pairwise Event Invariance (Zero Correlated Temporal Overlap):**
   $$\mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{val}} = \emptyset, \quad \mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{test}} = \emptyset, \quad \mathcal{E}_{\text{val}} \cap \mathcal{E}_{\text{test}} = \emptyset$$
   All packets and windows originating from a continuous movement event (`event_id`) remain in that participant's assigned partition.

3. **Window Construction Isolation:**
   Sliding temporal windows ($T=50$ frames, $1.40\text{ s}$) are extracted strictly within individual session boundaries. No window is permitted to bridge across sessions or across splits.

4. **Explicit Failure on Insufficient Participants:**
   If a 3-way split ($\text{Train} / \text{Val} / \text{Test}$) is requested on a dataset with fewer than 3 participants ($|\mathcal{P}| < 3$), the generator raises `InsufficientParticipantsError`. It never silently falls back to random or session-level partitioning.

5. **Class Coverage Verification:**
   All activity classes present in training must be present in the test partition. In strict mode (`strict_coverage=True`), the absence of any activity class or the absence of the safety-critical `fall` class raises `InadequateClassCoverageError`.

---

## 2. Statistical Limitation of 1 Held-Out Test Participant

Even when the 5-participant pilot target is achieved ($P_{\text{test}} = \{P_{05}\}$), **evaluating on a single held-out test participant provides only a preliminary pilot assessment, not proof of broad clinical generalizability**.

### Explicit Limitations:
1. **Single Anthropometric Sample:**
   One unseen test participant represents a single point in the multi-dimensional space of human stature, body mass, fat-to-muscle ratio, and dielectric absorption cross-section. Success on $P_{05}$ cannot establish robustness to populations with different body types (e.g., frail elderly individuals, wheelchair users).
2. **Kinematic Idiosyncrasy:**
   Individual movement cadences, fall dynamics, and transition speeds vary widely. A single test subject provides zero information regarding inter-subject variance on unseen individuals.
3. **Pilot vs. Regulatory Standards:**
   A 5-participant study serves as a protocol and software engineering benchmark. It does **not** constitute clinical validation under FDA or CE-MDR life-safety standards.

---

## 3. Current Dataset Reality ($N=2$ Participants)

### 3.1 Mathematical Barrier to 3-Way Partitioning
Inspection of the verified repository dataset confirms:
- **Total Distinct Participants:** $|\mathcal{P}| = 2$ (`Participant_01` and `Participant_02`).

Because a 3-way participant-independent split requires at least three mutually disjoint, non-empty participant subsets:
$$|\mathcal{P}| \ge |\mathcal{P}_{\text{train}}| + |\mathcal{P}_{\text{val}}| + |\mathcal{P}_{\text{test}}| \ge 1 + 1 + 1 = 3$$

Attempting to allocate `Participant_02` to test and `Participant_01` to validation leaves:
$$\mathcal{P}_{\text{train}} = \mathcal{P} \setminus (\mathcal{P}_{\text{val}} \cup \mathcal{P}_{\text{test}}) = \emptyset$$

Calling `ParticipantIndependentSplitGenerator.generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")` strictly triggers:
```
InsufficientParticipantsError: Cannot create a 3-way participant-independent split (Train/Val/Test) with only 2 participants (['Participant_01', 'Participant_02']). Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset.
```

### 3.2 Audited 2-Way LOSO Split Analysis
The only leakage-free participant-independent partition possible on the current dataset is a **2-way split** (`Participant_01` train, `Participant_02` test), versioned as [`data/real_csi_dataset/dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json):

```json
{
  "train_participants": ["Participant_01"],
  "val_participants": [],
  "test_participants": ["Participant_02"],
  "train_sessions": 12,
  "val_sessions": 0,
  "test_sessions": 11,
  "train_events": 12,
  "val_events": 0,
  "test_events": 11,
  "train_windows": 25,
  "val_windows": 0,
  "test_windows": 24,
  "fall_events": {
    "train": 2,
    "val": 0,
    "test": 2
  },
  "fall_windows": {
    "train": 4,
    "val": 0,
    "test": 4
  },
  "total_sessions": 23,
  "total_windows": 49
}
```

### 3.3 Class Representation Across Partitions
| Activity Class | Model Class ID | Train Windows (`Participant_01`) | Test Windows (`Participant_02`) | Total Windows | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `walk` | 11 | 4 | 5 | 9 | Fully Covered |
| `fall` | 9 | 4 | 4 | 8 | Covered (**Severe Sample Deficit: 4 vs. 35**) |
| `sit` | 8 | 4 | 6 | 10 | Fully Covered |
| `clap` | 2 | 4 | 4 | 8 | Fully Covered |
| `push_pull` | 0 | 5 | 4 | 9 | Fully Covered |
| `static` | 6 | 4 | 1 | 5 | Fully Covered (Imbalanced) |
| **All Classes** | — | **25** | **24** | **49** | **Full Taxonomy Present** |

---

## 4. Deficit Analysis Against Phase 20 Pilot Gates

| Readiness Gate Metric | Phase 20 Pilot Target | Current Verified Total | Attainment | Status | Remaining Deficit |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Distinct Participants ($|\mathcal{P}|$)** | $\ge 5$ | 2 (`P_01`, `P_02`) | 40.0% | **UNMET** | -3 participants |
| **3-Way Disjoint Split (Train/Val/Test)** | Supported | Unsupported ($N=2$) | 0.0% | **UNMET** | Requires $N \ge 3$ (pilot $N \ge 5$) |
| **Held-Out Test Fall Windows** | $\ge 35$ | 4 | 11.4% | **UNMET** | **-31 windows** |
| **Held-Out Test Fall Events** | $\ge 12$ | 2 | 16.7% | **UNMET** | **-10 events** |
| **Distinct Rooms / Environments** | $\ge 3$ | 1 (`Laboratory_Room1`) | 33.3% | **UNMET** | -2 rooms |
| **Tx-Rx Distance Variations** | $\ge 3$ | 1 ($2.5\text{ m}$) | 33.3% | **UNMET** | -2 distances |
| **Total Physical Sessions** | $\ge 50$ | 23 | 46.0% | **UNMET** | -27 sessions |
| **Total Valid Physical Packets** | $\ge 10,000$ | 3,212 | 32.1% | **UNMET** | -6,788 packets |
| **Total Valid Sliding Windows** | $\ge 150$ | 49 | 32.7% | **UNMET** | -101 windows |

---

## 5. Methodological Consequences of the Deficit

1. **Extreme Sensitivity Variance on Test Falls:**
   With only 4 test fall windows, each window represents $25.0\%$ of measured sensitivity:
   $$\text{Recall} \in \{0.00, 0.25, 0.50, 0.75, 1.00\}$$
   A single false negative (e.g., from an intermittent Wi-Fi packet drop during the impact spike) collapses measured recall from $100\%$ to $75\%$.
2. **Event Autocorrelation vs. Statistical Sample Size:**
   The 4 test fall windows derive from only 2 physical fall trials ($2\text{ windows/trial}$). Because sliding windows within a single 4-second continuous recording are temporally autocorrelated, the actual statistical sample size for test falls is $N_{\text{events}} = 2$.
3. **Absence of Validation Partition:**
   Because $N=2$, the validation set has 0 samples ($\emptyset$). Tuning decision thresholds, Doppler filter parameters, or early-stopping epochs without a validation set guarantees either:
   - Overfitting the single training participant (`Participant_01`), or
   - Contaminating the held-out test participant (`Participant_02`).
4. **Conclusion:**
   Model evaluation under these conditions cannot produce scientifically valid conclusions.

---

## 6. Split Readiness Decision

- **Split Generator Architecture:** **100% READY** ([`split_generator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py) fully implements 5-participant multi-subject assignment, pairwise zero leakage, and coverage error handling).
- **Physical Dataset Allocation:** **NOT READY** (constrained to $N=2$ participants, 4 held-out fall windows, zero validation partition).
- **Recommendation:** Keep the Phase 21 model evaluation gate firmly closed until physical recordings for $P_{03}$, $P_{04}$, and $P_{05}$ are collected, validated, and indexed.
