# Phase 57 Report: Live-vs-Training Preprocessing Parity and Collector Integrity

## Executive Summary

Phase 57 resolves the critical preprocessing divergence and packet-loss accounting conflation identified in Phase 56.2 through an offline, audit-first, mathematically rigorous engineering intervention. Prior to this phase, live production inference deployed in [LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) diverged drastically from the authoritative training pipeline used to train the protected Phase 15 adapted checkpoint ([csiformer_phase15_adapted.pth](file:///C:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth)), exhibiting a maximum tensor error of $3.0318$ and an RMSE of $1.0862$ across identical input windows. Furthermore, [RealCSICollector](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) conflated intentional MAC-level target filtering with physical packet loss, counting ambient Wi-Fi probe requests and non-target beacons as dropped records.

Through surgical modifications that strictly preserve backward compatibility and protect existing assets:
1. **Authoritative Preprocessing Provenance Established:** Sourced directly from [execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py), documenting Branch A (per-subcarrier temporal z-score) and Branch B (STFT with Hann window, DC notch, 2D B-spline interpolation, and 2.385x Doppler frequency expansion).
2. **Deterministic Parity Demonstrated:** Implemented explicit checkpoint-associated preprocessor configuration in [LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py). When configured for Phase 15, live inference and training reference achieve bit-level exact numerical parity ($0.0000$ absolute error) across synthetic fixed-seed complex arrays, constant static signals, and known-frequency sinusoids. Default Phase 13 configuration is strictly preserved.
3. **Collector Sequence-Gap and Loss Accounting Decoupled:** Isolated firmware callback sequence tracking from host-side MAC filtering. Confirmed transport loss now measures true serial delivery drops, while target sequence gaps and ambient filtering counts are tracked independently. 32-bit unsigned wraparound ($2^{32}-1 \to 0$) and firmware reboots are handled without false loss or negative counters.
4. **Comprehensive Regression Passed:** All 45 unit and integration tests across Phases 52, 55, 55.1, 56, 56.1, 56.2, and 57 passed without errors.
5. **Operational Status:** Physical acquisition-rate adequacy remains **UNVERIFIED**. Hardware communication, COM5 access, firmware builds, flashing, network stimulation, and model retraining were strictly excluded.

---

## 1. Gate 0 — Integrity and Change Control

Before and after all modifications, the bit-level integrity of the three protected assets was cryptographically verified via MD5 checksums.

### 1.1 Protected Hash Ledger

| Asset Path | Expected MD5 Hash | Measured MD5 Hash | Verification Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383B4D98C08F8970B0443738F170EC01` | **PASS (EXACT MATCH)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `AB3D97A04D78EDF75D807178772BC828` | **PASS (EXACT MATCH)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `A58E1280FB2C0A6649335A9A381D00C6` | **PASS (EXACT MATCH)** |

### 1.2 Change Control Invariance

- **Firmware flashing / builds:** Zero attempts, no PlatformIO execution, no binaries compiled.
- **Hardware interface:** COM5 port was never opened or polled.
- **Network traffic:** Zero packets transmitted; no active UDP stimulation generated.
- **Model checkpoints & manifest:** Zero bytes modified; checkpoints and manifest kept read-only.
- **Git operations:** Zero commits or pushes performed. Existing working-tree changes from earlier phases were inspected and preserved intact.

---

## 2. Task 1 — Authoritative Training Preprocessing Provenance

To eliminate speculation, the exact preprocessing pipeline used to generate [csiformer_phase15_adapted.pth](file:///C:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) was reconstructed from [scratch/execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py) and [scratch/evaluate_phase15_baseline.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/evaluate_phase15_baseline.py).

### 2.1 Branch A: Raw Spatial-Spectral Branch

```
Raw Window w in R^{50 x 56}
       │
       ▼
Per-Subcarrier Mean & Std along Temporal Axis (t = 0..49)
   μ_k = (1/50) Σ_t w[t, k]
   σ_k = sqrt((1/50) Σ_t (w[t, k] - μ_k)^2) + 1e-6
       │
       ▼
Z-Score Standardization: t_raw[t, k] = (w[t, k] - μ_k) / σ_k
       │
       ▼
Final Tensor Shape: [1, 50, 56], dtype: torch.float32
   Mean per subcarrier: 0.000, Std per subcarrier: 1.000
```

1. **Input Representation:** 50 consecutive CSI amplitude frames across 56 subcarriers (aligned from raw 64-bin FFT using linear interpolation to HT20 56 tones).
2. **Channel Selection:** Real-valued magnitudes $|H(t, k)| = \sqrt{I^2 + Q^2}$.
3. **Normalization:** Column-wise (per-subcarrier) temporal z-score standardization. Each subcarrier column has zero mean and unit variance.
4. **Dtype & Numerical Range:** `torch.float32`, bounded typically within $[-3.0, +3.0]$.

### 2.2 Branch B: Doppler Frequency Spectrum (DFS) Branch

```
Raw Window w in R^{50 x 56}
       │
       ▼
Static Multipath / DC Notch Filtering (Temporal Mean Subtraction)
   w_dyn[t, k] = w[t, k] - mean_t(w[:, k])
       │
       ▼
Short-Time Fourier Transform (STFT) per Subcarrier k = 0..55
   Parameters: nperseg = min(64, 50) = 50, noverlap = min(48, 49) = 48,
               nfft = max(128, 50) = 128, window = 'hann', fs = 35.58 Hz
       │
       ▼
Two-Sided Power Spectrum & Subcarrier Averaging
   Zxx_shifted = fftshift(Zxx, axes=0)
   P[f, t] = (1/56) Σ_k |Zxx_shifted_k[f, t]|^2
       │
       ▼
Log Compression (Decibels): dfs_log = 10 * log10(P + 1e-8) -> [3, 128]
       │
       ▼
2D RectBivariateSpline Interpolation to [50, 56]
       │
       ▼
Global 2D Z-Score Normalization: base_dopp = (dfs - mean(dfs)) / std(dfs)
       │
       ▼
Doppler Carrier Scale Expansion (2.385x Stretching)
   center = 28, f_old = arange(56) - 28, f_new = f_old / (5.825 / 2.442)
   rescaled_dopp[t] = interp(f_old, f_new, base_dopp[t])
       │
       ▼
Final Tensor Shape: [1, 50, 56], dtype: torch.float32
```

1. **Input Representation:** Same 50-frame slice $w \in \mathbb{R}^{50 \times 56}$.
2. **Static Component Subtraction:** Temporal mean subtracted per subcarrier, removing static wall/floor reflections and torso static bounce.
3. **STFT Parameters:** `stft_window = 64` (effective `nperseg = 50`), `stft_noverlap = 48`, `stft_nfft = 128`, Hann window, 2-sided FFT.
4. **Log Compression:** $10 \log_{10}(P_{\text{avg}} + 10^{-8})\text{ dB}$.
5. **Spatial-Temporal Resampling:** 2D B-spline mapping from $[0, 1] \times [0, 1]$ source coordinates $(3 \times 128)$ onto target grid $(50 \times 56)$.
6. **Standardization:** Global 2D z-score across all 50 time steps and 56 frequency bins.
7. **Doppler Carrier Scale Correction:** Frequency bins stretched by a factor of:
   $$\text{doppler\_scale} = \frac{5.825\text{ GHz}}{2.442\text{ GHz}} \approx 2.385258$$
   This maps 2.442 GHz Doppler shifts into the 5.825 GHz velocity scale expected by the dual-branch backbone.

---

## 3. Task 2 & Task 3 — Preprocessing Discrepancy & Parity Resolution

### 3.1 Pre-Fix Divergence Analysis

Prior to Phase 57, [LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) instantiated an uncalibrated preprocessor:
- `stft_window = 32` (vs training reference `64` $\to$ effective `50`)
- `stft_noverlap = 24` (vs training reference `48`)
- `stft_nfft = 64` (vs training reference `128`)
- `doppler_scale = 1.0` (unscaled; missing the 2.385x carrier frequency expansion)

This produced severe numerical distortion:

| Preprocessing Stage | Phase 15 Training Reference | Pre-Fix Live Pipeline | Numerical Divergence |
| :--- | :--- | :--- | :--- |
| **Branch A (Raw)** | Column-wise Z-score `(1, 50, 56)` | Column-wise Z-score `(1, 50, 56)` | $\Delta = 0.0000$ (Parity already held) |
| **STFT Window (`nperseg`)** | $50$ ($\min(64, 50)$) | $32$ | Spectral leakage & frequency resolution mismatch |
| **STFT Overlap (`noverlap`)** | $48$ | $24$ | Temporal hop size of 2 vs 8 samples |
| **STFT FFT Bins (`nfft`)** | $128$ | $64$ | 2x lower frequency grid resolution |
| **Doppler Scale Expansion** | $2.385\times$ ($5.825 / 2.442$) | $1.000\times$ (Unscaled) | Dynamic range compressed by $58\%$ |
| **Branch B Doppler Output** | Normalized DFS `(1, 50, 56)` | Normalized DFS `(1, 50, 56)` | **Max Diff: 3.0318, RMSE: 1.0862** |

An RMSE of $1.0862$ on unit-variance standardized features represents catastrophic input corruption, invalidating physical model inferences.

### 3.2 Implemented Software Correction

In [backend/app/services/live_pipeline_service.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py):
1. **Explicit Checkpoint Association:** Added `configure_preprocessor_for_checkpoint(checkpoint_id)`:
   - When `checkpoint_id="phase15"`: Instantiates [CalibratedPhysicsPreprocessor](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py) with `stft_window=64, stft_noverlap=48, stft_nfft=128, doppler_scale=2.385258, source_rate_hz=35.58`.
   - When `checkpoint_id="phase13"` (default): Preserves `PhysicsCSIPreprocessor` with `stft_window=32, stft_noverlap=24, stft_nfft=64, source_rate_hz=30.0`.
2. **Unified Window Preprocessing Method:** Added `preprocess_window(raw_win)` returning `(tensor_raw, tensor_dopp)` for deterministic offline pipeline verification.
3. **Clean Contract Preservation:** Did not add `predict_window` to strictly respect existing [test_phase37.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase37.py) contract assertions (`assert not hasattr(service, "predict_window")`).
4. **Enhanced Preprocessor Signature:** Extended [CalibratedPhysicsPreprocessor](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py) to accept optional `stft_window`, `stft_noverlap`, `stft_nfft`, and `doppler_scale` parameters.

### 3.3 Post-Fix Deterministic Parity Evidence

Evaluated on synthetic test vectors in [test_phase57.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py):

| Test Vector Description | Branch A Max Diff | Branch B Max Diff | RMSE Error | Parity Status |
| :--- | :--- | :--- | :--- | :--- |
| **Fixed-Seed Random Complex ($50 \times 56$)** | $0.000000$ | $0.000000$ | $0.000000$ | **CONFIRMED EXACT PARITY** |
| **Constant / Near-Static Signal ($A_k = 28.5$)** | $0.000000$ | $0.000000$ | $0.000000$ | **CONFIRMED EXACT PARITY** |
| **Synthetic Sinusoid ($f_0 = 3.0\text{ Hz}$)** | $0.000000$ | $0.000000$ | $0.000000$ | **CONFIRMED EXACT PARITY** |
| **Phase 13 Baseline Check (Uncalibrated)** | $0.000000$ | $1.842105$ | $0.624119$ | **EXPECTED DIVERGENCE CONFIRMED** |

---

## 4. Task 4 — Sequence-Gap and Loss Accounting Semantics

### 4.1 Tri-Counter Architectural Disambiguation

An in-depth audit of [firmware/esp32s3_csi_collector/main/main.c](file:///C:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c) and [backend/app/services/real_csi_collector.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) identified three fundamentally distinct sequence counters:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Firmware CSI-Callback Counter (packet_sequence in main.c)                           │
│    - Location: wifi_csi_cb() in firmware C code.                                       │
│    - Scope: Increments on EVERY packet received on Wi-Fi Channel 7.                    │
│    - Transmitted: As the 5th token in CSI_DATA and CSI_DATA_V2 ASCII telemetry lines.  │
│    - Nature: Global hardware callback sequence; NO MAC filtering exists in firmware.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. 802.11 MAC Frame Sequence Number (info->rx_ctrl.seq)                                │
│    - Location: 802.11 MAC Header parsed by ESP-IDF baseband.                           │
│    - Scope: Per-transmitter, 12-bit modulo 4096 (0..4095) sequence number.             │
│    - Transmitted: As rx_seq in structured CSI_DATA_V2 telemetry.                        │
│    - Nature: Reflects source Wi-Fi transmitter sequence; resets and wraps frequently.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Host Serial Record Count (collector.packets_received)                               │
│    - Location: RealCSICollector on host PC.                                            │
│    - Scope: Monotonically increments for each admitted target frame.                   │
│    - Nature: Local software ingestion count; insensitive to hardware packet loss.      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Root Cause of Loss Overestimation

In [RealCSICollector._process_parsed_frame](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py), target MAC filtering was executed *before* sequence gap tracking:
```python
if self.filter_by_mac:
    if source_mac_norm != self.target_mac:
        self.filtered_non_target_packets += 1
        return  # Exits before updating self.last_sequence!

# Subsequent target packet arrives:
gap = seq - (self.last_sequence + 1)
if gap > 0:
    self.packets_lost += gap  # Ambient frames erroneously added to packet loss!
```

Because ambient devices (smartphones, neighbor APs, IoT nodes) emit packets on Channel 7, every ambient packet received by the ESP32 incremented the firmware counter. When the collector dropped these ambient packets, the gap between consecutive target packets was attributed to packet loss, inflating `packets_lost` to over $90\%$ under passive ambient conditions despite perfect serial delivery.

### 4.3 Implemented Collector Architecture

The sequence tracking pipeline in [RealCSICollector](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) was restructured into three decoupled stages:

1. **Stage 1: Physical Firmware Stream Continuity (Pre-Filter):**
   - Evaluated across ALL received frames regardless of MAC address.
   - Computes $f_{\text{gap}} = \text{seq} - (\text{last\_firmware\_seq} + 1)$.
   - If $f_{\text{gap}} > 0$: An actual physical frame was dropped over UART/serial transport between the ESP32 and host PC. Increments `self.firmware_sequence_gaps` and `self.confirmed_transport_loss`.
   - Handles 32-bit unsigned wraparound ($0\text{xFFFFFFFF} \to 0\text{x00000000}$) without false loss.
   - Detects firmware reboots / counter restarts ($\text{seq} < \text{last\_firmware\_seq}$) and increments `self.counter_resets` without adding spurious gaps.
2. **Stage 2: Target-Source Filtering:**
   - Evaluates transmitter MAC address against `self.target_mac`.
   - Non-target frames increment `self.filtered_non_target_packets` and return.
   - Malformed frames increment `self.parse_errors` and return.
3. **Stage 3: Target Sequence Tracking (Post-Filter):**
   - For admitted target frames, computes $t_{\text{gap}} = \text{seq} - (\text{last\_sequence} + 1)$.
   - Increments `self.target_sequence_gaps`. This measures total spacing between target arrivals (comprising ambient non-target frames + true transport drops).
   - Sets `self.packets_lost = self.confirmed_transport_loss`.
4. **Stage 4: Mathematical Loss Accounting Reconciled:**
   $$\text{target\_sequence\_gaps} \equiv \text{filtered\_non\_target\_packets} + \text{confirmed\_transport\_loss}$$
   $$\text{packet\_loss\_pct} = \frac{\text{confirmed\_transport\_loss}}{\text{packets\_received} + \text{filtered\_non\_target\_packets} + \text{confirmed\_transport\_loss}} \times 100\%$$

---

## 5. Summary of Files Changed

| File Path | Nature of Change | Architectural Rationale |
| :--- | :--- | :--- |
| [backend/app/services/live_pipeline_service.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) | Modified | Added explicit `configure_preprocessor_for_checkpoint` and `preprocess_window` to eliminate the 3.0318 tensor divergence when using Phase 15 checkpoint. Maintained Phase 13 default. |
| [backend/app/services/physics_csi_preprocessor.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py) | Modified | Extended `CalibratedPhysicsPreprocessor.__init__` to accept optional STFT parameters and Doppler scale kwargs with full backward compatibility. |
| [backend/app/services/real_csi_collector.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) | Modified | Decoupled firmware sequence tracking from MAC filtering; isolated true transport losses from intentional ambient packet filtering; handled 32-bit wraparound and reboots. |
| [backend/tests/test_phase56_2.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase56_2.py) | Modified | Aligned sequence conflation test assertion to reflect decoupled metrics (`target_sequence_gaps == 1`, `packets_lost == 0`). |
| [backend/tests/test_phase57.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py) | Created | New comprehensive test suite validating Gate 0 hashes, deterministic parity, backward compatibility, interleaved sequence decoupling, and wraparound handling. |

---

## 6. Task 5 — Regression and Test Results

The complete offline test suite was executed using Python 3.11.9.

### 6.1 Execution Command
```powershell
py -3.11 -m pytest backend/tests/test_phase52.py backend/tests/test_phase55.py backend/tests/test_phase55_1.py backend/tests/test_phase56.py backend/tests/test_phase56_1.py backend/tests/test_phase56_2.py backend/tests/test_phase57.py
```

### 6.2 Test Results Ledger

| Test Suite File | Passed | Failed | Skipped | Execution Time | Key Covered Areas |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `backend/tests/test_phase52.py` | 5 | 0 | 0 | 2.1s | Gate 0 MD5, source MAC filtering, HT20 64-bin carrier masks, fail-closed policy. |
| `backend/tests/test_phase55.py` | 5 | 0 | 0 | 2.0s | Gate 0 MD5, passive rate gate fail-closed, sequence reconciliation logic. |
| `backend/tests/test_phase55_1.py` | 7 | 0 | 0 | 2.3s | Gate 0 MD5, record count vs rate separation, window span definitions, spatial interpolation. |
| `backend/tests/test_phase56.py` | 7 | 0 | 0 | 2.2s | Gate 0 MD5, calibration stage transitions, stop conditions, serial baud budget. |
| `backend/tests/test_phase56_1.py` | 6 | 0 | 0 | 2.1s | Gate 0 MD5, historical rate derivation, target BSSID capture rates, active vs passive. |
| `backend/tests/test_phase56_2.py` | 5 | 0 | 0 | 2.0s | Gate 0 MD5, source_rate_hz invariance, STFT divergence audit, decoupled sequence metrics. |
| `backend/tests/test_phase57.py` | 10 | 0 | 0 | 2.2s | Gate 0 MD5, 3 synthetic parity tests, backward compatibility, interleaved loss decoupling, wraparound, counter reset, tri-counter distinction. |
| **Total Comprehensive Suite** | **45** | **0** | **0** | **14.96s** | **100% Passing Rate across All Regression Tests** |

In addition, standalone regression suites for earlier phases were validated:
- `backend/tests/test_phase37.py`: 6 passed (verifying `assert not hasattr(service, "predict_window")` and Phase 13 preprocessor parameters).
- `backend/tests/test_phase21.py`: 17 passed (verifying diagnostic state machine and health reporting).

---

## 7. Remaining Unknowns and Blockers

1. **Physical Acquisition-Rate Adequacy: UNVERIFIED**
   - Resolving preprocessing parity in software and decoupling sequence loss accounting in collector telemetry does NOT increase the physical rate of passive Wi-Fi packets captured from the environment.
   - Under passive sensing without network stimulation, target-BSSID CSI packet rates remain at $1.66\text{--}3.8\text{ Hz}$, spanning $13\text{--}30\text{ seconds}$ per 50-frame window.
   - Whether active network stimulation (e.g. UDP traffic generation) or firmware-level promiscuous ACK listening can reliably sustain the empirical training rate ($\approx 35\text{ Hz}$) on hardware remains to be evaluated in authorized future hardware phases.
2. **Phase 15 Checkpoint Generalization on Live Signals:**
   - While software parity between training reference and live inference is now mathematically exact ($0.0000$ error), live inference performance on real human subjects depends on temporal continuity. Model inference accuracy under real non-uniform packet inter-arrival intervals has not yet been benchmarked on physical hardware.
3. **Hardware Microsecond Timestamp Availability in Running Firmware:**
   - The active firmware flashed to the ESP32-S3 emits Format B (`CSI_DATA`) without microsecond hardware timestamps (`hw_timestamp_us`). Hardware timestamps will only become available when Format B v2 (`CSI_DATA_V2`) firmware is compiled and flashed under authorized hardware change control.

---

## 8. Conclusion and Sign-Off

Phase 57 successfully achieves its objectives:
- **Preprocessing parity** is mathematically proven and deterministic ($0.0000$ error against the verified Phase 15 training reference).
- **Collector loss accounting** separates observed sequence gaps from confirmed serial drops, preventing ambient Wi-Fi traffic from distorting loss percentages.
- **Change control and asset integrity** were preserved without deviation (all protected MD5 hashes match, zero uncommitted work destroyed).
- **Physical acquisition-rate adequacy** is explicitly recorded as **UNVERIFIED**.
