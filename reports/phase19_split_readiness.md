# CSIFormer Phase 19 — Participant-Independent Split Readiness Report

## Executive Summary

This report establishes the participant-independent evaluation architecture and assesses the dataset split readiness for **CSIFormer Phase 19**. 

A core principle of scientific validation in wireless sensing is that Wi-Fi Channel State Information (CSI) carries biometric and anthropometric characteristics specific to an individual (e.g., body mass, height, gait tempo, torso scattering cross-section). Consequently, random session-level or frame-level splitting causes catastrophic data leakage, leading to artificially inflated accuracy metrics that collapse when evaluated on unseen people.

Phase 19 formally defines and freezes the target **5-participant pilot evaluation protocol** (3 Train / 1 Val / 1 Test), evaluates the actual dataset constraints ($N=2$ participants), audits the active 2-way Leave-One-Subject-Out (LOSO) partition, and provides empirical evidence of why Phase 20 model evaluation cannot proceed until physical collection targets are fulfilled.

---

## 1. Frozen 5-Participant Pilot Evaluation Protocol

To prevent test-set overfitting and establish reproducible evaluation benchmarks, the target evaluation design is structured as follows:

```
+-----------------------------------------------------------------------------+
|               CSIFormer 5-Participant Pilot Partition Protocol              |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ Training Partition: 3 Participants ]                                     |
|    - Participants: P_01, P_02, P_03                                         |
|    - Purpose: Learn domain-invariant motion features across diverse body     |
|      builds, walking speeds, and transition dynamics.                       |
|                                                                             |
|  [ Validation Partition: 1 Participant ]                                    |
|    - Participant: P_04                                                      |
|    - Purpose: Epoch checkpoint selection, learning-rate scheduling, and     |
|      loss convergence monitoring.                                           |
|                                                                             |
|  [ Held-Out Test Partition: 1 Participant (FROZEN) ]                        |
|    - Participant: P_05                                                      |
|    - Purpose: Final unbiased assessment of participant-independent          |
|      generalization and fall detection sensitivity.                         |
|    - STRICT RULE: Frozen prior to model evaluation. Zero tuning of          |
|      preprocessing filters, Doppler thresholds, or network parameters       |
|      against this partition.                                                |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 1.1 Formal Partition Invariants
The `ParticipantIndependentSplitGenerator` (`backend/app/services/split_generator.py`) enforces strict mathematical isolation:

1. **Pairwise Participant Invariance (Zero Identity Leakage):**
   $$\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{val}} = \emptyset, \quad \mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset, \quad \mathcal{P}_{\text{val}} \cap \mathcal{P}_{\text{test}} = \emptyset$$
   Participant identities determine split boundaries. Under no circumstance may a participant appear in more than one partition.

2. **Pairwise Event & Session Invariance (Zero Temporal Correlated Leakage):**
   $$\mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{val}} = \emptyset, \quad \mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{test}} = \emptyset, \quad \mathcal{E}_{\text{val}} \cap \mathcal{E}_{\text{test}} = \emptyset$$
   All packets, windows, and sessions generated during a physical movement event (`event_id`) remain strictly within that participant's assigned partition.

3. **Window Construction Isolation:**
   Sliding windows ($T=50$ packets, $1.40\text{ s}$) are extracted strictly within individual session boundaries. No window is allowed to bridge across sessions or across splits.

4. **Explicit Failure on Insufficient Subjects:**
   If a 3-way split ($\text{Train} / \text{Val} / \text{Test}$) is requested on a dataset where $|\mathcal{P}| < 3$, the split generator raises `InsufficientParticipantsError`. It never silently degrades to random or session-level partitioning.

5. **Class Coverage Verification:**
   All activity classes present in training must be represented in the test partition. In strict mode (`strict_coverage=True`), absence of any class or absence of falls raises `InadequateClassCoverageError`.

---

## 2. Limitation of 1 Held-Out Test Participant

Even when the 5-participant pilot target is achieved ($P_{\text{test}} = \{P_{05}\}$), **a single held-out test participant provides only a preliminary pilot assessment**.

### Explicit Limitations:
1. **Limited Anthropometric Diversity:**
   One unseen test participant represents a single point in the space of human body mass, stature, fat-to-muscle ratio, and dielectric scattering properties. Success on $P_{05}$ cannot prove generalizability to populations with different body builds (e.g., pediatric, geriatric, or mobility-impaired individuals).
2. **Kinematic Idiosyncrasy:**
   Individual movement cadences, fall descent speeds, and transition styles vary significantly. Evaluating on one subject carries high variance.
3. **Pilot vs. Clinical Sufficiency:**
   A 5-participant setup is a software engineering and protocol proof-of-concept. It does **not** constitute clinical validation or safety-critical reliability under IEC/ISO medical device standards.

---

## 3. Current Dataset Reality ($N=2$ Participants)

### 3.1 Mathematical Barrier to 3-Way Partitioning
Inspection of the actual verified repository dataset on disk (`data/real_csi_dataset/dataset_manifest.json`) reveals:
- Total Participants: $|\mathcal{P}| = 2$ (`Participant_01`, `Participant_02`)
- Total Sessions: 23
- Total Physical Packets: 3,212
- Total Windows: 49

Because a 3-way participant-independent split requires at least 3 mutually disjoint, non-empty participant subsets:
$$|\mathcal{P}| \ge |\mathcal{P}_{\text{train}}| + |\mathcal{P}_{\text{val}}| + |\mathcal{P}_{\text{test}}| \ge 1 + 1 + 1 = 3$$

Attempting to allocate `Participant_02` to test and `Participant_01` to validation leaves:
$$\mathcal{P}_{\text{train}} = \mathcal{P} \setminus (\mathcal{P}_{\text{val}} \cup \mathcal{P}_{\text{test}}) = \emptyset$$
which raises `InsufficientParticipantsError`.

### 3.2 Audited 2-Way LOSO Baseline Split
The only valid participant-independent partition possible on the current 2-participant dataset is a **2-way split** (`data/real_csi_dataset/dataset_manifest_p17_loso.json`):
- **Training Partition ($\mathcal{P}_{\text{train}}$):** `Participant_01` (12 sessions, 1,652 packets, 25 windows)
- **Validation Partition ($\mathcal{P}_{\text{val}}$):** $\emptyset$ (0 sessions, 0 packets, 0 windows)
- **Held-Out Test Partition ($\mathcal{P}_{\text{test}}$):** `Participant_02` (11 sessions, 1,560 packets, 24 windows)

### 3.3 Partition Window & Event Accounting
| Partition | Participant ID | Sessions | Events | Total Packets | Total Windows | Fall Events | Fall Windows |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | `Participant_01` | 12 | 12 | 1,652 | 25 | 2 | 4 |
| **Val** | None | 0 | 0 | 0 | 0 | 0 | 0 |
| **Test** | `Participant_02` | 11 | 11 | 1,560 | 24 | 2 | 4 |
| **Total** | **2 Participants** | **23** | **23** | **3,212** | **49** | **4** | **8** |

### 3.4 Class Distribution in 2-Way Split
| Activity Label | Model Class ID | Train Windows (`P_01`) | Test Windows (`P_02`) | Total Windows | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `push_pull` | 0 | 5 | 4 | 9 | Covered |
| `clap` | 2 | 4 | 4 | 8 | Covered |
| `static` | 6 | 4 | 1 | 5 | Covered (Imbalanced) |
| `sit` | 8 | 4 | 6 | 10 | Covered |
| `fall` | 9 | 4 | 4 | 8 | Covered (Deficient: 4 vs 35 target) |
| `walk` | 11 | 4 | 5 | 9 | Covered |
| **Total** | — | **25** | **24** | **49** | **Full Taxonomy Present** |

---

## 4. Deficit Analysis Against Phase 19 Readiness Gates

The Phase 19 split-readiness gate establishes specific empirical thresholds required before participant-independent model evaluation can be considered meaningful:

| Readiness Gate Metric | Phase 19 Pilot Target | Current Verified Count | Attainment | Status | Deficit |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Distinct Participants ($|\mathcal{P}|$)** | $\ge 5$ | 2 (`P_01`, `P_02`) | 40.0% | **UNMET** | -3 participants |
| **3-Way Disjoint Split (Train/Val/Test)** | Supported | Unsupported ($N=2$) | 0.0% | **UNMET** | Requires $N \ge 3$ (pilot $N \ge 5$) |
| **Held-Out Test Fall Windows** | $\ge 35$ | 4 | 11.4% | **UNMET** | -31 windows |
| **Held-Out Test Fall Events** | $\ge 12$ | 2 | 16.7% | **UNMET** | -10 events |
| **Distinct Rooms / Environments** | $\ge 3$ | 1 (`Laboratory_Room1`) | 33.3% | **UNMET** | -2 rooms |
| **Tx-Rx Distance Variations** | $\ge 3$ | 1 (2.5 m) | 33.3% | **UNMET** | -2 distances |
| **Total Physical Sessions** | $\ge 50$ | 23 | 46.0% | **UNMET** | -27 sessions |
| **Total Valid Packets** | $\ge 10,000$ | 3,212 | 32.1% | **UNMET** | -6,788 packets |
| **Total Sliding Windows** | $\ge 150$ | 49 | 32.7% | **UNMET** | -101 windows |

---

## 5. Methodological Consequences of the Deficit

1. **Extreme Metric Variance on Test Falls:**
   With only 4 test fall windows, each window represents $25\%$ of the measured sensitivity:
   $$\text{Recall} \in \{0.00, 0.25, 0.50, 0.75, 1.00\}$$
   A single false negative (e.g., due to Wi-Fi packet drop during the impact spike) drops recall from $100\%$ to $75\%$.
2. **Degrees of Freedom vs. Window Count:**
   The 4 test fall windows derive from only 2 physical fall events ($2\text{ windows/event}$). Because sliding windows within a continuous 4-second recording are autocorrelated, the actual statistical sample size for falls in the test partition is $N_{\text{events}} = 2$.
3. **Absence of Validation Partition:**
   Without a validation partition, any hyperparameter search, learning-rate adjustment, or threshold calibration must either:
   - Overfit the single training subject (`Participant_01`), or
   - Touch the test subject (`Participant_02`), destroying test isolation.
4. **Conclusion:**
   Advancing to model evaluation or comparative retraining under these conditions would violate scientific rigor and produce uninformative metrics.

---

## 6. Readiness Decision for Split Architecture

- **Split Generator Implementation:** **READY** (`backend/app/services/split_generator.py` fully implements 5-participant multi-subject assignment, pairwise zero leakage, and coverage error handling).
- **Physical Dataset Allocation:** **NOT READY** (constrained to $N=2$ participants, 4 held-out fall windows, zero validation partition).
- **Recommendation:** Freeze the 5-participant split design and keep the readiness gate firmly closed until physical recordings for $P_{03}$, $P_{04}$, and $P_{05}$ are collected and validated.
