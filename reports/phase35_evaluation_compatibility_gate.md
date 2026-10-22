# CSIFormer Phase 35 — Five-Class Cross-Room Evaluation Compatibility & Protocol Gate Report

**Date:** October 19, 2026  
**Status:** ALL GATES PASSED (GO FOR SEPARATE EVALUATION PHASE)  
**Author:** Antigravity / CSIFormer Pair Programming Agent  
**Artifact Hash Audits:** Verified Bit-for-Bit Pristine  
**Model Inference / Weight Loading:** NOT PERFORMED  

---

## Executive Summary

Phase 35 establishes the formal compatibility, architectural alignment, preprocessing verification, and evaluation protocol gate for the proposed five-class cross-room feasibility evaluation of CSIFormer.

Using the strict room-held-out and participant-held-out partition established in Phase 34, this phase audited the production (`models/csiformer_phase13_best.pth`) and experimental (`models/csiformer_phase15_adapted.pth`) checkpoints without loading checkpoint weights into instantiated models, without running forward passes or predictions, and without modifying any checkpoint or manifest files.

All software contracts, tensor shapes, channel alignments, and label mappings were confirmed to be 100% compatible. The evaluation protocol is formally specified below prior to any evaluation execution.

---

## Required Final Status Summary

| Gate / Component | Status | Verification Detail |
| :--- | :---: | :--- |
| **Strict Cross-Room Split Reproducibility** | **GO** | Non-mutating generation yields identical 75 train / 20 val / 11 test / 49 excluded accounting. Zero room/subject leakage. |
| **Checkpoint & Preprocessing Compatibility** | **GO** | State dicts verified (140 parameter tensors each). Dual-branch inputs `(50, 56)` match Conv1d kernels. |
| **Five-Class Label Mapping** | **GO** | 1-to-1 unambiguous mapping: `push_pull:0`, `clap:2`, `static:6`, `sit:8`, `walk:11`. Falls (9) strictly excluded. |
| **Evaluation Protocol** | **GO** | Formal pre-specification complete: 12-class unrestricted + 5-class restricted modes, window + session aggregation. |
| **Regression Suite (Targeted)** | **GO** | 6 / 6 tests passed in `backend/tests/test_phase35.py` (100% pass). |
| **Regression Suite (Phases 21–34)** | **GO** | 92 / 92 tests passed across Phases 21–34; combined Phase 21–35 total: 98 / 98 passed (100% pass). |
| **Repository Full Suite** | **GO** | 228 / 228 tests passed across 32 test files (0 failures, 100% pass rate). |
| **Checkpoint Protection Hashes** | **GO** | Both checkpoints bit-for-bit identical to protected MD5 reference hashes. |
| **Model Inference / Evaluation** | **NOT PERFORMED** | Zero inference forward passes, zero weight loading into model, zero training/adaptation performed. |

---

## Task 1 — Strict Evaluation Partition Reproduction

The strict evaluation partition was independently verified using the non-mutating path `ParticipantIndependentSplitGenerator.generate_strict_cross_room_split(output_manifest_path=None)` on `data/real_csi_dataset/dataset_manifest.json`.

### 1.1 Complete Partition Accounting

| Partition Split | Assigned Participants | Physical Room(s) | Sessions | Frames | Sliced Windows (50-frame) | Target Activity Coverage |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Train** | `Participant_01`, `Participant_03`, `Participant_04` | `Laboratory_Room1` | 36 | 5,051 | 75 | 15 static, 15 sit, 16 walk, 14 clap, 15 push_pull |
| **Val** | `Participant_05` | `Laboratory_Room1` | 10 | 1,388 | 20 | 4 static, 4 sit, 4 walk, 4 clap, 4 push_pull |
| **Test** | `Participant_02` | `Office_Room2` | 5 | 714 | 11 | 2 static, 2 sit, 2 walk, 2 clap, 3 push_pull |
| **Excluded** | `Participant_01` (Office_Room2), `Participant_02` (Lab), Fall sessions | `Office_Room2`, `Laboratory_Room1` | 23 | 3,254 | 49 | 5 static, 11 sit, 9 walk, 8 clap, 8 push_pull, 8 fall |
| **Total Dataset** | All 5 Participants | Both Rooms | **74** | **10,407** | **155** | Complete dataset preservation |

### 1.2 Isolation Invariants Confirmed

1. **Zero Room Leakage:**
   - Training room set: `{'Laboratory_Room1'}`. Zero `Office_Room2` sessions in train.
   - Validation room set: `{'Laboratory_Room1'}`. Zero `Office_Room2` sessions in val.
   - Test room set: `{'Office_Room2'}` exclusively.
