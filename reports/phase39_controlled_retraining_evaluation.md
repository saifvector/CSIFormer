# CSIFormer Phase 39 — Controlled Retraining and Cross-Room Feasibility Evaluation Report

**Date:** October 19, 2026  
**Status:** GATE 0 BLOCKED (DATA INSUFFICIENCY & CATASTROPHIC OVERFITTING EVIDENCE) — RETRAINING & EVALUATION HALTED  
**Author:** Antigravity / CSIFormer Pair Programming Agent  
**Artifact Hash Audits:** Verified Bit-for-Bit Pristine  
**Model Inference on Held-Out Test Set:** NOT PERFORMED (STRICT TEST ISOLATION ENFORCED)  
**Model Retraining / Checkpoint Creation:** NOT PERFORMED (PRE-CONDITIONS ENFORCED)  

---

## 1. Executive Summary

Phase 39 was chartered to proceed with the Phase 38 Strategy C design ("Native ESP32-S3 Preprocessing Contract with Real-Data Adaptation"), subject to mandatory pre-training gates (Gates 0–3). The stated objective was to establish a consistent real-ESP32-S3 training/inference pipeline, train a new model artifact at `models/csiformer_phase39_retrained.pth` **only if the available data and protocol justify it**, and evaluate cross-room feasibility using the frozen Phase 34 strict cross-room partition.

In strict compliance with **Mandatory Protection 9** ("*If a mandatory gate fails, stop before training and document the blocker*") and the explicit mandate of **Gate 0** ("*Assess whether the available dataset is sufficient for the proposed architecture... If training from scratch or fine-tuning is not defensible with the available data, mark Gate 0 BLOCKED and propose a safe data-acquisition or model-scope change instead*"), **Gate 0 is formally evaluated as BLOCKED**.

### Primary Forensic Findings:

1. **Extreme Parameter-to-Sample Disparity:**
   The proposed architecture, [`CSIDualBranchFusionNet`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/models/csiformer_dual_branch.py) (configured for 5 activity classes), contains **1,482,503 trainable parameters**. In the frozen strict cross-room partition, the training set contains exactly **75 windows** (14 `clap`, 15 `push_pull`, 15 `sit`, 15 `static`, 16 `walk`) across 3 participants in `Laboratory_Room1`. This yields a parameter-to-sample ratio of **19,766:1**. Total training signal duration is merely 105 seconds ($75 \times 1.4\text{ s}$).
2. **Empirical Overfitting & Memorization Dynamics:**
   To establish whether regularized training could overcome this imbalance, an empirical baseline trial was conducted on the training and validation partitions. The results revealed textbook catastrophic overfitting:
   - Training accuracy rose from 6.7% to **100.0%** (training loss collapsed from 1.6729 to 0.3610).
   - Concurrently, validation loss on `Participant_05` in the same room monotonically **diverged from 1.6089 to 2.4660**, while validation accuracy collapsed to **5.0%** (substantially worse than random 5-class chance of 20.0%).
   - The dual-branch Transformer memorized room-specific multipath and participant signatures within 10 epochs.
3. **Preclusion of Transfer Learning / Benchmark Pretraining (Gate 2 Boundary):**
   Initializing or fine-tuning from historical checkpoints or benchmark datasets (Widar 3.0 / NTU-Fi) is indefensible because:
   - Widar 3.0 and NTU-Fi contain **zero examples** of stationary standing (`static`) or chair descent (`sit`). Gate 2 prohibits substituting dynamic boxing (`box`) or table cleaning (`clean`).
   - Severe domain mismatch: Widar operates at 5.2 GHz with 1000 Hz packet rates ($v_{\max} = 14.4\text{ m/s}$, zero aliasing), whereas ESP32-S3 operates at 2.442 GHz with 35.58 Hz packet rates ($v_{\max} = 1.09\text{ m/s}$, severe walking aliasing) with 91% synthetic subcarriers.
4. **Preservation of the Held-Out Test Partition (Gate 5 Protection):**
   Because training was not authorized, the held-out test partition (5 sessions, 11 windows from `Participant_02` in `Office_Room2`) was **never evaluated**. The test partition remains 100% pristine, unpeaked, and unpolluted.
