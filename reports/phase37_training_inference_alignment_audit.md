# CSIFormer Phase 37 — Training–Inference Preprocessing Alignment Audit Report

**Date:** October 19, 2026  
**Status:** EVALUATION READINESS BLOCKED — MODEL INFERENCE NOT PERFORMED  
**Author:** Antigravity / CSIFormer Pair Programming Agent  
**Artifact Hash Audits:** Verified Bit-for-Bit Pristine  
**Model Inference / Forward Passes:** NOT PERFORMED (STRICTLY PROHIBITED)  
**Model Training / Adaptation:** NOT PERFORMED (STRICTLY PROHIBITED)  

---

## 1. Executive Summary

Phase 37 was chartered to conduct an exhaustive, rigorous engineering and physical signal audit of the preprocessing pipelines used to construct the dual-branch inputs (`Branch A: Raw CSI` and `Branch B: Doppler Frequency Spectrum`) for the protected CSIFormer checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`). The primary objective was to resolve the preprocessing compatibility blockers identified in Phase 36 before authorizing any model inference on real ESP32-S3 hardware recordings.

### Key Forensic Discoveries:

1. **Fatal Training-Time Branch B Disparity (NTU-Fi STFT Bypass):**
   Forensic analysis of the original Phase 13 training implementation in [`scratch/execute_phase13_2_dual_branch_and_benchmark.py:L325-326`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L325-L326) reveals that while Widar 3.0 gesture samples (classes 0–5) were trained with distinct dual branches (Raw CSI + STFT Doppler Spectrogram), **NTU-Fi HAR activity samples (classes 6–11, which includes `walk` [11]) completely bypassed STFT during training**. The training script explicitly duplicated the raw CSI amplitude tensor directly into Branch B (`nt_dopp_train.append(s["csi"])`). Consequently, the Doppler encoder weights for class 11 (`walk`) were trained on raw subcarrier amplitudes, **not** Doppler frequency spectrograms.

2. **Inference Preprocessing Disparity (`LivePipelineService`):**
   The production inference engine in [`backend/app/services/live_pipeline_service.py:L201-202`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L201-L202) applies `self.preprocessor.compute_doppler_spectrogram(raw_win)` unconditionally to all incoming windows. When an ESP32-S3 `walk` window is processed through `LivePipelineService`, Branch B receives a log-power Doppler spectrogram, conflicting directly with the training contract of `csiformer_phase13_best.pth`.

3. **Inference Normalization Discrepancy:**
   `LivePipelineService` normalizes Branch A using **per-subcarrier (channel-wise) z-score normalization along axis 0** (`(raw_win - mean(axis=0)) / std(axis=0)`), whereas Phase 13 training utilized **global scalar z-score normalization** across the entire $50 \times 56$ matrix (`(resampled - mean) / std`).

4. **Evaluation Readiness Determination:**
   Because a label-blind production inference service cannot determine whether an incoming window is `walk` or `push_pull` in order to switch Branch B between raw duplication and STFT without ground-truth label snooping, **exact preprocessing parity with `csiformer_phase13_best.pth` cannot be achieved simultaneously across all target classes**. Evaluation readiness is formally marked **BLOCKED**.

5. **Protections Enforced:**
   Zero model instances were loaded with protected weights; zero forward passes were executed; zero checkpoints were trained, adapted, or modified. Checkpoint hashes and the dataset manifest remain bit-for-bit invariant. Full repository regression suite passed with 100% success (238 / 238 tests passing across 34 test files).

---

## 2. Final Status Summary Table

| Evaluation Gate / Component | Status | Detailed Finding & Forensic Verification |
| :--- | :---: | :--- |
| **Training Preprocessing Reconstructed** | **COMPLETED** | Traced to source: Widar used (Raw CSI + STFT Doppler); NTU-Fi bypassed STFT and duplicated raw CSI into Branch B. |
| **Production Preprocessing Reconstructed** | **COMPLETED** | Traced `LivePipelineService`: Channel-wise normalization on Raw; unconditional STFT at 30.0 Hz on Doppler; lacks offline API. |
| **Raw-Branch Compatibility** | **MISMATCHED** | Live service uses column-wise (per-subcarrier) z-score; training used global scalar z-score across $50 \times 56$. |
| **Doppler-Branch Compatibility** | **BLOCKED** | Live service computes STFT for all inputs; Phase 13 training bypassed STFT for class 11 (`walk`). |
| **Three-Class Semantic Compatibility** | **PASSED (GO)** | `push_pull` (0), `clap` (2), and `walk` (11) are semantically identical physical activities between training and real captures. |
| **Offline Evaluation Readiness** | **BLOCKED** | Label-blind inference cannot resolve the source-dependent Branch B contract (STFT vs Raw duplicate) without target leakage. |
| **Regression Status** | **PASSED (GO)** | Full repository suite: **238 / 238 tests passed across 34 test files (0 failures, 100% pass rate)**. |
| **Checkpoint Integrity** | **PASSED (GO)** | Production MD5: `383b4d98c08f8970b0443738f170ec01` (**MATCH**)<br>Experimental MD5: `ab3d97a04d78edf75d807178772bc828` (**MATCH**) |
| **Inference Status** | **NOT PERFORMED** | Zero inference forward passes executed; zero weights loaded into instantiated models. |

---

## 3. Task 1 — Reconstruction of Training-Time Preprocessing

Both protected checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) utilize the dual-branch architecture [`CSIDualBranchFusionNet`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/models/csiformer_dual_branch.py). However, the training inputs were assembled from heterogeneous datasets with fundamentally distinct signal chains.

### 3.1 Widar 3.0 Dataset Path (Classes 0–5: `Push&Pull`, `Sweep`, `Clap`, `Slide`, `Draw-O`, `Draw-Zigzag`)

- **Physical Sensor:** Intel 5300 NIC (802.11n HT20, 5.2 GHz carrier, $\lambda \approx 0.0576$ m).
- **Source Dimensions:** Raw packet bursts of shape $(T_{\text{packets}}, 30, 3, 1)$ containing complex channel response $H(t, k, rx, tx)$ across 30 sampled subcarriers, 3 receiver antennas, and 1 transmitter antenna. Packet counts typically range from 1,000 to 2,500 packets per gesture burst.
- **Sampling Rate:** $1000\text{ Hz}$ packet rate (`source_rate_hz=1000.0`).
- **Branch A (Raw CSI) Construction (`PhysicsCSIPreprocessor.process_raw_representation`):**
  1. *Amplitude Extraction:* Complex magnitude $|H(t, k, rx, tx)|$.
  2. *Antenna Reduction:* Mean-pooling across the 3 antennas $\rightarrow (T_{\text{packets}}, 30)$.
  3. *Subcarrier Interpolation:* 1D linear interpolation from 30 subcarriers (`np.linspace(0, 1, 30)`) to 56 target subcarriers (`np.linspace(0, 1, 56)`) $\rightarrow (T_{\text{packets}}, 56)$.
  4. *Temporal Resampling:* 1D linear interpolation along time axis from $T_{\text{packets}}$ to $T=50$ timesteps $\rightarrow (50, 56)$.
  5. *Normalization:* **Global scalar z-score normalization** over all $50 \times 56 = 2,800$ elements:
     $$\text{resampled} = \frac{\text{resampled} - \mu_{\text{global}}}{\sigma_{\text{global}} + 10^{-8}}$$
  6. *Tensor Dtype:* `torch.float32`, shape `[50, 56]`.
- **Branch B (Doppler Frequency Spectrum) Construction (`PhysicsCSIPreprocessor.process_doppler_representation`):**
  1. *Differential Phase:* Cross-antenna conjugate multiplication $S(t, k) = H_1(t, k) \cdot H_2^*(t, k)$ to cancel packet-level CFO and SFO.
  2. *Static Multipath Subtraction:* Temporal mean subtraction along time axis:
     $$\tilde{S}(t, k) = S(t, k) - \frac{1}{T}\sum_{\tau} S(\tau, k)$$
  3. *STFT Computation:* Short-Time Fourier Transform computed per subcarrier using `scipy.signal.stft` with:
     - Sampling frequency: $f_s = 1000.0\text{ Hz}$
     - Window: Hann, $N_{\text{perseg}} = \min(64, T)$
     - Overlap: $N_{\text{noverlap}} = \min(48, N_{\text{perseg}} - 1)$
     - FFT points: $N_{\text{fft}} = \max(128, N_{\text{perseg}})$
     - Two-sided spectrum: `return_onesided=False`
  4. *Frequency Centering:* `np.fft.fftshift` along frequency axis so that $0\text{ Hz}$ (DC) is centered.
  5. *Power Averaging:* Magnitude squared $|Z_{xx}(f, t)|^2$ averaged across all 30 subcarriers.
  6. *Log-Power Conversion:* $P_{\text{log}}(f, t) = 10 \log_{10}(P(f, t) + 10^{-8})$.
  7. *2D Spline Interpolation:* `scipy.interpolate.RectBivariateSpline` from $(T_{\text{stft}}, F_{\text{stft}})$ to target grid $(50, 56)$.
  8. *Normalization:* Global scalar z-score normalization over the resulting $(50, 56)$ matrix.
  9. *Tensor Dtype:* `torch.float32`, shape `[50, 56]`.

---

### 3.2 NTU-Fi HAR Dataset Path (Classes 6–11: `box`, `circle`, `clean`, `fall`, `run`, `walk`)

- **Physical Sensor:** Qualcomm Atheros AR9580 NIC (802.11n HT40, 5.0 GHz band).
- **Source Dimensions:** Pre-extracted amplitude matrices of shape $(342, T_{\text{packets}})$, where $342 = 3\text{ RX antennas} \times 114\text{ subcarriers}$.
- **Sampling Rate:** $100\text{ Hz}$ packet rate (`source_rate_hz=100.0`).
- **Ingestion Pipeline (`NTUFiDataset` and `CSIPreprocessor.preprocess_sample`):**
  1. *Reshaping:* Reshaped to $(3, 114, T_{\text{packets}})$.
  2. *Antenna Reduction:* Mean-pooled across antennas $\rightarrow (114, T_{\text{packets}})$.
  3. *Subcarrier Decimation:* Center-channel linear decimation via `ESP32CSIAdapter.atheros_to_esp32` from 114 subcarriers to 56 subcarriers $\rightarrow (56, T_{\text{packets}})$.
  4. *Transposition:* Transposed to $(T_{\text{packets}}, 56)$.
  5. *Butterworth Lowpass Filter:* 3rd-order Butterworth low-pass filter with normalized cutoff $W_n = 0.15$.
  6. *Hampel Outlier Removal:* Temporal Hampel filter with window length 7 and $3\sigma$ threshold.
  7. *Temporal Resampling:* Linear interpolation along time axis to $T=50$ timesteps $\rightarrow (50, 56)$.
  8. *Normalization:* Global scalar z-score normalization across all elements $\rightarrow (50, 56)$.
- **Branch A (Raw CSI) Construction:**
  - Standard preprocessed tensor `s["csi"]` from `NTUFiDataset`, shape `[50, 56]`, `torch.float32`.
- **Branch B (Doppler Frequency Spectrum) Construction — FATAL ANOMALY:**
  - In [`scratch/execute_phase13_2_dual_branch_and_benchmark.py:L323-326`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L323-L326):
    ```python
    for i in range(len(ntufi_train)):
        s = ntufi_train[i]
        nt_raw_train.append(s["csi"])
        nt_dopp_train.append(s["csi"])  # Supply csi to both branches for Atheros
    ```
  - And in the Phase 13 held-out test evaluation sets ([lines 354–362](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L354-L362)):
    ```python
    fall_dopp = fall_raw.clone()
    har_dopp = har_raw.clone()
    ```
  - **Verdict:** **STFT was completely bypassed for all NTU-Fi samples during Phase 13 training.** Branch B was assigned the raw amplitude tensor identical to Branch A.

---

### 3.3 Phase 15 Domain Adaptation Path (`models/csiformer_phase15_adapted.pth`)

- **Physical Sensor:** ESP32-S3 SoC (802.11n HT20, 2.442 GHz carrier).
- **Dataset:** 26 real physical windows from `data/real_csi_dataset/` (Laboratory_Room1).
- **Signal Representation:** Real amplitude arrays of shape `[50, 56]`.
- **Branch A Preprocessing:** Per-subcarrier (channel-wise) z-score normalization along axis 0 (`(w - mean(axis=0)) / (std(axis=0) + 1e-6)`).
- **Branch B Preprocessing:** `CalibratedPhysicsPreprocessor.compute_doppler_spectrogram(w)`:
  - STFT computed on real amplitudes with $f_s = 35.58\text{ Hz}$.
  - **2.385x Doppler frequency scaling expansion:** Frequency bins stretched by ratio $5.825\text{ GHz} / 2.442\text{ GHz} \approx 2.385$ via linear interpolation around DC (bin 28) to compensate for 2.4 GHz vs 5 GHz Doppler wavelength differences.
- **Fine-Tuning:** End-to-end backpropagation on 26 training windows using alias labels (`static -> 6`, `sit -> 8`, `push_pull -> 0`, `clap -> 2`, `walk -> 11`, `fall -> 9`).

---

## 4. Task 2 — Stage-by-Stage Parity Comparison: Training vs Production Inference

The following comprehensive audit table maps every processing stage from raw acquisition to model input, comparing the training implementation of `csiformer_phase13_best.pth` against the production implementation in `LivePipelineService`.

| Processing Stage | Phase 13 Training Implementation | Production Inference Implementation (`LivePipelineService`) | Equivalent, Different, or Unknown | Evidence (File & Symbol) | Impact on Model Input |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **1. Window Sizing & Stride** | Widar: Variable burst (1,000–2,500 frames) resampled to 50 timesteps.<br>NTU-Fi: Fixed 50-step resampled sequence. | Slices fixed continuous ring buffer: window length $W=50$, update stride $S=1$ to $S=10$. | **DIFFERENT** | [`execute_phase13_2_dual_branch_and_benchmark.py:261`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L261)<br>[`live_pipeline_service.py:188`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L188) | Training windows capture entire gesture from start to finish. Live inference windows capture arbitrary 1.4-second continuous streaming slices. |
| **2. Channel Count & Grid** | Widar: 30 Intel 5300 subcarriers interpolated to 56.<br>NTU-Fi: 114 Atheros subcarriers decimated to 56. | Hardware provides 56 native subcarriers (HT20: $-28 \dots -1, +1 \dots +28$). | **EQUIVALENT (GRID)** | [`esp32_csi_adapter.py:28-32`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_csi_adapter.py#L28-L32)<br>[`live_pipeline_service.py:191`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L191) | Output shape is identical `[50, 56]`, but training channels were synthetic interpolations while production channels are physical measurements. |
| **3. Raw-Branch Normalization** | Global scalar z-score over all $50 \times 56$ values:<br>`(resampled - mean) / (std + 1e-8)` | Channel-wise (column-wise) z-score along axis 0:<br>`amp_mean = raw_win.mean(axis=0)`<br>`norm = (raw_win - amp_mean) / amp_std` | **DIFFERENT** | [`physics_csi_preprocessor.py:265`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py#L265)<br>[`live_pipeline_service.py:195-197`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L195-L197) | In live inference, frequency-selective subcarrier attenuation profile is completely erased (each column forced to variance 1). In training, subcarrier profile shape was preserved. |
| **4. Doppler Construction (Widar: Classes 0–5)** | STFT on dynamic complex CSI ($f_s=1000\text{ Hz}$, $N_{\text{perseg}}=64$, $N_{\text{fft}}=128$, carrier 5.2 GHz). | STFT on real amplitude matrix ($f_s=30.0\text{ Hz}$, $N_{\text{perseg}}=32$, $N_{\text{fft}}=64$, carrier 2.442 GHz). | **DIFFERENT** | [`physics_csi_preprocessor.py:200-205`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py#L200-L205)<br>[`live_pipeline_service.py:61-63`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L61-L63) | Training used complex CSI separating positive and negative velocities. Production STFT on real amplitude produces strictly Hermitian symmetric Doppler spectra. |
| **5. Doppler Construction (NTU-Fi: Classes 6–11)** | **STFT BYPASS:** Branch B fed identical raw amplitude tensor `s["csi"]`. | STFT computed unconditionally on all inputs via `compute_doppler_spectrogram(raw_win)`. | **FATALLY DIFFERENT** | [`execute_phase13_2_dual_branch_and_benchmark.py:326`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L326)<br>[`live_pipeline_service.py:201`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L201) | Model weights for `walk` (class 11) expect raw spatial-temporal amplitudes in Branch B, but live inference supplies a frequency-domain spectrogram. |
| **6. Sampling Rate Assumption** | Widar: 1000.0 Hz.<br>NTU-Fi: 100.0 Hz. | Hardcoded preprocessor rate: $30.0\text{ Hz}$. Physical hardware rate: $\approx 35.58\text{ Hz}$. | **DIFFERENT** | [`execute_phase13_2_dual_branch_and_benchmark.py:32`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L32)<br>[`live_pipeline_service.py:58`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L58) | Live preprocessor underestimates physical packet arrival rate by $\approx 18.6\%$, distorting frequency bin calibration in STFT. |
| **7. Signal Physical Nature** | Complex Phasor ($I + jQ$) in Widar; real amplitudes in NTU-Fi. | Real Amplitudes Only (Magnitude values from ESP32-S3 driver). | **DIFFERENT (WIDAR)**<br>**EQUIVALENT (NTU-FI)** | [`widar_dataset.py:208`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/datasets/widar_dataset.py#L208)<br>[`live_pipeline_service.py:170`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L170) | Prevents antenna conjugate multiplication and directional Doppler extraction for Widar-derived gesture models. |
| **8. Offline Evaluation API** | Offline batch DataLoader iterating over PyTorch tensors. | None. Service only supports live serial streaming via `predict_latest_window()`. | **DIFFERENT** | [`execute_phase13_2_dual_branch_and_benchmark.py:335`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L335)<br>[`live_pipeline_service.py:174`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L174) | Impossible to run reproducible, pre-registered evaluation through official production service without modifying code or writing ad-hoc harnesses. |
| **9. Numerical Stability & Dtype** | `torch.float32`, bounded, zero NaNs/Infs. | `torch.float32`, bounded, zero NaNs/Infs. | **EQUIVALENT** | [`execute_phase13_2_dual_branch_and_benchmark.py:302`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L302)<br>[`live_pipeline_service.py:198,202`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L198-L202) | Memory precision and GPU tensor handling are fully compatible. |

---

## 5. Task 3 — Evaluation of the Three-Class Proposal (`push_pull`, `clap`, `walk`)

Phase 36 demonstrated that `static` (stationary human standing still) and `sit` (chair descent) were falsely equated to `box` (dynamic arm boxing) and `clean` (table cleaning motion), and recommended investigating a restricted 3-class evaluation scope on the remaining shared activities.

We now evaluate whether this 3-class proposal is compatible at the preprocessing level:

### 5.1 Activity-by-Activity Forensic Findings

1. **`push_pull` (Unified Class Index 0):**
   - *Semantic Validity:* **VALID**. Arm pushing and pulling is physically identical between Widar 3.0 Gestures 1 & 7 and real ESP32-S3 collections.
   - *Training Contract:* Trained on Widar 3.0 with dual branches: Branch A = Raw CSI amplitude; Branch B = STFT Doppler Spectrogram.
   - *Live Service Parity:* `LivePipelineService` computes STFT Doppler for Branch B, matching the structural two-branch paradigm of Widar training. However, normalization (column-wise vs global) and sampling rate (30.0 Hz vs 35.58 Hz hardware vs 1000 Hz training) remain misaligned.

2. **`clap` (Unified Class Index 2):**
   - *Semantic Validity:* **VALID**. Two-hand rhythmic clapping is physically identical between Widar 3.0 Gestures 3 & 9 and real ESP32-S3 collections.
   - *Training Contract:* Trained on Widar 3.0 with dual branches: Branch A = Raw CSI amplitude; Branch B = STFT Doppler Spectrogram.
   - *Live Service Parity:* Identical status to `push_pull`. Dual-branch STFT structure matches, with normalization and sampling rate offsets.

3. **`walk` (Unified Class Index 11):**
   - *Semantic Validity:* **VALID**. Forward human locomotion in LOS is physically identical between NTU-Fi HAR and real ESP32-S3 collections.
   - *Training Contract:* Trained on NTU-Fi HAR with **STFT BYPASS**: Branch A = Raw CSI amplitude; Branch B = **Raw CSI amplitude duplicate** ([`execute_phase13_2_dual_branch_and_benchmark.py:326`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L326)).
   - *Live Service Parity:* **FATAL BLOCKER**. `LivePipelineService` computes `compute_doppler_spectrogram(raw_win)` and feeds the resulting log-power frequency spectrogram into Branch B. This feeds an entirely different physical representation into Branch B's encoder than what the network learned for `walk`.

### 5.2 The Fundamental Inference Dilemma

At inference time, an evaluation engine or production classifier receives an unlabeled window $W \in \mathbb{R}^{50 \times 56}$ and must output predicted class probabilities:
- To achieve parity for `push_pull` (0) and `clap` (2), Branch B must receive an **STFT Doppler Spectrogram**.
- To achieve parity for `walk` (11), Branch B must receive a **Raw CSI duplicate** ($W_{\text{raw}}$).

**An unlabeled, production-grade inference service cannot know a priori which preprocessing branch to execute without knowing the ground-truth class label.** Applying class-dependent preprocessing during evaluation would constitute ground-truth target leakage. Conversely, applying uniform STFT preprocessing corrupts the feature representation for `walk`.

---

## 6. Task 4 — Minimal Corrective Design & Risk Analysis

To restore end-to-end preprocessing parity without violating non-negotiable project protections (no unauthorized checkpoint modifications, no data mutations, no model forward passes without protocol clearance), we evaluate candidate remediation strategies:

### Candidate Approach Comparison

| Approach | Description | Parity Restored? | Retains Checkpoints? | Risks & Limitations |
| :--- | :--- | :---: | :---: | :--- |
| **Approach 1: Uniform Live Pipeline STFT** | Evaluate all 3 classes through `LivePipelineService`'s existing preprocessor. | **NO (Fails on `walk`)** | YES | Destroys evaluation validity for `walk`. Model penalized for preprocessor mismatch, not cross-room generalization. |
| **Approach 2: Source-Specific Evaluation Adapter** | Branch preprocessor based on ground-truth label (STFT for Widar classes; raw duplicate for NTU-Fi). | **PARTIAL (Synthetic)** | YES | **Scientifically Invalid**: Constitutes ground-truth target leakage. Cannot be deployed in live production. |
| **Approach 3: Dedicated Offline Preprocessor with Calibrated Parameters** | Create a standalone `OfflineEvaluationPreprocessor` implementing global scalar z-score and 35.58 Hz STFT rate. | **PARTIAL** | YES | Fixes normalization and rate calibration for `push_pull` and `clap`, but leaves the NTU-Fi `walk` STFT bypass unresolved. |
| **Approach 4: Standardized Adaptation / Retraining Protocol (Recommended Future Step)** | Formulate a pre-registered retraining or head-adaptation protocol that trains on a uniform dual-branch contract (Raw + STFT Doppler) across all classes. | **FULL** | Requires New Authorized Checkpoint | Requires a dedicated retraining phase. Protected checkpoints remain frozen as historic baselines. |

### The Smallest Safe Next Step:
Because no inference-time transformation can resolve the contradictory training-time Branch B representations (STFT vs Raw duplicate) in an unlabeled setting, **evaluation must remain HALTED**. The project must not execute ad-hoc inference scripts that paper over these architectural discrepancies.

---

## 7. Task 5 — Deterministic Test Suite Execution & Outcomes

A dedicated test suite [`backend/tests/test_phase37.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase37.py) was implemented to deterministically validate all audit findings without executing model forward passes or loading checkpoint weights.

