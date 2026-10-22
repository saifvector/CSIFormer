# CSIFormer Phase 40 — Small-Sample Baseline Feasibility Study Report

**Date:** October 19, 2026  
**Status:** COMPLETED — BASELINE UNSTABLE & UNINFORMATIVE (DATA DEFICIT CONFIRMED)  
**Author:** Antigravity / CSIFormer Pair Programming Agent  
**Gate 4 Decision:** **BASELINE UNSTABLE OR UNINFORMATIVE — STOP MODEL DEVELOPMENT & RECOMMEND SYSTEMATIC DATA COLLECTION**  
**Protected Checkpoints:** Bit-for-Bit Pristine (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`)  
**Production Checkpoint Promotion:** **NOT PERFORMED** (No Checkpoint Created)  
**Held-Out Test Set (`Participant_02` in `Office_Room2`):** **ZERO INFERENCE EXECUTED** (100% Isolated & Unpeaked)  

---

## 1. Executive Summary

Phase 40 was chartered to conduct a disciplined small-sample baseline feasibility study on the existing real ESP32-S3 CSI dataset. The primary objective was to determine whether a low-capacity, transparent five-class baseline (`push_pull`, `clap`, `walk`, `static`, `sit`) could establish credible activity discrimination before investing in more complex deep learning or additional data collection.

Phase 39 halted before retraining `CSIDualBranchFusionNet` due to extreme parameter-to-sample disparity (1.48M parameters vs. 75 training windows, ratio 19,766:1) and empirical proof of catastrophic memorization (100% train accuracy with validation loss exploding to 2.47). Phase 40 evaluated whether this failure was merely an artifact of deep Transformer overparameterization or a fundamental reflection of physical data insufficiency.

### Key Conclusions & Decisions:

1. **Reconciliation of Split & Fall Window Counts (Gate 0 Passed):**
   - The global manifest ([`data/real_csi_dataset/dataset_manifest.json`](file:///C:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json)) contains exactly **74 sessions, 10,407 frames, and 155 windows** ($T=50$, stride 50).
   - Slicing into non-overlapping 50-frame windows strictly yields: **75 train, 20 val, 11 test, and 49 excluded windows** (with 2,657 dropped remainder frames).
   - The historical fall window discrepancy was forensically reconciled: the entire dataset has exactly **4 fall sessions (561 frames, 8 windows total)**. In historical 2-way LOSO (Phases 17–21), only 4 fall windows were in test (`Participant_02`) and 4 in train (`Participant_01`). In Phase 34, all 4 fall sessions (8 windows) were quarantined into the excluded partition.
2. **Preprocessing Contract Validated (Gate 1 Passed):**
   - The distinction between 5 physically measured subcarrier pairs and 56 linearly interpolated channels is verified.
   - Preprocessing parity between offline window extraction and [`LivePipelineService.predict_latest_window()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) was confirmed. All feature transformations and scalers were fitted **strictly on training data**.
3. **Transparent Baseline Evaluation (Gates 2 & 3 Completed):**
   - Evaluated 4 baseline families on the frozen training partition (75 windows) and evaluated on the frozen validation partition (20 windows across `Participant_05`):
     - **Majority-Class Baseline:** Predicts `walk`. Validation Accuracy: **20.0%**, Validation Macro-F1: **0.0667**.
     - **Regularized Logistic Regression (L2, $C=0.1, 1.0$):** Validation Accuracy: **15.0% – 30.0%**, Validation Macro-F1: **0.1197 – 0.3284**.
     - **Random Forest (100 trees, max_depth=4):** Validation Accuracy: **15.0% – 30.0%**, Validation Macro-F1: **0.1416 – 0.2905**.
     - **Support Vector Machine (RBF & Linear kernels):** Validation Accuracy: **5.0% – 25.0%**, Validation Macro-F1: **0.0444 – 0.2633**.
     - **Compact Shallow 1D CNN (1,413 parameters):** Validation Accuracy: **20.0%**, Validation Macro-F1: **0.1505**.