2. **Zero Subject Leakage:**
   - Training participant set: `{'Participant_01', 'Participant_03', 'Participant_04'}`. Zero `Participant_02` sessions in train.
   - Validation participant set: `{'Participant_05'}`. Zero `Participant_02` sessions in val.
   - Test participant set: `{'Participant_02'}` exclusively.
3. **Session and Window Disjointness:**
   - Zero event ID overlap: `Train ∩ Test = ∅`, `Train ∩ Val = ∅`, `Val ∩ Test = ∅`.
   - Zero sliding window boundary crossing across partitions.
4. **Target Activity Completeness:**
   - All five target activities (`static`, `sit`, `walk`, `clap`, `push_pull`) are represented in train, val, and test.
5. **Exact Test Windows Extracted:**
   Using the production sliding-window extractor (50 frames per window, non-overlapping step 50, all finite, shape `(50, 56)`):
   - `phase16_real_static_Participant_02_1792404586_1792404586` (142 frames) -> **2 windows** (frames 0–50, 50–100)
   - `phase16_real_sit_Participant_02_1792404619_1792404619` (139 frames) -> **2 windows** (frames 0–50, 50–100)
   - `phase16_real_walk_Participant_02_1792404736_1792404736` (141 frames) -> **2 windows** (frames 0–50, 50–100)
   - `phase16_real_clap_Participant_02_1792404793_1792404793` (142 frames) -> **2 windows** (frames 0–50, 50–100)
   - `phase16_real_push_pull_Participant_02_1792404825_1792404825` (150 frames) -> **3 windows** (frames 0–50, 50–100, 100–150)
   - **Total Test Windows = 11 windows** reproduced exactly.
6. **Immutability:**
   - `data/real_csi_dataset/dataset_manifest.json` on disk was not modified during the non-mutating call.

---

## Task 2 — Checkpoint and Model Compatibility Audit

Inspection was conducted directly on checkpoint state dict metadata without instantiating or loading weights into model objects.

### 2.1 Model Architecture Expected by Checkpoints

Both checkpoints (`csiformer_phase13_best.pth` and `csiformer_phase15_adapted.pth`) share the identical architectural parameter structure of `CSIDualBranchFusionNet`:

```
CSIDualBranchFusionNet(
  num_subcarriers=56,
  doppler_bins=56,
  seq_len=50,
  num_classes=12,
  embed_dim=128,
  nhead=8,
  num_layers=3,
  dim_feedforward=512,
  dropout=0.1,
  fusion_mode='gated',
  proj_dim=128
)
```

Each checkpoint contains exactly **140 parameter tensors**:

| Parameter Submodule | Checkpoint Key Example | Tensor Shape | Architectural Role |
| :--- | :--- | :---: | :--- |
| **Branch A (Raw CNN)** | `raw_cnn.conv1.weight` | `torch.Size([128, 56, 3])` | 1D Conv over 56 subcarrier channels along time |
| **Branch A BatchNorm** | `raw_cnn.bn1.weight` | `torch.Size([128])` | Spectral feature normalization |
| **Branch A Spatial Proj** | `raw_spatial_proj.weight` | `torch.Size([128, 128])` | Linear feature projection to embedding dimension |
| **Branch A Positional Enc** | `raw_pos_encoder.pe` | `torch.Size([1, 100, 128])` | Sinusoidal positional encoding up to seq_len=100 |
| **Branch A Transformer** | `raw_transformer.layers.0...` | 3 layers, 8 heads | Temporal self-attention across 50 time steps |
| **Branch A Temporal Pool** | `raw_temporal_pool.attn_net...` | `torch.Size([64, 128])` | Temporal attention-based context pooling |
| **Branch B (Doppler CNN)**| `dopp_cnn.conv1.weight` | `torch.Size([128, 56, 3])` | 1D Conv over 56 Doppler bins along time |
| **Branch B Positional Enc** | `dopp_pos_encoder.pe` | `torch.Size([1, 100, 128])` | Sinusoidal positional encoding up to seq_len=100 |
| **Branch B Transformer** | `dopp_transformer.layers.0...` | 3 layers, 8 heads | Temporal self-attention over kinematic spectrogram |
| **Branch B Temporal Pool** | `dopp_temporal_pool.attn_net...`| `torch.Size([64, 128])` | Kinematic context pooling |
| **Gated Fusion Network** | `gate_dense.0.weight` | `torch.Size([128, 256])` | Learnable gated weighting between Raw and Doppler |
| **Gated Fusion Output** | `gate_dense.3.weight` | `torch.Size([128, 128])` | Gating sigmoid projection |
| **Activity Head (12-class)**| `activity_head.0.weight` | `torch.Size([64, 128])` | Linear projection (128 -> 64) |
| **Activity Head Logits** | `activity_head.3.weight` | `torch.Size([12, 64])` | Final 12-class classification logits |
| **Activity Head Bias** | `activity_head.3.bias` | `torch.Size([12])` | Class biases |
| **Presence Head** | `presence_head.2.weight` | `torch.Size([1, 32])` | Binary presence detection |
| **Motion Head** | `motion_head.2.weight` | `torch.Size([1, 32])` | Binary motion intensity detection |
| **Projection Head** | `proj_head.2.weight` | `torch.Size([128, 128])` | Contrastive feature representation (Phase 13.3) |