### 7.1 Unit Tests in `backend/tests/test_phase37.py`:
1. `test_phase37_checkpoint_md5_protection`: Re-verifies production and experimental checkpoint MD5 hashes against reference values.
2. `test_phase37_training_source_code_disparity_reconstruction`: Verifies code-level evidence of the NTU-Fi STFT bypass in `scratch/execute_phase13_2_dual_branch_and_benchmark.py`.
3. `test_phase37_production_inference_discrepancies`: Verifies `LivePipelineService` STFT parameters, channel-wise normalization vs global z-score, and absence of `predict_window`.
4. `test_phase37_three_class_audit_and_walk_branch_b_blocker`: Validates semantic validity of the 3 classes and demonstrates the architectural Branch B incompatibility for `walk`.
5. `test_phase37_doppler_spectrogram_numerical_properties`: Confirms deterministic, finite output of `PhysicsCSIPreprocessor.compute_doppler_spectrogram` with zero NaNs/Infs.
6. `test_phase37_strict_partition_and_manifest_immutability`: Confirms dataset manifest remains unmutated and reproduces the 75/20/11/49 partition.

### 7.2 Test Execution Results:

```bash
# 1. Targeted Phase 37 Suite:
py -3.11 -m pytest backend/tests/test_phase37.py -v
# Outcome: 6 passed in 11.07s (Exit code 0)

# 2. Complete Cross-Room Protocol Suite (Phases 34–37):
py -3.11 -m pytest backend/tests/test_phase34.py backend/tests/test_phase35.py backend/tests/test_phase36.py backend/tests/test_phase37.py -v
# Outcome: 22 passed in 6.63s (Exit code 0)

# 3. Full Repository Regression Suite:
py -3.11 -m pytest backend/tests/ -v
# Outcome: 238 passed, 0 failed across all 34 test files in 71.77s (Exit code 0)
```

