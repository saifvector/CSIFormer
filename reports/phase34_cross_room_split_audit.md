# CSIFormer Phase 34 — Independent Cross-Room Split Audit & Evaluation Gate Report

**Execution Date:** October 19, 2026  
**Auditor / Verification Agent:** CSIFormer Autonomous Verification Agent  
**Phase Objective:** Independently verify the Phase 33 recordings on disk and manifest, audit the split-generation mechanisms and code changes, and construct a mathematically and scientifically valid five-class evaluation partition that tests an unseen participant in a physical room completely excluded from training and validation. Maintain strict model freeze (no training, fine-tuning, adaptation, or inference) and preserve protected checkpoints.

---

## 1. Required Final Status Table

| Dimension | Final Status | Empirical / Verifiable Finding |
| :--- | :---: | :--- |
| **Phase 33 Physical Data Integrity** | **GO** | All 5 physical recordings for `Participant_02` in `Office_Room2` @ 2.0 m verified on disk and manifest. 714 frames captured across 5 safe activities (`static`, `sit`, `walk`, `clap`, `push_pull`). Raw 5 complex subcarrier pairs and 56 aligned derived channels verified. 100% manifest-to-disk parity. 0 duplicate IDs. |
| **Current Split Integrity** | **CONDITIONAL GO** | Standard LOSO generator (`generate_loso_split`) correctly partitions by participant without leakage, but because `Participant_01` is assigned to training, `Participant_01`'s five `Office_Room2` sessions are included in training. Calling this naive LOSO split an "unseen room" evaluation is scientifically invalid. |
| **Strict Room-Held-Out Five-Class Partition** | **GO** | Candidate 5-class cross-room partition successfully defined and verified: `Office_Room2` completely excluded from Train and Val; `Participant_02` completely excluded from Train and Val; Test contains only `Participant_02`'s 5 `Office_Room2` sessions (11 windows across 5 classes). All 8 invariants verified with zero leakage. |
| **Model Training / Inference / Evaluation** | **NOT PERFORMED** | Strict model freeze maintained. Neither checkpoint was loaded into memory for training, fine-tuning, adaptation, or inference. |
| **Checkpoint Hashes** | **VERIFIED MATCH** | Production checkpoint MD5: `383b4d98c08f8970b0443738f170ec01` (MATCH).<br>Experimental checkpoint MD5: `ab3d97a04d78edf75d807178772bc828` (MATCH). |
| **Source & Repository Changes** | **REVIEWED** | Implementation diffs in `collection_workflow.py`, `real_csi_collector.py`, `session_validator.py`, and `split_generator.py` audited. Deterministic immutability verified. Zero git reset, clean, commit, or push executed. |

---

## 2. Task 1 — Independent Verification of Phase 33 Physical Data

An independent file-level and byte-level inspection of the dataset was conducted directly against `data/real_csi_dataset/` and `data/real_csi_dataset/dataset_manifest.json`:

### 2.1 Individual Session Verification (`Participant_02` in `Office_Room2` @ 2.0 m)

| Activity | Session ID | Packets | Duration | Empirical Rate | Mean RSSI | Subcarriers (Raw / Derived) | Timestamps Monotonic | Status | Split |
| :--- | :--- | :-: | :-: | :-: | :-: | :-: | :-: | :---: | :---: |
| **`static`** | `phase16_real_static_Participant_02_1792404586_1792404586` | 142 | 4.03 s | 35.28 Hz | -60.0 dBm | 5 (I, Q) / 56 HT20 | YES ($\Delta t > 0$) | confirmed | test |
| **`sit`** | `phase16_real_sit_Participant_02_1792404619_1792404619` | 139 | 4.03 s | 34.58 Hz | -63.0 dBm | 5 (I, Q) / 56 HT20 | YES ($\Delta t > 0$) | confirmed | test |
| **`walk`** | `phase16_real_walk_Participant_02_1792404736_1792404736` | 141 | 4.04 s | 35.04 Hz | -61.0 dBm | 5 (I, Q) / 56 HT20 | YES ($\Delta t > 0$) | confirmed | test |
| **`clap`** | `phase16_real_clap_Participant_02_1792404793_1792404793` | 142 | 4.04 s | 35.30 Hz | -59.0 dBm | 5 (I, Q) / 56 HT20 | YES ($\Delta t > 0$) | confirmed | test |
| **`push_pull`** | `phase16_real_push_pull_Participant_02_1792404825_1792404825` | 150 | 4.02 s | 37.27 Hz | -58.0 dBm | 5 (I, Q) / 56 HT20 | YES ($\Delta t > 0$) | confirmed | test |
| **Total** | **5 Sessions** | **714** | **20.16 s** | **35.49 Hz** | **-60.2 dBm** | **Preserved** | **100% Strict** | **5 / 5** | **test** |