4. **Gate 4 Decision: BASELINE UNSTABLE OR UNINFORMATIVE:**
   - No baseline candidate achieves validation accuracy meaningfully superior to the 20.0% majority-class baseline (and 20.0% random chance).
   - In all classical models, `static` and `sit` collapse to near-zero recall ($0.00\text{--}0.25$). Cross-subject amplitude variance in an unseen participant (`Participant_05`) is overwhelmed by the static multipath of `Laboratory_Room1`.
   - **Formal Ruling:** Stop model development and recommend systematic, controlled data collection before training further classifiers.
5. **Strict Test Partition Isolation & Zero Regressions (Gate 5 Passed):**
   - The held-out test set (`Participant_02` in `Office_Room2`, 5 sessions, 11 windows) was **not evaluated** and remains completely unpeaked.
   - Checkpoint hashes (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) and manifest hash are verified bit-for-bit pristine.
   - The full repository regression suite passes: **258 / 258 tests passed across 37 test files (100% pass rate)**.

---

## 2. Gate 0 — Reconciled Dataset and Split Evidence

### 2.1 Complete Physical Accounting Across Partitions
An independent audit of `data/real_csi_dataset/dataset_manifest.json` and [`ParticipantIndependentSplitGenerator.generate_strict_cross_room_split()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py) was executed.

| Partition | Sessions | Total Frames | Valid Windows ($T=50$) | Dropped Remainder Frames ($N \pmod{50}$) | Demographics & Invariant Rule |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Train** | **36** | 5,051 | **75** | 1,301 | `Participant_01, 03, 04` in `Laboratory, Laboratory_Room1` |
| **Validation** | **10** | 1,388 | **20** | 388 | `Participant_05` in `Laboratory` (unseen subject, seen room) |
| **Held-Out Test** | **5** | 714 | **11** | 164 | `Participant_02` in `Office_Room2` (unseen subject, unseen room) |
| **Excluded** | **23** | 3,254 | **49** | 804 | P02 in Lab (14 sess), P01 in Office (5 sess), Falls (4 sess) |
| **Global Total** | **74** | **10,407** | **155** | **2,657** | **100% Manifest-to-Disk Integrity** |

### 2.2 Per-Class Window Distribution and Class-ID Mappings

```
Class Mapping:
  0: push_pull (gross upper-limb motion in LOS)
  1: clap      (two-hand rhythmic impact in LOS)
  2: walk      (ambient locomotion across room)
  3: static    (stationary standing motionless)
  4: sit       (chair descent transition)
  Excluded: fall (Class 9 in legacy taxonomy; quarantined)
```

| Activity Label | Class ID | Train Windows | Val Windows | Test Windows | Excluded Windows | Global Windows |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `push_pull` | 0 | 15 | 4 | 3 | 8 | 30 |
| `clap` | 1 | 14 | 4 | 2 | 8 | 28 |
| `walk` | 2 | 16 | 4 | 2 | 9 | 31 |
| `static` | 3 | 15 | 4 | 2 | 5 | 26 |
| `sit` | 4 | 15 | 4 | 2 | 11 | 32 |
| `fall` | *Excl.* | 0 | 0 | 0 | 8 | 8 |
| **Total** | — | **75** | **20** | **11** | **49** | **155** |

### 2.3 Forensic Reconciliation of the Fall Window Discrepancy
Phase 40 was specifically tasked to investigate the historical discrepancy regarding fall window counts:
1. **The Physical Reality on Disk:**
   There are exactly **4 fall recording sessions** in the entire repository:
   - `p15_real_fall_t1_1792303885` (`Participant_01`): 135 packets $\rightarrow 135 // 50 = 2$ windows (remainder 35)
   - `p15_real_fall_t2_1792303889` (`Participant_02`): 136 packets $\rightarrow 136 // 50 = 2$ windows (remainder 36)
   - `p15_real_fall_t3_1792303894` (`Participant_01`): 145 packets $\rightarrow 145 // 50 = 2$ windows (remainder 45)
   - `p15_real_fall_t4_1792303899` (`Participant_02`): 145 packets $\rightarrow 145 // 50 = 2$ windows (remainder 45)
   - **Total Fall Packets:** $135 + 136 + 145 + 145 = 561$ frames.
   - **Total Non-Overlapping Fall Windows:** $2 + 2 + 2 + 2 = \mathbf{8\text{ windows}}$.
2. **Origin of the Historical "4 Fall Windows" Metric:**
   In Phases 17 through 21, the repository utilized a 2-participant Leave-One-Subject-Out (LOSO) partition where `Participant_01` was train and `Participant_02` was test. Under that partition, `Participant_02` contributed sessions `t2` and `t4`, which yielded **exactly 4 test fall windows** (achieving 11.4% of the pilot target of 35). Earlier reports (e.g., `reports/phase18_readiness.md`, `reports/phase20_split_readiness.md`) correctly cited "*4 held-out test fall windows*" derived from 2 trials.
3. **Origin of Phase 34 Narrative Ambiguity:**
   In Phase 34, `reports/phase34_cross_room_split_audit.md` Section 4.1 text described the excluded partition as:
   `Fall sessions from P01: 2 sessions, 280 frames, 4 windows`
   This was an informal drafting categorization because `Participant_02`'s fall sessions were grouped under `Non-Office_Room2 sessions from P02`. However, in the actual implementation of [`ParticipantIndependentSplitGenerator`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py), line 303 checks `if act not in target_classes: assigned_split = 'excluded', reason = 'non_target_activity_fall'`. Thus, **all 4 fall sessions (both P01 and P02)** were quarantined directly under `non_target_activity_fall`. Section 4.2 of the Phase 34 report and Section 4.3 Invariant 8 explicitly confirmed that "*All 8 fall windows (4 sessions) are quarantined in the excluded partition.*"
4. **Conclusion:** There is zero physical contradiction. The repository contains exactly 4 fall sessions and 8 fall windows. All 8 are excluded under the strict cross-room protocol.

---

## 3. Gate 1 — Preprocessing Contract Validation & Training-Only Fitting

### 3.1 Preprocessing Contract Fidelity
1. **Physical Provenance:** Real ESP32-S3 firmware transmits IQ telemetry for only 5 physical subcarrier groups (`raw_num_subcarriers: 5`). The 56 channels in `amplitudes` are derived via 1D linear interpolation (`np.interp`). This distinction is preserved in session JSON files (`raw_amplitudes` vs. `amplitudes`).
2. **Windowing Policy:** Fixed window length of $T = 50$ consecutive frames ($\approx 1.405\text{ s}$ at the empirical $35.58\text{ Hz}$ packet rate). Stride is non-overlapping ($stride = 50$). Trailing frames are discarded at session boundaries.
3. **Branch A Normalization:** Column-wise (per-subcarrier) z-score normalization across the 50 frames:
   $$\tilde{X}(t, k) = \frac{X(t, k) - \mu_k}{\sigma_k + 10^{-6}}$$
   $\epsilon = 10^{-6}$ protects against division-by-zero on static subcarriers.
4. **Branch B Doppler Spectrogram:** Computed via [`PhysicsCSIPreprocessor`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py): static component removal, Hann-windowed STFT ($N_{\text{perseg}}=32, N_{\text{noverlap}}=24, N_{\text{fft}}=64$), log-power transform ($10\log_{10}(P + 10^{-8})$), 2D spline interpolation to $[50, 56]$, and global z-score normalization.
5. **Deployment Parity:** Preprocessing logic is verified to match [`LivePipelineService.predict_latest_window()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) identically.
6. **Strict Training-Only Fitting Invariant:** For classical models requiring standardized feature scaling (`StandardScaler`), the mean $\mu_{\text{train}}$ and variance $\sigma_{\text{train}}^2$ were fitted **strictly on the 75 training windows**. Validation features were normalized using frozen training parameters ($\frac{X_{\text{val}} - \mu_{\text{train}}}{\sigma_{\text{train}}}$). Zero validation or test data was used during fitting.

