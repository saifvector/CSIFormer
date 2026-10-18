# CSIFormer Phase 17 — Participant-Independent Split Validation Report

## Executive Summary

Phase 17 designs, implements, and rigorously evaluates a reproducible **Participant-Independent (Leave-One-Subject-Out / LOSO) Dataset Split Generator** (`backend/app/services/split_generator.py`). In Phase 15 and Phase 16, model evaluations were conducted on a 12-train / 6-validation / 5-test partition that split by recording sessions rather than by participants. Because both `Participant_01` and `Participant_02` were present across all three splits, model weights were exposed to the physical biometric RF signatures of the test subjects during training, creating cross-subject leakage.

This report validates the new LOSO generator against the real ESP32-S3 dataset, demonstrates strict rejection of 3-way splits when fewer than 3 subjects exist, verifies zero leakage in a 2-way LOSO partition, and analyzes class representation on unseen participants.

---

## 1. Split Architecture & Anti-Leakage Constraints

The `ParticipantIndependentSplitGenerator` enforces five strict invariant properties:
1. **Zero Participant Overlap:** No participant identity may appear in more than one partition ($\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$).
2. **Zero Window Overlap Across Splits:** Overlapping sliding windows (stride: 25, size: 50) must never span session boundaries or partition boundaries.
3. **Session Invariance:** All frames and windows belonging to a physical recording session are kept intact within the assigned split.
4. **Explicit Failure on Insufficient Subjects:** If a 3-way split is requested on a dataset with $N < 3$ participants, the generator strictly raises `InsufficientParticipantsError`. It never silently degrades to random or session-only splitting.
5. **Class Balance & Coverage Audit:** The generator computes class-level window counts per partition and explicitly lists any classes absent from the test set (`missing_in_test`).

---

## 2. Participant Breakdown of the Current Dataset

Inspection of `data/real_csi_dataset/dataset_manifest.json` reveals the following physical distribution:

| Participant ID | Sessions | Physical Packets | Extracted Windows | Activity Breakdown (Windows) |
| :--- | :---: | :---: | :---: | :--- |
| `Participant_01` | 12 | 1,655 | 25 | `push_pull`: 5, `clap`: 4, `static`: 4, `sit`: 4, `fall`: 4, `walk`: 4 |
| `Participant_02` | 11 | 1,557 | 24 | `push_pull`: 4, `clap`: 4, `static`: 1, `sit`: 6, `fall`: 4, `walk`: 5 |
| **Total** | **23** | **3,212** | **49** | `push_pull`: 9, `clap`: 8, `static`: 5, `sit`: 10, `fall`: 8, `walk`: 9 |

---

## 3. Mathematical Proof: Infeasibility of 3-Way Independent Splitting at $N=2$

Let $\mathcal{P} = \{p_1, p_2, \dots, p_N\}$ denote the set of distinct human participants.
A 3-way participant-independent split requires three pairwise disjoint, non-empty subsets $\mathcal{P}_{\text{train}}$, $\mathcal{P}_{\text{val}}$, and $\mathcal{P}_{\text{test}}$:
$$\mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{val}} = \emptyset, \quad \mathcal{P}_{\text{train}} \cap \mathcal{P}_{\text{test}} = \emptyset, \quad \mathcal{P}_{\text{val}} \cap \mathcal{P}_{\text{test}} = \emptyset$$
$$\mathcal{P}_{\text{train}} \cup \mathcal{P}_{\text{val}} \cup \mathcal{P}_{\text{test}} \subseteq \mathcal{P}$$
$$|\mathcal{P}_{\text{train}}| \ge 1, \quad |\mathcal{P}_{\text{val}}| \ge 1, \quad |\mathcal{P}_{\text{test}}| \ge 1$$
Therefore:
$$|\mathcal{P}| \ge |\mathcal{P}_{\text{train}}| + |\mathcal{P}_{\text{val}}| + |\mathcal{P}_{\text{test}}| \ge 1 + 1 + 1 = 3$$

In the current dataset, $|\mathcal{P}| = 2$ (`Participant_01` and `Participant_02`). 
Hence, **no 3-way partition can exist without violating the disjointness constraint**. Any claim of a 3-way "Train/Val/Test" split on this dataset necessarily causes participant leakage.

### Generator Error Handling Verification
When calling `generate_loso_split(test_participant="Participant_02", val_participant="Participant_01")`, the generator raises:
```
InsufficientParticipantsError: Cannot create a 3-way participant-independent split (Train/Val/Test) with only 2 participants (['Participant_01', 'Participant_02']). Requires at least 3 distinct participants. Use a 2-way (Train/Test) split or expand the dataset.
```
This confirms that silent fallback has been successfully eliminated.

---

## 4. 2-Way Leave-One-Subject-Out (LOSO) Partitioning

Because $N=2$, the only valid participant-independent topology is a **2-way split**:
- **Training Set ($\mathcal{P}_{\text{train}}$):** `Participant_01`
- **Validation Set ($\mathcal{P}_{\text{val}}$):** $\emptyset$ (0 sessions, 0 windows)
- **Held-Out Test Set ($\mathcal{P}_{\text{test}}$):** `Participant_02`

The generator saved this versioned split to `data/real_csi_dataset/dataset_manifest_p17_loso.json`.

### 4.1 Split Distribution Summary
```json
{
  "train_sessions": 12,
  "val_sessions": 0,
  "test_sessions": 11,
  "train_windows": 25,
  "val_windows": 0,
  "test_windows": 24,
  "total_sessions": 23,
  "total_windows": 49
}
```

### 4.2 Class Representation & Coverage
| Activity Label | Model Class ID | Train Windows (`Participant_01`) | Test Windows (`Participant_02`) | Total Windows | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `push_pull` | 0 | 5 | 4 | 9 | Covered |
| `clap` | 2 | 4 | 4 | 8 | Covered |
| `static` | 6 | 4 | 1 | 5 | Covered (Imbalanced) |
| `sit` | 8 | 4 | 6 | 10 | Covered |
| `fall` | 9 | 4 | 4 | 8 | Covered (Low Count) |
| `walk` | 11 | 4 | 5 | 9 | Covered |
| **All Classes** | — | **25** | **24** | **49** | **Full Taxonomy Covered** |

- **Missing Classes in Test:** None (`missing_in_test: []`). All 6 activities are present in both the training subject and the test subject.
- **Class Imbalance:** In the test set, `static` has only 1 window, while `sit` has 6 windows. In the training set, activities range from 4 to 5 windows.

---

## 5. Held-Out Fall Test Windows vs. Pilot Milestone

The primary metric established in Phase 16 for evaluating fall detection reliability is the count of unseen fall test windows:

$$\text{Test Fall Windows Available} = 4$$
$$\text{Phase 16 Target Milestone} = 35$$
$$\text{Milestone Attainment} = \frac{4}{35} = 11.4\%$$

### Critical Scientific Assessment:
1. **Improvement Over Phase 16:** In the Phase 16 random session split, the test split contained only **2 fall windows** (both from sessions that leaked participant identities). Under the new 2-way LOSO split, the held-out test participant (`Participant_02`) contains **4 fall windows**, and they are completely free of participant leakage.
2. **Deficit Remaining:** 4 fall windows is statistically insufficient to compute a credible confidence interval for sensitivity. A single misclassified window shifts observed sensitivity by 25.0%.
3. **No Retraining Mandate:** As mandated by Phase 17 engineering constraints, the model will not be fine-tuned or evaluated until the dataset is expanded to include $\ge 3$ participants and $\ge 35$ held-out fall windows.