### 2.2 Global Dataset Reconciliation
- **Total Indexed Sessions:** Exactly 74 sessions in `dataset_manifest.json`.
- **Total Physical Frames:** Exactly 10,407 frames.
- **Total Non-Overlapping Windows ($T=50$, stride 50):** Exactly 155 windows.
- **Manifest-to-Disk Coverage:** 100% (all 74 JSON files and 74 CSV files exist on disk with exact frame and row parity).
- **Disk-to-Manifest Coverage:** Exactly 1 isolated unindexed exploratory trial pair exists on disk:
  - `phase14_p15_real_walk_t1_1792303844_1792303844.csv`
  - `phase14_p15_real_walk_t1_1792303844_1792303844.json`
  - Preserved strictly as non-dataset historical evidence; not indexed or deleted.
- **ID Uniqueness:** 74 distinct session IDs, 74 distinct event IDs, 0 duplicate IDs.
- **Validator Assessment:** `DatasetIntegrityValidator.validate_dataset_manifest()` reports `all_sessions_valid = True`.

---

## 3. Task 2 — Audit of Current Split Implementation and Code Changes

### 3.1 Split Generator Side-Effect and Persistence Analysis
Audit of `backend/app/services/split_generator.py`:
1. **Manifest Mutation:** `ParticipantIndependentSplitGenerator.generate_loso_split()` and `generate_strict_cross_room_split()` do **NOT** mutate the manifest in memory. Both methods instantiate `new_manifest = dict(self.manifest)` and duplicate session dictionaries before assigning split labels.
2. **Disk Persistence:** Neither method writes to disk unless `output_manifest_path: Optional[Path]` is explicitly provided as a non-None path. When called without an output path, split generation is completely non-mutating and returns an in-memory dictionary.
3. **Persisted Manifest on Disk:** The physical file `data/real_csi_dataset/dataset_manifest.json` preserves the collection-time split tags (58 train, 6 val, 10 test). It has not been overwritten by dynamic split generation.

### 3.2 The "Unseen Room" Methodological Caveat
Audit of `Participant_01` in `Office_Room2`:
- In the real dataset manifest on disk, all 5 of `Participant_01`'s `Office_Room2` recordings carry `"split": "train"`.
- When standard participant-independent LOSO is invoked with `test_participant="Participant_02"`:
  - Training participants: `Participant_01`, `Participant_03`, `Participant_04`.
  - Because `Participant_01` is assigned to training, `Participant_01`'s five sessions in `Office_Room2` are included in the training partition.
  - As a result, the neural network would observe RF propagation features from `Office_Room2` during training.
- **Methodological Rule:** An evaluation of `Participant_02` in `Office_Room2` under standard LOSO **CANNOT** be claimed as an "unseen room generalization evaluation". It only evaluates subject-independence within a previously seen room.
- To evaluate genuine generalization to an unseen physical room, `Office_Room2` must be strictly excluded from both training and validation.

---

## 4. Task 3 — Definition & Mathematical Verification of the Five-Class Cross-Room Partition

To establish a scientifically rigorous test on an unseen participant in an unseen physical environment, the 8 mandatory invariants were formalized and implemented in `ParticipantIndependentSplitGenerator.generate_strict_cross_room_split()`:

### 4.1 Partition Specification

```text
Total Dataset: 74 sessions (10,407 frames, 155 windows @ T=50)
├── Active Partition (51 sessions, 7,153 frames, 106 windows)
│   ├── TRAIN: 36 sessions, 5,051 frames, 75 windows (P01, P03, P04 | Laboratory, Laboratory_Room1)
│   ├── VAL:   10 sessions, 1,388 frames, 20 windows (P05 | Laboratory)
│   └── TEST:   5 sessions,   714 frames, 11 windows (P02 | Office_Room2)
└── Excluded Partition (23 sessions, 3,254 frames, 49 windows)
    ├── Office_Room2 sessions from P01: 5 sessions, 696 frames, 10 windows (preserves unseen room)
    ├── Non-Office_Room2 sessions from P02: 16 sessions, 2,278 frames, 35 windows (preserves unseen subject)
    └── Fall sessions from P01: 2 sessions, 280 frames, 4 windows (preserves 5-class protocol)
```

### 4.2 Activity Window Breakdown Across Partitions

| Partition | `static` | `sit` | `walk` | `clap` | `push_pull` | `fall` | Total Windows | Total Frames | Sessions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TRAIN** (`P01`, `P03`, `P04`) | 15 | 15 | 16 | 14 | 15 | 0 (excl.) | **75** | 5,051 | 36 |
| **VAL** (`P05`) | 4 | 4 | 4 | 4 | 4 | 0 (excl.) | **20** | 1,388 | 10 |
| **TEST** (`P02` in `Office_Room2`) | 2 | 2 | 2 | 2 | 3 | 0 (excl.) | **11** | 714 | 5 |
| **EXCLUDED** (All non-eligible) | 5 | 11 | 9 | 8 | 8 | 8 | **49** | 3,254 | 23 |
| **GLOBAL TOTAL** | **26** | **32** | **31** | **28** | **30** | **8** | **155** | **10,407** | **74** |