5. **No Checkpoint Creation & Zero Regressions:**
   `models/csiformer_phase39_retrained.pth` was **not created**. Historical checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) and the dataset manifest remain bit-for-bit identical to their reference MD5 hashes. All **252 / 252 tests** in the repository regression suite pass with a 100% pass rate.

---

## 2. Final Status Summary Table

| Evaluation Gate / Component | Status | Detailed Finding & Forensic Verification |
| :--- | :---: | :--- |
| **Training/Evaluation Scope Reconciled** | **RECONCILED (GO)** | Training taxonomy established as 5 physical classes; primary evaluation taxonomy defined with 3-class dynamic diagnostic subset. |
| **Data Sufficiency** | **BLOCKED (FAIL)** | **75 training windows (15/class) vs. 1,482,503 parameters (ratio 19,766:1). Empirical trial demonstrated validation loss divergence from 1.61 to 2.47 and 100% training memorization.** |
| **Preprocessing Contract** | **FROZEN & VERIFIED (GO)** | Contract frozen: 5-to-56 linear interpolation, 50-frame non-overlapping window, column-wise z-score normalization (Branch A), STFT log-power spectrogram (Branch B). |
| **Train/Val/Test Isolation** | **PASSED (GO)** | Strict cross-room partition audited: Train (P01, P03, P04 in Lab), Val (P05 in Lab), Test (P02 in Office), Excluded (23 sessions). Zero participant or room leakage. |
| **Training Status** | **NOT PERFORMED** | **Strict compliance with Gate 0 blocker: Zero model training steps executed for checkpoint creation.** |
| **Evaluation Status** | **NOT PERFORMED** | **Zero test-set forward passes executed. Held-out test partition preserved completely unpolluted.** |
| **Deployment Parity** | **VERIFIED (GO)** | Frozen preprocessing contract verified bit-for-bit identical to [`LivePipelineService.predict_latest_window()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py). |
| **Historical Checkpoint Integrity** | **PASSED (GO)** | Phase 13 MD5: `383b4d98c08f8970b0443738f170ec01` (**MATCH**)<br>Phase 15 MD5: `ab3d97a04d78edf75d807178772bc828` (**MATCH**) |
| **New Checkpoint Integrity** | **NOT CREATED** | `models/csiformer_phase39_retrained.pth` was **not created**, honoring the pre-training gate blocker. |
| **Regression Status** | **PASSED (GO)** | Full repository test suite: **252 / 252 passed across all 36 test files (0 failures, 100% pass rate)**. |
| **Scientific Limitations** | **CATALOGED** | Severe undersampling, multipath memorization, 35.58 Hz Doppler aliasing, and single-room training limitations formally documented. |

---

## 3. Gate 0 — Scope Reconciliation & Per-Class Accounting

### 3.1 Training vs. Primary Evaluation Taxonomy Reconciliation
Phase 38 noted that `static` and `sit` were marked "excluded from benchmark scope" while Strategy C simultaneously proposed real ESP32-S3 supervision for them. This apparent contradiction is formally resolved:
- **Benchmark-Pretraining Scope:** Widar 3.0 and NTU-Fi lack `static` (stationary motionless standing) and `sit` (chair descent). They are strictly excluded from any benchmark pretraining stage to prevent invalid alias substitutions (e.g., mapping `static` to dynamic boxing or `sit` to table cleaning).
- **Real-Hardware Training Taxonomy (5 Classes):** When training on real ESP32-S3 data, direct physical ground-truth labels exist for all 5 activities. The model is formulated to distinguish:
  - Class 0: `push_pull` (gross upper-limb motion in LOS)
  - Class 1: `clap` (rhythmic two-hand impact in LOS)
  - Class 2: `walk` (gross-motor human locomotion across room)
  - Class 3: `static` (stationary human standing motionless in room)
  - Class 4: `sit` (gross-motor vertical body descent into chair)
  - *Excluded:* `fall` is strictly excluded from this phase due to safety and absence in the held-out test partition.
- **Primary Evaluation Taxonomy:** Evaluated on the 5-class physical taxonomy, with an explicitly isolated 3-class diagnostic subset (`push_pull`, `clap`, `walk` at indices 0, 1, 2) to assess whether dynamic activities behave differently from stationary posture states.

### 3.2 Audit of Frozen Strict Partition and Per-Class Window Counts
The dataset manifest ([`data/real_csi_dataset/dataset_manifest.json`](file:///C:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json)) was partitioned using [`ParticipantIndependentSplitGenerator.generate_strict_cross_room_split()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py). Slicing sessions into non-overlapping windows of 50 consecutive frames produces exact per-class counts:

| Split Partition | Participant & Environment Demographics | Sessions | `clap` | `push_pull` | `sit` | `static` | `walk` | `fall` | Total Windows |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | `Participant_01, 03, 04` in `Laboratory_Room1` | 36 | 14 | 15 | 15 | 15 | 16 | 0 | **75** |
| **Validation** | `Participant_05` in `Laboratory_Room1` | 10 | 4 | 4 | 4 | 4 | 4 | 0 | **20** |
| **Held-Out Test** | `Participant_02` in `Office_Room2` | 5 | 2 | 3 | 2 | 2 | 2 | 0 | **11** |
| **Excluded** | P02 in Lab (14), P01 in Office (5), Falls in Lab (4) | 23 | 8 | 8 | 11 | 5 | 9 | 8 | **49** |
| **Total** | **Full Physical Inventory** | **74** | **28** | **30** | **32** | **26** | **31** | **8** | **155** |

*Key Audit Confirmation:* The previously cited 75 / 20 / 11 window counts apply to the **full five-class safe taxonomy**, not a three-class subset. The three-class subset contains only 45 train, 12 val, and 7 test windows.

---

## 4. Gate 0 — Data Sufficiency Audit & Empirical Evidence

### 4.1 Theoretical Parameter-to-Sample Analysis
The standard CSIFormer dual-branch architecture, [`CSIDualBranchFusionNet`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/models/csiformer_dual_branch.py), consists of:
- **Branch A (Raw Amplitude Encoder):** 1D-CNN Spatial Extractor + 3-layer Transformer Encoder (`embed_dim=128`, `nhead=8`, `dim_feedforward=512`) + Temporal Attention Pooling = 708,231 parameters.
- **Branch B (Doppler Spectrogram Encoder):** 1D-CNN Spatial Extractor + 3-layer Transformer Encoder + Temporal Attention Pooling = 708,231 parameters.
- **Gated Cross-Branch Fusion & Multi-Task Heads:** Gated dense linear layer (`256 -> 128`), LayerNorm, 5-class activity head (`128 -> 5`), presence head, motion head, projection head = 66,041 parameters.
- **Total Trainable Parameters:** **1,482,503 parameters**.

**The Fundamental Flaw:**  
- Input data: 75 training windows $\times$ (50 time frames $\times$ 56 subcarriers) = 210,000 input scalar float values.
- Free model parameters: 1,482,503.
- Parameter-to-sample ratio: $\frac{1,482,503}{75} \approx \mathbf{19,766\text{ parameters per training sample}}$.
- Parameter-to-input ratio: Model parameters outnumber all raw input floats by **7:1**.
- In statistical learning theory, training an unconstrained Transformer with 1.48M weights on 15 examples per class violates basic sample-complexity lower bounds, guaranteeing sample memorization rather than generalizable pattern extraction.

### 4.2 Empirical Proof: Training Dynamics and Overfitting Trial
To verify whether heavy regularization (weight decay = 0.01, dropout = 0.3, AdamW optimizer, lr = $10^{-4}$, batch size = 8) could stabilize learning, a trial run was executed on the exact 75 train and 20 validation windows:

