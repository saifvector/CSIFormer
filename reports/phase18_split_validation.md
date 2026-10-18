# CSIFormer Phase 18 — Participant-Independent Split Validation Report

## Executive Summary

This report establishes the validation and architectural invariants of the **Participant-Independent (Leave-One-Subject-Out / LOSO) Dataset Split Generator** (`backend/app/services/split_generator.py`) in Phase 18. Historical evaluations in Phase 15 and Phase 16 partitioned data by session ID rather than by participant ID, causing the biometric RF signatures of test subjects to leak into training and validation sets.

Phase 18 extends the split generator to support multi-subject assignments (e.g. 3 Train, 1 Val, 1 Test for 5 subjects), enforces event-level grouping, and introduces strict class-coverage error handling (`InadequateClassCoverageError`).

---

## 1. Partition Design & Anti-Leakage Invariants

The `ParticipantIndependentSplitGenerator` enforces five strict invariant rules:
1. **Zero Participant Overlap (Subject Invariance):**
   $$\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{val}} = \emptyset, \quad \mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset, \quad \mathcal{P}_{\text{val}} \cap \mathcal{P}_{\text{test}} = \emptyset$$
   Participant identities determine split boundaries. Window counts or session counts are never used to balance partitions if doing so splits a participant's data across partitions.
2. **Event & Session Invariance:**
   All frames, sliding windows, and sessions belonging to a specific movement event (`event_id`) remain strictly within the assigned participant's partition:
   $$\mathcal{E}_{\text{train}} \cap \mathcal{E}_{\text{test}} = \emptyset$$
3. **Temporal Window Isolation:**
   Sliding windows (size: 50 frames, stride: 50) are constructed strictly within session boundaries. No window is permitted to bridge two different sessions or two different splits.
4. **Explicit Failure on Insufficient Subjects:**
   If a 3-way partition ($\text{Train} / \text{Val} / \text{Test}$) is requested on a dataset with fewer than 3 participants ($|\mathcal{P}| < 3$), the generator raises `InsufficientParticipantsError`. It never silently falls back to random session splitting.
5. **Class Coverage Verification:**
   The generator verifies whether all activity classes present in the training partition are represented in the test partition (`missing_in_test`). If `strict_coverage=True` and any class (or the safety-critical `fall` class) is absent, `InadequateClassCoverageError` is raised.

---

## 2. Theoretical 5-Participant Pilot Split vs. Current Reality

### 2.1 Theoretical 5-Participant Design
When the dataset is expanded to five distinct subjects ($\mathcal{P} = \{P_{01}, P_{02}, P_{03}, P_{04}, P_{05}\}$), the recommended pilot allocation is:
- **Training Partition ($\mathcal{P}_{\text{train}}$):** 3 participants ($P_{01}, P_{02}, P_{03}$) — provides intra-class movement diversity across body builds and kinematic cadences.
- **Validation Partition ($\mathcal{P}_{\text{val}}$):** 1 participant ($P_{04}$) — used strictly for early stopping and hyperparameter monitoring without test leakage.
- **Held-Out Test Partition ($\mathcal{P}_{\text{test}}$):** 1 participant ($P_{05}$) — frozen completely prior to model evaluation. Test results must never be used to tune preprocessing thresholds or architecture parameters.

### 2.2 Current Dataset Constraint ($N=2$)
In the actual repository dataset, $|\mathcal{P}| = 2$ (`Participant_01` and `Participant_02`).
As proven mathematically in Phase 17, a 3-way partition requires at least 3 disjoint non-empty sets ($|\mathcal{P}| \ge 1 + 1 + 1 = 3$).
Calling `generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")` immediately triggers:
```
InsufficientParticipantsError: Cannot create a 3-way participant-independent split (Train/Val/Test) with only 2 participants (['Participant_01', 'Participant_02']). Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset.
```

---

## 3. Audited 2-Way Leave-One-Subject-Out (LOSO) Split Analysis

Because $|\mathcal{P}| = 2$, the only leakage-free participant-independent partition possible is a **2-way split**:
- **Training Split ($\mathcal{P}_{\text{train}}$):** `Participant_01`
- **Validation Split ($\mathcal{P}_{\text{val}}$):** $\emptyset$ (0 sessions, 0 windows)
- **Held-Out Test Split ($\mathcal{P}_{\text{test}}$):** `Participant_02`

This partition is stored in [`data/real_csi_dataset/dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json).

### 3.1 Partition Distribution
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

### 3.2 Class Coverage Breakdown
| Activity Label | Model Class ID | Train Windows (`Participant_01`) | Test Windows (`Participant_02`) | Total Windows | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `push_pull` | 0 | 5 | 4 | 9 | Fully Covered |
| `clap` | 2 | 4 | 4 | 8 | Fully Covered |
| `static` | 6 | 4 | 1 | 5 | Fully Covered (Imbalanced) |
| `sit` | 8 | 4 | 6 | 10 | Fully Covered |
| `fall` | 9 | 4 | 4 | 8 | Fully Covered (Low Count) |
| `walk` | 11 | 4 | 5 | 9 | Fully Covered |
| **All Classes** | — | **25** | **24** | **49** | **Full Taxonomy Covered** |

- **Missing in Test:** None (`missing_in_test: []`). All 6 classes are present in both training and test subjects.
- **Event-Level Isolation:** Zero overlap between the 12 training events and the 11 test events.

---

## 4. Held-Out Fall Event & Window Limitations

The primary objective of CSIFormer fall detection evaluation is to verify sensitivity on unseen subjects. Under the clean 2-way LOSO partition:
- **Test Fall Events:** 2 discrete physical trials.
- **Test Fall Windows:** 4 sliding windows ($1.40\text{ s}$ duration each).
- **Phase 18 Pilot Target:** $\ge 35$ held-out fall windows across $\ge 12$ distinct events.
- **Attainment:**
  $$\text{Fall Window Attainment} = \frac{4}{35} = 11.4\% \quad (\text{Deficit: } 31\text{ windows})$$
  $$\text{Fall Event Attainment} = \frac{2}{12} = 16.7\% \quad (\text{Deficit: } 10\text{ events})$$

### Statistical Implications:
1. **Extreme Metric Instability:** With only 4 test windows, a single false negative causes measured recall to collapse from 100% to 75%.
2. **Event Autocorrelation:** The 4 test windows originate from only 2 physical events. Consecutive overlapping windows from the same fall trial do not represent statistically independent degrees of freedom.
3. **No Validation Split:** Because $N=2$, the validation set has 0 samples. Hyperparameter selection, checkpoint selection, or threshold tuning cannot be performed without either contaminating the test set or overfitting the single training subject.

---

## 5. Automated Split Integrity Verification

Automated unit tests in `backend/tests/test_phase18.py` verify that:
1. `test_loso_participant_and_event_isolation`: Asserts that `train_participants.intersection(test_participants) == set()` and `train_events.intersection(test_events) == set()`.
2. `test_insufficient_participants_3way_error`: Asserts that `generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")` raises `InsufficientParticipantsError`.
3. `test_inadequate_class_coverage_strict_mode`: Asserts that when a test split lacks a class, `InadequateClassCoverageError` is raised under `strict_coverage=True`.
4. `test_multi_participant_split_allocation`: Verifies that passing participant lists (e.g., 3 train, 1 val, 1 test on mock manifests) correctly assigns splits without cross-contamination.