---

## 4. Gate 2 & Gate 3 — Baseline Definitions & Experimental Results

To determine whether the data supports low-capacity classification, four transparent baseline models were evaluated across two feature representations on the frozen training (75 windows) and validation (20 windows) sets:

### 4.1 Feature Representations Evaluated

1. **Representation 1 — Domain Summary Features (26 features):**
   Physically motivated compact summary features extracted from each $[50, 56]$ window:
   - Subcarrier temporal statistics on the 5 physical subcarriers (indices $[0, 13, 27, 41, 55]$): Mean, Standard Deviation, Peak-to-Peak Amplitude, and Mean Squared Temporal Difference ($5 \times 4 = 20\text{ features}$).
   - Global spatial variance across all 56 subcarriers: Mean temporal variance, Maximum temporal variance, Global temporal difference energy (3 features).
   - Global Doppler kinematics from STFT: Spectrogram mean, variance, and peak intensity (3 features).
   - Total dimensionality: $p = 26$. Ratio to training samples: $\frac{75}{26} \approx 2.88\text{ samples/feature}$ (well-conditioned).
2. **Representation 2 — Flattened Normalized Amplitudes (2,800 features):**
   Full temporal-spatial matrix flattened after per-window column-wise normalization ($50 \times 56 = 2,800\text{ features}$). High-dimensional regime ($p \gg N$).