---

## 8. Task 6 — Checkpoint Integrity & Manifest Invariance

Checksum verification was conducted before and after all audit procedures:

| File Path | Role | Reference MD5 Hash | Actual Verified MD5 | Integrity Status |
| :--- | :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | Production Checkpoint | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | Experimental Checkpoint | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| `data/real_csi_dataset/dataset_manifest.json` | Dataset Manifest | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |

### Git Working Tree Status (`git status --short`):
- `backend/tests/test_phase37.py`: Added (Deterministic audit unit tests).
- `reports/phase37_training_inference_alignment_audit.md`: Added (This audit report).
- All raw CSV and JSON recording files: **Untouched**.
- Zero commits, pushes, cleans, or resets executed.

---

## 9. Explicit Confirmation: Inference & Training Protections

In strict compliance with project protections:
- **Model inference was NOT executed.** Zero forward passes were run against real or synthetic data.
- **Model weights were NOT loaded into instantiated networks.** State dictionaries were inspected only for tensor structure and cryptographic hash checks.
- **Model training, adaptation, fine-tuning, or retraining was NOT performed.**
- **Dataset splits and manifests were NOT altered.**

---

## 10. Single Smallest Safe Next Step

**Do NOT authorize cross-room model inference on either protected checkpoint.**

The single smallest safe next step to unblock the project is to:
1. **Formulate a Pre-Registered Retraining Protocol (Phase 38):**
   Define a unified dual-branch preprocessing standard where all classes (Widar gestures, NTU-Fi activities, and real ESP32-S3 recordings) are preprocessed using an identical, physically consistent signal chain:
   - Branch A: Raw amplitude CSI with standardized global or channel-wise normalization.
   - Branch B: Doppler spectrogram computed consistently on dynamic CSI at the physical hardware rate ($\approx 35.58\text{ Hz}$), with the NTU-Fi STFT bypass eliminated.
2. **Authorize Training a New Production Checkpoint (`csiformer_phase38.pth`):**
   Train this unified model under the strict cross-room partition, preserving `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` frozen and untouched as historical baselines.