### 2.2 Expected Input Dimensions & Tensor Layout

- **Branch A (Raw CSI):**
  - Shape: `[Batch, TimeSteps=50, Channels=56]`
  - Normalization: Per-window temporal z-score normalization:
    $$norm\_raw = \frac{w - \mu_t(w)}{\sigma_t(w) + 10^{-6}}$$
  - Subcarriers: 56 HT20 OFDM subcarriers (indices aligned with ESP32-S3 hardware stream).
- **Branch B (Doppler Spectrogram):**
  - Shape: `[Batch, TimeSteps=50, DopplerBins=56]`
  - STFT computation: Computed dynamically per window via `PhysicsCSIPreprocessor.compute_doppler_spectrogram(w)` or `CalibratedPhysicsPreprocessor`.
  - Log-power spectrum resampled via 2D spline interpolation to fixed grid `(50, 56)`.
  - Z-score normalized per spectrogram.

### 2.3 Twelve-Class Model Taxonomy vs. Five-Class Dataset Alignment

The model's native `DEFAULT_CLASSES` taxonomy in `CSIDualBranchFusionNet` comprises 12 classes:

```
Index  0: Push&Pull
Index  1: Sweep
Index  2: Clap
Index  3: Slide
Index  4: Draw-O
Index  5: Draw-Zigzag
Index  6: box       (Historical baseline alias for static)
Index  7: circle
Index  8: clean     (Historical baseline alias for sit)
Index  9: fall      (Life-safety fall class)
Index 10: run
Index 11: walk
```

The five target activities present in the physical real-world test partition map to the model's output space as follows:

| Physical Activity | Manifest `activity_label` | Manifest `class_id` | Model Logit Index | Model Taxonomy Label | Mapping Status |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Push & Pull** | `push_pull` | `0` | `0` | `Push&Pull` | **1-to-1 Exact** |
| **Clap** | `clap` | `2` | `2` | `Clap` | **1-to-1 Exact** |
| **Static / Torso Still** | `static` | `6` | `6` | `box` (alias `Static`) | **1-to-1 Exact** |
| **Sit Down** | `sit` | `8` | `8` | `clean` (alias `Sit`) | **1-to-1 Exact** |
| **Walk** | `walk` | `11` | `11` | `walk` | **1-to-1 Exact** |

**Excluded Class:**
- `fall` (`class_id: 9`) is present in the training set and model taxonomy, but is **strictly excluded** from the Phase 35 five-class evaluation protocol due to ethical/safety constraints (zero physical falls recorded for Participant_02).

**Compatibility Finding:**
No remapping, permutation, or weight modification is required. The five test activities correspond directly to logit indices `[0, 2, 6, 8, 11]`.

### 2.4 Preprocessing and Scaler Consistency

- Preprocessing during Phase 13 training and Phase 15 adaptation relied exclusively on **sample-local instance normalization** (temporal z-score per 50-frame window).
- No global dataset mean/standard deviation file, `StandardScaler` pickle, or external label encoder artifact is required or expected.
- Both `PhysicsCSIPreprocessor` and `CalibratedPhysicsPreprocessor` are present in `backend/app/services/` and `scratch/` and operate deterministically on raw amplitude matrices of shape `(50, 56)`.

---

## Task 3 — Formal Five-Class Cross-Room Evaluation Protocol Specification

To prevent retrospective data fitting or unscientific adjustments, the evaluation protocol is strictly pre-defined below prior to accessing any model predictions.

### 3.1 Evaluation Scope & Limitations Disclaimer

> [!IMPORTANT]
> **Small Feasibility Study Disclaimer:**
> The five test sessions and 11 windows represent an initial feasibility probe evaluating cross-room generalization to an unseen subject (`Participant_02`) in an unseen room (`Office_Room2`).
> This evaluation does **NOT** constitute a statistically conclusive benchmark of room invariance, and does **NOT** evaluate fall detection performance.
> Generalization claims must be bounded strictly by the empirical sample size (N = 11 windows, N = 5 sessions).