### 4.3 Invariants Verification Checklist
1. **Zero `Office_Room2` in Training:** Verified. `train_rooms = {'Laboratory', 'Laboratory_Room1'}`.
2. **Zero `Office_Room2` in Validation:** Verified. `val_rooms = {'Laboratory'}`.
3. **Test Contains ONLY `Participant_02` in `Office_Room2`:** Verified. Exactly 5 sessions, 11 windows.
4. **Zero `Participant_02` in Training or Validation:** Verified. `P02` is completely held out.
5. **Zero Leakage:** Disjoint participant sets ($\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$), disjoint session IDs, disjoint event IDs, and disjoint non-overlapping window segments.
6. **Class Coverage:** All 5 safe ordinary classes represented in Train (14–16 windows/class), Val (exactly 4 windows/class), and Test (2–3 windows/class).
7. **Complete Window Accounting:** Exactly 75 train + 20 val + 11 test + 49 excluded = 155 windows. Every window accounted for.
8. **Fall Detection Excluded:** All 8 fall windows (4 sessions) are quarantined in the excluded partition.

### 4.4 Statistical Significance Disclaimer
> [!NOTE]
> **Sample Size & Statistical Scope:** The test partition comprises 5 physical recording sessions yielding 11 non-overlapping windows ($T=50$). While mathematically rigorous and completely free of leakage, this partition constitutes a small-sample **preliminary feasibility study** rather than a large-scale statistical benchmark. Results from evaluating this test set should be reported with explicit confidence bounds and should not be overstated as generalized production validation.

---

## 5. Task 4 — Test Split Integrity Without Training

A dedicated test module was created in [backend/tests/test_phase34.py](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase34.py) covering all audit objectives:

1. `test_phase34_checkpoint_invariance`: Bit-for-bit MD5 verification of Phase 13 and Phase 15 checkpoints without model initialization.
2. `test_phase34_phase33_physical_data_verification`: Complete physical file verification on disk (packet counts, timestamps monotonicity, empirical rates, raw subcarriers, 56 aligned channels).
3. `test_phase34_manifest_split_audit_and_unseen_room_caveat`: Audits baseline manifest and verifies that standard LOSO assigns `Participant_01`'s `Office_Room2` sessions to training.
4. `test_phase34_strict_cross_room_split_invariants`: Tests all 8 invariants on the candidate partition (zero room leakage, zero participant leakage, exact window counts).
5. `test_phase34_split_generator_determinism_and_immutability`: Verifies repeated calls return identical dicts, do not mutate input, do not write to disk unless path is passed, and pass temporary-fixture write checks.
6. `test_phase34_insufficient_class_coverage_enforcement`: Asserts that `InadequateClassCoverageError` is raised if any class is missing from test, train, or val.

---

## 6. Task 5 — Checkpoint Protection & Regression Suite Results

### 6.1 Checkpoint MD5 Hash Audit
Both checkpoints were verified via byte-level MD5 hashing without model initialization or execution:

| Model Checkpoint | Expected MD5 Reference | Measured MD5 Hash | Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |

### 6.2 Regression Test Execution Report

Command executed:
```powershell
py -3.11 -m pytest `
  backend/tests/test_phase21.py `
  backend/tests/test_safe_disconnection.py `
  backend/tests/test_sampling_rate_audit.py `
  backend/tests/test_phase30.py `
  backend/tests/test_phase31.py `
  backend/tests/test_phase32.py `
  backend/tests/test_phase33.py `
  backend/tests/test_phase34.py -v
```

Execution Results:
- **Exit Code:** `0`
- **Total Test Cases Executed:** `61`
- **Passed:** `61` (100%)
- **Failed:** `0`
- **Warnings:** None
- **Duration:** `20.31 seconds`

### 6.3 Repository Diff & Working Tree State
- **`git diff --stat`:** Audited 13 modified files (including services and tests); zero core model checkpoints or binary weights altered.
- **`git status --short`:** Verified all untracked files are preserved (Phase 16–33 session files, reports, and scratch audit scripts).
- **Git Commit/Push Policy:** Strictly maintained. Zero git commits, zero git pushes, and zero git resets were executed.

---

## 7. Phase 34 Conclusion & Evaluation Gate Status

1. **Independent Verification Complete:** Phase 33 data acquisition is fully verified on disk and manifest. All 5 sessions for `Participant_02` in `Office_Room2` are valid physical recordings.
2. **Methodological Caveat Documented:** Standard LOSO includes `Participant_01` in training, which invalidates claims of an "unseen room".
3. **Strict Evaluation Partition Established:** The newly developed `generate_strict_cross_room_split()` enforces complete room and participant isolation, providing 75 training windows, 20 validation windows, and 11 cross-room test windows across 5 balanced classes.
4. **Evaluation Gate Status:** The cross-room evaluation partition is mathematically and empirically ready. Model training, inference, and evaluation remain **NOT PERFORMED** awaiting explicit operator authorization.