---

### 4.2 Comprehensive Empirical Results Table

| Candidate Baseline Model | Feature Representation | Train Parameters / Capacity | Train Accuracy | Train Macro-F1 | Validation Accuracy ($N=20$) | Validation Macro-F1 | Primary Confusion Pattern |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Majority-Class Baseline** | Class frequencies | 0 | 21.3% | 0.0703 | **20.0%** (4/20) | 0.0667 | Predicts `walk` for all samples |
| **Logistic Regression ($C=0.1$)** | Domain Summary (26 feats) | 135 weights | 53.3% | 0.5264 | **15.0%** (3/20) | 0.1197 | Severe confusion; `walk`/`static` F1=0 |
| **Logistic Regression ($C=1.0$)** | Domain Summary (26 feats) | 135 weights | 57.3% | 0.5717 | **20.0%** (4/20) | 0.1632 | Matches majority baseline accuracy |
| **Random Forest ($N=100, D=4$)** | Domain Summary (26 feats) | 100 trees | 93.3% | 0.9361 | **30.0%** (6/20) | 0.2905 | `static` and `sit` have 0% recall |
| **SVC (RBF Kernel, $C=1.0$)** | Domain Summary (26 feats) | Kernel SVM | 60.0% | 0.6016 | **5.0%** (1/20) | 0.0444 | Substantially worse than random chance |
| **SVC (Linear Kernel, $C=0.1$)** | Domain Summary (26 feats) | 135 weights | 48.0% | 0.4644 | **20.0%** (4/20) | 0.1606 | Identical to majority baseline |
| **Logistic Regression ($C=0.1$)** | Flattened Norm (2800 feats) | 14,005 weights | 100.0% | 1.0000 | **25.0%** (5/20) | 0.2680 | 1 sample better than majority baseline |
| **Logistic Regression ($C=1.0$)** | Flattened Norm (2800 feats) | 14,005 weights | 100.0% | 1.0000 | **30.0%** (6/20) | 0.3284 | 2 samples better than majority baseline |
| **Random Forest ($N=100, D=4$)** | Flattened Norm (2800 feats) | 100 trees | 100.0% | 1.0000 | **15.0%** (3/20) | 0.1416 | Worse than majority baseline |
| **SVC (RBF Kernel, $C=1.0$)** | Flattened Norm (2800 feats) | Kernel SVM | 100.0% | 1.0000 | **25.0%** (5/20) | 0.2438 | Overfit; static/sit collapsed |
| **SVC (Linear Kernel, $C=0.1$)** | Flattened Norm (2800 feats) | 14,005 weights | 100.0% | 1.0000 | **25.0%** (5/20) | 0.2633 | Overfit; static recall = 0% |
| **Compact Shallow 1D CNN** | Normalized Window [50, 56] | 1,413 weights | 28.0% | 0.2450 | **20.0%** (4/20) | 0.1505 | Identical to majority baseline |