```
Loaded train: x_raw=[75, 50, 56], x_dopp=[75, 50, 56], y=[75]
Loaded val:   x_raw=[20, 50, 56], x_dopp=[20, 50, 56], y=[20]

Training Dynamics:
Epoch  1: Train Loss = 1.6729, Train Acc =   6.7% | Val Loss = 1.6089, Val Acc = 15.0%
Epoch  2: Train Loss = 1.5716, Train Acc =  33.3% | Val Loss = 1.6104, Val Acc = 20.0%
Epoch  4: Train Loss = 1.5386, Train Acc =  33.3% | Val Loss = 1.6416, Val Acc = 20.0%
Epoch  6: Train Loss = 1.3817, Train Acc =  52.0% | Val Loss = 1.7127, Val Acc = 10.0%
Epoch  8: Train Loss = 1.2167, Train Acc =  60.0% | Val Loss = 1.8535, Val Acc =  5.0%
Epoch 10: Train Loss = 1.0496, Train Acc =  77.3% | Val Loss = 1.9669, Val Acc =  5.0%
Epoch 12: Train Loss = 0.8398, Train Acc =  85.3% | Val Loss = 2.1368, Val Acc =  5.0%
Epoch 14: Train Loss = 0.7372, Train Acc =  84.0% | Val Loss = 2.2366, Val Acc =  5.0%
Epoch 16: Train Loss = 0.5354, Train Acc =  93.3% | Val Loss = 2.2988, Val Acc =  0.0%
Epoch 18: Train Loss = 0.3916, Train Acc =  98.7% | Val Loss = 2.4105, Val Acc =  0.0%
Epoch 20: Train Loss = 0.3610, Train Acc = 100.0% | Val Loss = 2.4660, Val Acc =  5.0%
```

```mermaid
graph TD
    subgraph Training Dynamics (75 Train Windows vs 1.48M Params)
        TL[Train Loss: 1.67 -> 0.36] --> TA[Train Accuracy: 6.7% -> 100.0%]
        VL[Val Loss: 1.61 -> 2.47 DIVERGES] --> VA[Val Accuracy: 20.0% -> 5.0% COLLAPSES]
    end
    TA --> MEM[Total Sample Memorization]
    VL --> OVERFIT[Severe Catastrophic Overfitting]
    MEM --> BLK[Gate 0 BLOCKED: Indefensible for Evaluation]
    OVERFIT --> BLK
```

### 4.3 Gate 0 Ruling
The empirical trial demonstrates that by Epoch 20, the model reaches 100.0% training accuracy while validation loss explodes from 1.61 to 2.47 and validation accuracy collapses to 5.0% (1 correct prediction out of 20).  
Training a model under these conditions to evaluate cross-room feasibility on an unseen room (`Office_Room2`) is **scientifically indefensible**: the network evaluates purely random noise or memorized multipath artifacts.

Therefore, in strict adherence to Gate 0 instructions:  
**Gate 0 is marked BLOCKED.**

---

## 5. Gate 1 — Frozen Real-Hardware Preprocessing Contract

To establish standard parity between offline training and live production deployment, the native ESP32-S3 preprocessing contract is formally frozen.

### 5.1 Preprocessing Specification

1. **Input Channel Provenance:**
   - Physical hardware captures exactly **5 subcarriers** (`raw_num_subcarriers: 5`).
   - The 56 channels in `amplitudes` are derived via 1D linear interpolation (`np.interp` from 5 points to a 56-element uniform grid).
   - The distinction between physical and synthetic subcarriers is preserved in telemetry.
2. **Temporal Windowing:**
   - Window length: Exactly **50 consecutive frames** ($T = 50$). At $35.58\text{ Hz}$, window duration is $\approx 1.405\text{ seconds}$.
   - Stride: Non-overlapping sliding windows ($stride = 50$).
   - Session Boundaries: Windows must never cross session boundaries. Trailing frames ($N \pmod{50} < 50$) are strictly discarded.
3. **Branch A (Raw Amplitude Pipeline):**
   - Extract raw amplitude window matrix $X_{\text{raw}} \in \mathbb{R}^{50 \times 56}$.
   - Apply channel-wise (column-wise) z-score normalization across the 50 timeframes:
     $$\mu_k = \frac{1}{50}\sum_{t=1}^{50} X_{\text{raw}}(t, k), \quad \sigma_k = \sqrt{\frac{1}{50}\sum_{t=1}^{50} (X_{\text{raw}}(t, k) - \mu_k)^2}$$
     $$\tilde{X}_{\text{raw}}(t, k) = \frac{X_{\text{raw}}(t, k) - \mu_k}{\sigma_k + 10^{-6}}$$
   - Numerical safeguard: $\epsilon = 10^{-6}$ prevents division by zero on static subcarriers.