### 3.2 Target Models Under Evaluation

1. **Production Model (`Checkpoint A`):**  
   - File: `models/csiformer_phase13_best.pth` (MD5: `383b4d98c08f8970b0443738f170ec01`)
   - Preprocessor: Standard `PhysicsCSIPreprocessor` (Carrier: 2.442 GHz, Rate: 35.58 Hz).
2. **Experimental Model (`Checkpoint B`):**  
   - File: `models/csiformer_phase15_adapted.pth` (MD5: `ab3d97a04d78edf75d807178772bc828`)
   - Preprocessor: `CalibratedPhysicsPreprocessor` (subcarrier DC notch filtering + dynamic noise thresholding).

### 3.3 Dual Inference Modes

Because the model natively produces 12-class logits, the evaluation must report results under **two distinct, complementary evaluation modes**:

#### Mode 1: 12-Class Unrestricted Argmax (Primary Scientific Mode)
- **Mathematical Form:**
  $$\hat{y}_{unrestricted} = \arg\max_{c \in \{0, \dots, 11\}} z_c$$
- **Error Accounting:**
  If the model predicts any of the 7 out-of-set classes (e.g., class 1 `Sweep`, class 3 `Slide`, class 9 `fall`, etc.), it is scored as an **incorrect prediction** (False Negative for the true class).
- **Purpose:**
  Unbiased test of whether the model maintains selectivity in a new environment or suffers false alarms into unused classes.

#### Mode 2: 5-Class Restricted Sub-Logits (Diagnostic Mode)
- **Mathematical Form:**
  $$\hat{y}_{restricted} = \mathcal{C}_{target}\left[\arg\max_{k \in \{0, \dots, 4\}} z_{\mathcal{C}_{target}[k]}\right], \quad \mathcal{C}_{target} = [0, 2, 6, 8, 11]$$
- **Purpose:**
  Forces the model to choose among the five plausible physical activities. Clarifies whether errors in Mode 1 stem from slight logit competition with unused classes or genuine confusion among target motions.

### 3.4 Aggregation Levels & Metrics

Both Window-Level and Session-Level metrics must be computed and reported:

#### Window-Level Metrics (N = 11)
- **Overall Accuracy:** $\frac{1}{11} \sum_{i=1}^{11} \mathbb{I}(y_i = \hat{y}_i)$
- **Balanced Accuracy:** Macro-averaged recall across the 5 target classes.
- **Per-Class Metrics:** Precision, Recall, F1-Score, and Support for each of the 5 classes.
- **Confusion Matrix:** $5 \times 5$ (Mode 2) and $5 \times 12$ / $12 \times 12$ (Mode 1).

#### Session-Level Metrics (N = 5)
- **Majority-Vote Prediction:** For each of the 5 sessions, the session prediction is the majority class among its constituent windows:
  $$\hat{Y}_{session} = \text{mode}(\{\hat{y}_{w_1}, \hat{y}_{w_2}, \dots\})$$
- **Tie-Breaking Rule:** In the event of a tie (e.g., a 2-window session where window 1 predicts class $A$ and window 2 predicts class $B$):
  $$\hat{Y}_{session} = \arg\max_{c} \left( \frac{1}{2} [P_{w_1}(c) + P_{w_2}(c)] \right)$$
  The class with the higher average softmax probability across the session breaks the tie deterministically.
- **Session Accuracy:** $\frac{1}{5} \sum_{s=1}^5 \mathbb{I}(Y_s = \hat{Y}_s)$
- **Uncertainty & Stability Score:** Report unanimous agreement rate (e.g., $2/2$ vs $1/2$ split) to measure intra-session temporal consistency.

### 3.5 Handling Invalid or Corrupted Windows

- If any window contains NaNs, non-finite values, or incomplete frame lengths, it **must NOT be dropped silently**.
- It must be recorded as an `Invalid Window Failure` and penalized as an incorrect classification ($0$ reward).
- Verified pre-condition: All 11 test windows are $100\%$ finite with verified valid shape $(50, 56)$.

### 3.6 Strict Non-Tuning Constraint

- Zero threshold tuning, preprocessor parameter tweaking, class mapping adjustments, or model hyperparameter modifications are permitted based on test set performance.
- Any observed failures must be reported transparently as empirical findings regarding cross-room domain shift.

---

## Task 4 — Regression and Repository Verification