---

### 4.3 Validation Confusion Matrices & Per-Class Failure Analysis

#### Random Forest (Domain Summary Features) — Best Classical Performer (Val Acc: 30.0%):
```
Confusion Matrix (Rows: Ground Truth, Cols: Predicted):
                push_pull    clap    walk    static    sit
  push_pull  : [    2,         0,      1,       1,      0  ]  (Recall: 50.0%)
  clap       : [    2,         2,      0,       0,      0  ]  (Recall: 50.0%)
  walk       : [    1,         0,      2,       1,      0  ]  (Recall: 50.0%)
  static     : [    2,         0,      0,       0,      2  ]  (Recall:  0.0% - COMPLETE FAILURE)
  sit        : [    3,         0,      1,       0,      0  ]  (Recall:  0.0% - COMPLETE FAILURE)
```
- **Per-Class Metrics:**
  - `push_pull` ($N=4$): Precision = 0.20, Recall = 0.50, F1 = 0.29
  - `clap` ($N=4$): Precision = 1.00, Recall = 0.50, F1 = 0.67
  - `walk` ($N=4$): Precision = 0.50, Recall = 0.50, F1 = 0.50
  - `static` ($N=4$): Precision = 0.00, Recall = 0.00, F1 = 0.00 (Predicted as `push_pull` and `sit`)
  - `sit` ($N=4$): Precision = 0.00, Recall = 0.00, F1 = 0.00 (Predicted as `push_pull` and `walk`)

#### Logistic Regression ($C=1.0$, Flattened Normalized Features) — Val Acc: 30.0%:
```
Confusion Matrix (Rows: Ground Truth, Cols: Predicted):
                push_pull    clap    walk    static    sit
  push_pull  : [    1,         0,      1,       1,      1  ]  (Recall: 25.0%)
  clap       : [    0,         2,      1,       0,      1  ]  (Recall: 50.0%)
  walk       : [    1,         0,      1,       0,      2  ]  (Recall: 25.0%)
  static     : [    3,         0,      0,       1,      0  ]  (Recall: 25.0%)
  sit        : [    2,         0,      0,       1,      1  ]  (Recall: 25.0%)
```

### 4.4 Session-Level Aggregation Analysis
Each of the 10 validation sessions consists of exactly 2 consecutive 50-frame windows:
- In sessions where window predictions diverged (e.g., Window 0 predicted `clap`, Window 1 predicted `push_pull`), majority voting with tie-breaking (favoring higher confidence) yielded session accuracy identical to window accuracy (**20.0% – 30.0%**, or 2 to 3 sessions correct out of 10).
- In `static` and `sit` sessions, both windows were misclassified into dynamic motion classes in almost every model, showing that session aggregation cannot resolve feature-level representation collapse.

---

## 5. Gate 4 — Decision & Forensic Evaluation

In accordance with Gate 4, we evaluate the evidence against the three pre-registered outcomes:

1. **Is the baseline promising?**
   **NO.** Across all 12 model/feature configurations, validation accuracy on an unseen subject in the training room ranges from **5.0% to 30.0%**. In a 5-class problem where random guessing is 20.0% and the majority-class baseline is 20.0%, an accuracy of 30.0% represents exactly **6 correct windows out of 20** (a margin of only 2 windows above chance). Both `static` and `sit` exhibit near-zero sensitivity. There is zero evidence of a credible activity classifier.
2. **Did data or preprocessing audit fail?**
   **NO.** Gate 0 and Gate 1 passed completely. Data provenance, 155-window accounting, 5-to-56 subcarrier interpolation, dropped frame accounting, and preprocessing parity with deployment were independently verified and passed unit tests.
3. **Is the baseline unstable or uninformative?**
   **YES.** All models either:
   - Severely overfit on 2,800 features (100% train accuracy $\rightarrow$ 15%–30% val accuracy), or
   - Underfit on 26 summary features (48%–60% train accuracy $\rightarrow$ 5%–20% val accuracy), or
   - Collapse to random guessing on a compact 1D CNN (20.0% val accuracy).