4. **Branch B (Doppler Frequency Spectrogram Pipeline):**
   - Implemented via [`PhysicsCSIPreprocessor.compute_doppler_spectrogram()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py):
     1. Static component removal: Subtract temporal mean per subcarrier.
     2. STFT calculation: Hann window, $N_{\text{perseg}} = 32$, $N_{\text{noverlap}} = 24$, $N_{\text{fft}} = 64$ at $f_s = 30.0\text{ Hz}$.
     3. Frequency shift and power calculation: $P(f, t) = |\text{fftshift}(Z_{xx})|^2$.
     4. Subcarrier aggregation: Average power across 56 subcarriers.
     5. Log-scale power: $S_{\text{log}} = 10 \log_{10}(P_{\text{avg}} + 10^{-8})$.
     6. 2D Bivariate Spline Resampling: Interpolate time-frequency grid to target shape $[50, 56]$.
     7. Global z-score normalization: $\tilde{X}_{\text{dopp}} = \frac{S - \mu_S}{\sigma_S + 10^{-6}}$.
5. **Tensor Shape and Dtype:**
   - `tensor_raw`: `torch.FloatTensor` of shape `[Batch, 50, 56]`.
   - `tensor_dopp`: `torch.FloatTensor` of shape `[Batch, 50, 56]`.

### 5.2 Verification of Deployment Parity (Gate 6)
Deterministic unit tests in [`backend/tests/test_phase39.py::test_phase39_shared_preprocessing_contract_and_parity`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase39.py) verify that the frozen contract produces outputs bit-for-bit identical to [`LivePipelineService.predict_latest_window()`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py). Zero ground-truth-dependent logic exists in the signal chain.

---

## 6. Gate 2 — Benchmark Pretraining Boundary

In accordance with Gate 2, benchmark pretraining on external datasets was formally audited:
1. **Semantic Incompatibility:** Neither Widar 3.0 nor NTU-Fi contains `static` or `sit`. NTU-Fi contains dynamic boxing (`box`) and table wiping (`clean`), which Phase 36 proved are completely distinct physical motions. Using them as proxies causes severe negative transfer.
2. **Physical Domain Shift:**
   - Widar 3.0: 5.2 GHz, 1000 Hz packet rate, 30 subcarriers, zero Doppler aliasing ($v_{\max} = 14.4\text{ m/s}$).
   - ESP32-S3: 2.442 GHz, 35.58 Hz packet rate, 5 physical subcarriers, severe Doppler aliasing at walking speeds ($v_{\max} = 1.09\text{ m/s}$).
3. **Decision:** Because the benchmark-to-hardware transfer strategy cannot be justified or validated without polluting or accessing the test set, **the benchmark pretraining stage was omitted**, in full compliance with Gate 2.

---

## 7. Gate 3 — Pre-Training Unit Test Suite

Prior to halting training, eight deterministic tests were implemented in [`backend/tests/test_phase39.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase39.py):

| Test Identifier | Validated Contract / Invariant | Status |
| :--- | :--- | :---: |
| `test_phase39_checkpoint_and_manifest_integrity` | Asserts MD5 hashes of P13, P15, and manifest; confirms P39 artifact does not exist | **PASSED** |
| `test_phase39_channel_provenance_and_ordering` | Verifies 5 raw subcarriers vs. 56 interpolated channels in Phase 16+ sessions | **PASSED** |
| `test_phase39_window_construction_and_session_boundaries` | Confirms strict session isolation and exact 75/20/11/49 window accounting | **PASSED** |
| `test_phase39_shared_preprocessing_contract_and_parity` | Verifies bit-for-bit parity between training contract and `LivePipelineService` | **PASSED** |
| `test_phase39_numerical_safeguards_and_finite_bounds` | Validates finite bounds and $\epsilon=10^{-6}$ handling on constant/zero-variance inputs | **PASSED** |
| `test_phase39_class_index_mapping_and_taxonomy` | Enforces exact 5-class index mapping [0..4] and segregation from legacy indices | **PASSED** |
| `test_phase39_train_val_test_isolation` | Confirms strict participant and room isolation (zero test leakage into train/val) | **PASSED** |
| `test_phase39_gate0_data_sufficiency_and_parameter_audit` | Formally audits 1.48M parameters vs. 75 samples and enforces Gate 0 BLOCKED status | **PASSED** |