### 4.1 Summary of Executed Regression Suites

| Suite Group | Description | Files Executed | Tests Run | Passed | Failed | Exit Code | Duration |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Targeted Phase 35** | New compatibility & protocol gate coverage | 1 file | 6 | 6 | 0 | `0` | 10.95s |
| **Phase 21–34 Regression** | Recent dataset, hardware, and split tests | 13 files | 92 | 92 | 0 | `0` | 18.00s |
| **Phases 16–20 & Utilities** | Historical physical collection & integrity suites | 8 files | 78 | 78 | 0 | `0` | 24.70s |
| **Phases 02–14 Baseline** | Early architecture, DSP, and digital twin tests | 10 files | 52 | 52 | 0 | `0` | 34.98s |
| **Total Repository Suite** | Complete regression suite | **32 files** | **228** | **228** | **0** | **`0`** | **88.63s** |

### 4.2 Test Files Executed

1. `backend/tests/test_phase35.py` (6 passed)
2. `backend/tests/test_phase34.py` (6 passed)
3. `backend/tests/test_phase33.py` (6 passed)
4. `backend/tests/test_phase32.py` (6 passed)
5. `backend/tests/test_phase31.py` (5 passed)
6. `backend/tests/test_phase30.py` (5 passed)
7. `backend/tests/test_phase29.py` (6 passed)
8. `backend/tests/test_phase28.py` (6 passed)
9. `backend/tests/test_phase27.py` (8 passed)
10. `backend/tests/test_phase26.py` (7 passed)
11. `backend/tests/test_phase25.py` (7 passed)
12. `backend/tests/test_phase23.py` (5 passed)
13. `backend/tests/test_phase22.py` (8 passed)
14. `backend/tests/test_phase21.py` (17 passed)
15. `backend/tests/test_phase20.py` (10 passed)
16. `backend/tests/test_phase19.py` (10 passed)
17. `backend/tests/test_phase18.py` (12 passed)
18. `backend/tests/test_phase17.py` (12 passed)
19. `backend/tests/test_phase16.py` (10 passed)
20. `backend/tests/test_safe_disconnection.py` (8 passed)
21. `backend/tests/test_sampling_rate_audit.py` (8 passed)
22. `backend/tests/test_training_datasets.py` (8 passed)
23. `backend/tests/test_phase14.py` (10 passed)
24. `backend/tests/test_phase10.py` (16 passed)
25. `backend/tests/test_phase09_dataset_acquisition.py` (5 passed)
26. `backend/tests/test_phase08.py` (5 passed)
27. `backend/tests/test_phase07.py` (3 passed)
28. `backend/tests/test_phase06.py` (4 passed)
29. `backend/tests/test_phase05.py` (2 passed)
30. `backend/tests/test_phase04.py` (3 passed)
31. `backend/tests/test_phase03.py` (2 passed)
32. `backend/tests/test_phase02.py` (2 passed)

**Tests Not Run:** None. All 32 test files in `backend/tests/` were executed and passed.

### 4.3 Git Working Tree Review

- `git status --short` confirms all user data, Phase 33 session files, and modified test suites are intact.
- Diffs in `backend/app/services/split_generator.py` correspond to the Phase 34 addition of `generate_strict_cross_room_split`.
- Zero uncommitted resets, cleanings, or pushes were performed.

---

## Task 5 — Checkpoint Protection & Hash Verification

Before and after all test executions and compatibility audits, both model checkpoints were re-hashed using MD5:

| Model Checkpoint Artifact | Protected Reference MD5 | Computed MD5 | Status |
| :--- | :--- | :--- | :---: |
| **Production Baseline:** `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (BIT-FOR-BIT IDENTICAL)** |
| **Experimental Adapted:** `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (BIT-FOR-BIT IDENTICAL)** |

**Strict Isolation Invariant:**
No checkpoint weights were loaded into an active model instance. No inference forward passes, gradient calculations, or fine-tuning were performed.

---

## Gate Determination & Recommendation

All prerequisites and gating criteria for Phase 35 have been completely satisfied:
1. The strict five-class room-held-out and participant-held-out split is 100% reproducible and leak-free.
2. The checkpoints, preprocessors, input dimensions, and output classes are verified to be structurally and functionally compatible.
3. The evaluation protocol is pre-registered with clear dual-mode evaluation and aggregation rules.
4. The entire test suite of 228 tests across 32 test files passed with 0 failures.
5. Both checkpoints remain bit-for-bit pristine.

**Recommendation:**  
Authorize a subsequent evaluation phase (e.g., Phase 36) to execute model inference strictly following the protocol specified in Task 3.