### Formal Gate 4 Ruling:
> **BASELINE UNSTABLE OR UNINFORMATIVE**  
> **Model development is halted.** The existing 75 training windows across 3 participants in a single room are mathematically and physically inadequate to establish a credible five-class baseline. Proceeding to evaluate cross-room generalization on the held-out test set under these conditions would be scientifically uninformative and waste the unpeaked test set. We recommend systematic, controlled data collection.

---

## 6. Gate 5 — Integrity and Full Repository Regression

### 6.1 Checkpoint & Manifest MD5 Bit-Integrity

| Target File | Reference MD5 Hash | Current Computed MD5 | Integrity Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |
| `models/csiformer_phase39_retrained.pth` | *N/A (Not Created)* | *File does not exist* | **CORRECT** |
| `models/csiformer_phase40_baseline.pth` | *N/A (Not Created)* | *File does not exist* | **CORRECT** |

### 6.2 Full Repository Test Execution Results

```bash
# 1. Targeted Phase 40 Unit Tests:
py -3.11 -m pytest backend/tests/test_phase40.py -v
# Outcome: 6 passed in 19.36s (Exit code 0)

# 2. Cumulative Strict Split & Protocol Suite (Phases 34–40):
py -3.11 -m pytest backend/tests/test_phase34.py backend/tests/test_phase35.py backend/tests/test_phase36.py backend/tests/test_phase37.py backend/tests/test_phase38.py backend/tests/test_phase39.py backend/tests/test_phase40.py -v
# Outcome: 42 passed in 9.19s (Exit code 0)

# 3. Full Repository Regression Suite:
py -3.11 -m pytest backend/tests/ -v
# Outcome: 258 passed, 0 failed across all 37 test files in 75.52s (Exit code 0)
```

---

## 7. Explicit Confirmation of Scientific Protections

1. **Held-Out Test Set Untouched:** The held-out test partition (`Participant_02` in `Office_Room2`, 5 sessions, 11 windows) was **NEVER evaluated, fitted, or predicted**. It remains 100% unpeaked and preserved for future phases.
2. **No Production Checkpoint Created:** In strict compliance with instructions, no production or experimental checkpoint was created, promoted, or overwritten.
3. **No Unsafe Falls Collected:** Zero new data was acquired.
4. **No Destructive Cleanup:** Zero files were deleted, committed, pushed, or reset.
5. **No Claims of Generalization:** We explicitly state that the existing dataset cannot support a credible 5-class baseline, and that no cross-room generalization is claimed.

---

## 8. Limitations & Recommended Next Steps

### 8.1 Inherent Physical Limitations of the Current Dataset
1. **Severe Subcarrier Decimation:** Physical ESP32-S3 firmware provides only 5 subcarriers. Linearly interpolating to 56 channels produces smooth synthetic curves but cannot recover high-frequency multipath spatial diversity.
2. **Single-Room Training Overfitting:** All 75 training windows were collected in `Laboratory_Room1`. Static human presence and subtle body movements are masked by the specific multipath reflection profile of that room.
3. **Extreme Sample Scarcity:** 15 windows per class corresponds to roughly 21 seconds of physical activity per class across 3 participants. This volume is insufficient to train even regularized linear classifiers to generalize across subjects.

### 8.2 Recommended Safe Next Steps

1. **Systematic Multi-Room Data Acquisition Campaign:**
   Before training further machine learning models (deep or classical), expand the physical ESP32-S3 dataset:
   - Target: Minimum 100+ sessions per class across $\ge 10$ participants in at least 3 distinct physical rooms ($> 500$ windows per class).
   - Ensure balanced recordings of stationary states (`static`, `sit`) under varied multipath conditions and distances.
2. **Multi-Antenna / Dual-Node Firmware Configuration:**
   Explore ESP32-S3 firmware upgrades to capture multi-antenna CSI (MIMO $2 \times 1$ or $2 \times 2$) to recover true spatial phase diversity rather than relying on 1D subcarrier interpolation.
3. **Formal Review:**
   Present this report to project leadership to conclude the evaluation track and transition the project to an authorized, systematic data-acquisition campaign.