Execution Output:
```bash
py -3.11 -m pytest backend/tests/test_phase39.py -v
# Outcome: 8 passed in 9.64s (Exit code 0)
```

---

## 8. Gates 4 & 5 — Retraining and Controlled Evaluation Status

### 8.1 Gate 4 (Model Retraining) Status: BLOCKED
Because Gate 0 is BLOCKED:
- No new checkpoint was trained or saved.
- `models/csiformer_phase39_retrained.pth` was **NOT created**.
- Protected checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) were preserved untouched.

### 8.2 Gate 5 (Controlled Cross-Room Evaluation) Status: BLOCKED (PRESERVED)
Because Gate 4 did not produce a valid, generalizable checkpoint:
- The held-out test partition (5 sessions, 11 windows from `Participant_02` in `Office_Room2`) was **NOT evaluated**.
- Zero model forward passes or predictions were executed against the test set.
- The test set remains completely unpeaked, uncompromised, and preserved for future phases when adequate data is acquired.

---

## 9. Gate 7 — Regression Suite & Checkpoint Integrity

### 9.1 Checkpoint and Manifest Bit-Integrity Audit

| Target File | Reference MD5 Hash | Current Computed MD5 | Integrity Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |
| `models/csiformer_phase39_retrained.pth` | *N/A (Not Authorized)* | *File does not exist* | **CORRECT (Not Created)** |

### 9.2 Complete Regression Execution Results

```bash
# 1. Targeted Phase 39 Test Suite:
py -3.11 -m pytest backend/tests/test_phase39.py -v
# Outcome: 8 passed in 9.64s (Exit code 0)

# 2. Cumulative Strict Split & Protocol Suite (Phases 34–39):
py -3.11 -m pytest backend/tests/test_phase34.py backend/tests/test_phase35.py backend/tests/test_phase36.py backend/tests/test_phase37.py backend/tests/test_phase38.py backend/tests/test_phase39.py -v
# Outcome: 36 passed in 6.62s (Exit code 0)

# 3. Full Repository Regression Suite:
py -3.11 -m pytest backend/tests/ -v
# Outcome: 252 passed, 0 failed across all 36 test files in 66.91s (Exit code 0)
```

### 9.3 Working Tree Status (`git status --short`)
- `backend/tests/test_phase39.py`: Added (Deterministic unit tests).
- `reports/phase39_controlled_retraining_evaluation.md`: Added (This evaluation report).
- All raw CSV and JSON recording files: **Untouched**.
- Zero commits, pushes, cleans, or resets executed.

---

## 10. Explicit Confirmation of Scientific Protections

In strict compliance with all project instructions:
1. **Model inference was NOT executed on the held-out test set.**
2. **No model weights were modified, adapted, or retrained.**
3. **`models/csiformer_phase39_retrained.pth` was NOT created.**
4. **Dataset files and splits were NOT mutated.**
5. **No claim of benchmark generalization was fabricated.**

---

## 11. Smallest Safe Next Steps & Recommendations

Because training an unconstrained 1.48M-parameter dual-branch Transformer network on 75 training samples leads to 100% memorization and validation divergence, the smallest safe next steps to achieve a scientifically defensible model are:

1. **Option A (Model Scope Change — Lightweight Architecture):**
   Replace `CSIDualBranchFusionNet` with a lightweight, low-capacity architecture tailored for small-sample edge regimes:
   - A 2-layer shallow CNN or linear classifier with $< 2,000$ parameters (parameter-to-sample ratio $< 25:1$).
   - A traditional machine learning baseline (e.g., Random Forest or SVM on summary Doppler and amplitude statistical features).
2. **Option B (Data Acquisition Expansion):**
   Before deploying deep Transformer architectures, expand the real-hardware collection in `Laboratory_Room1` and additional training rooms:
   - Minimum target: 100+ sessions per class across 10+ participants ($> 500$ windows per class).
   - Multi-room training diversity to break environment-specific multipath memorization.
3. **Review and Gate Closure:**
   Present this report to the user to formally ratify the Gate 0 blocker and select between Option A (Lightweight Architecture) or Option B (Targeted Data Acquisition).
