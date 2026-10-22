# Phase 57.1 Report: Independent Integration Readiness Audit

## Executive Summary

Phase 57.1 performs an independent, audit-first review of Phase 57's source modifications, mathematical parity claims, checkpoint routing mechanisms, and collector packet-loss accounting semantics prior to authorizing any future physical hardware calibration.

Prior to Phase 57, a significant preprocessing divergence existed between live inference ([LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py)) and the authoritative training pipeline for the protected adapted model ([csiformer_phase15_adapted.pth](file:///C:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth)), yielding a maximum tensor error of $3.0318$ and an RMSE of $1.0862$. In addition, [RealCSICollector](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) conflated intentional MAC-layer target filtering with physical transport packet loss.

Phase 57 implemented software corrections to resolve both issues. This independent audit evaluated these changes and discovered three subtle vulnerabilities:
1. **Self-Referential Parity Risk:** Initial Phase 57 parity tests compared `LivePipelineService.preprocess_window()` against `CalibratedPhysicsPreprocessor` from the same backend service package rather than directly against the historical training script ([scratch/execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py)). An independent test was authored, confirming bit-level exact parity ($0.0000$ error) directly against the historical script.
2. **Permissive Fallback in Checkpoint Routing:** `configure_preprocessor_for_checkpoint` previously fell back to Phase 13 for any unrecognized checkpoint ID rather than failing closed. This was corrected: unsupported IDs now raise `ValueError`, and non-existent checkpoint files raise `FileNotFoundError` atomically without mutating internal preprocessor state.
3. **Out-of-Order / Reboot Sequence Ambiguity:** In `RealCSICollector`, a sequence drop condition checked `seq < 50`, causing low-numbered out-of-order packets (e.g., sequence 12 arriving after sequence 13) to be misclassified as counter reboots. This was refined to isolate true reboots (`(last - seq) > 1000` or `last >= 100 and seq <= 10`) from out-of-order jitter (`out_of_order_packets`), and explicit duplicate tracking (`duplicate_packets`) was added.

All 48 unit and integration tests across Phases 52, 55, 55.1, 56, 56.1, 56.2, and 57 pass with a 100% pass rate. All three protected asset hashes remain bit-for-bit pristine. Physical acquisition-rate adequacy remains **UNVERIFIED**.

---

## 1. Gate 0 — State Preservation and Cryptographic Hash Ledger

Before and after all audit operations, the three protected repository assets were verified via MD5 checksums.

### 1.1 Protected Hash Ledger

| Protected Asset Path | Expected MD5 Hash | Measured MD5 Hash | Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **PASS (EXACT MATCH)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **PASS (EXACT MATCH)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **PASS (EXACT MATCH)** |

### 1.2 Constraint Compliance
- **Hardware Access:** COM5 serial port was never opened or probed.
- **Network Stimulation:** Zero packets transmitted; no active UDP stimulators generated.
- **Firmware:** No binaries compiled, no PlatformIO commands invoked, zero flashing attempts.
- **Git State:** No commits, resets, cleanups, or pushes performed. Uncommitted working-tree modifications from earlier audit phases were inspected and preserved intact.

---

## 2. Task 1 — Independent Verification of Preprocessing Parity

### 2.1 The Independence Audit
In Phase 57, `test_phase57.py` imported `CalibratedPhysicsPreprocessor` from `backend.app.services.physics_csi_preprocessor` and compared it against `LivePipelineService.preprocess_window()`. Because `LivePipelineService` internally instantiates that exact same class, this raised the concern of **self-consistency verification** rather than true **historical reference parity**.

To resolve this concern independently:
1. The historical benchmark script [scratch/execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py) was audited. Lines 51–76 define the original `CalibratedPhysicsPreprocessor` directly within the script that produced [models/csiformer_phase15_adapted.pth](file:///C:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth).
2. A direct cross-script test (`test_phase57_independent_training_script_reference_parity`) was added to [backend/tests/test_phase57.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py). This test imports `CalibratedPhysicsPreprocessor` directly from `scratch.execute_phase15_adaptation_benchmark` as an external reference and compares it to `LivePipelineService.preprocess_window()`.

### 2.2 Branch-by-Branch Numerical Comparison

| Signal Processing Dimension | Historical Training Reference ([execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py)) | Current Live Implementation ([LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py)) | Measured Max Difference | Numerical Equivalence |
| :--- | :--- | :--- | :--- | :--- |
| **Input Representation** | 50 temporal frames $\times$ 56 subcarriers float32 | 50 temporal frames $\times$ 56 subcarriers float32 | `0.00000000` | **IDENTICAL** |
| **Branch A Normalization** | Column-wise temporal z-score (`(win - mean) / (std + 1e-6)`) along axis 0 | Column-wise temporal z-score (`(win - mean) / (std + 1e-6)`) along axis 0 | `0.00000000` | **IDENTICAL** |
| **Branch A Shape & Range** | Shape `[1, 50, 56]`, dtype `float32`, per-column mean 0, std 1 | Shape `[1, 50, 56]`, dtype `float32`, per-column mean 0, std 1 | `0.00000000` | **IDENTICAL** |
| **STFT Window & Overlap** | Hann window $N_w = 64$, overlap $N_o = 48$, hop $N_h = 16$ | Hann window $N_w = 64$, overlap $N_o = 48$, hop $N_h = 16$ | `0.00000000` | **IDENTICAL** |
| **STFT FFT Size** | $N_{fft} = 128$, `return_onesided=False`, two-sided centered FFT | $N_{fft} = 128$, `return_onesided=False`, two-sided centered FFT | `0.00000000` | **IDENTICAL** |
| **DC Component Handling** | Method="mean", central DC notch at bin 28 | Method="mean", central DC notch at bin 28 | `0.00000000` | **IDENTICAL** |
| **Doppler Frequency Scaling** | $\alpha = 5.825 / 2.442 = 2.38533989...$, 1D linear interpolation across frequency bins per time step around DC bin 28 | $\alpha = 5.825 / 2.442 = 2.38533989...$, 1D linear interpolation across frequency bins per time step around DC bin 28 | `0.00000000` | **IDENTICAL** |
| **2D Spatial Resampling** | `RectBivariateSpline` to target shape `[50, 56]` | `RectBivariateSpline` to target shape `[50, 56]` | `0.00000000` | **IDENTICAL** |
| **Branch B Shape & Range** | Shape `[1, 56, 50]`, dtype `float32`, finite values bounded in $[-1.0, 1.0]$ | Shape `[1, 56, 50]`, dtype `float32`, finite values bounded in $[-1.0, 1.0]$ | `0.00000000` | **IDENTICAL** |

### 2.3 Classification
Because the live inference pipeline matches the historical script's class byte-for-byte and float-for-float ($0.00000000$ error across all dimensions), the finding is:
👉 **VERIFIED OFFLINE** (Both Self-Consistency and Historical Reference Parity are confirmed).

---

## 3. Task 2 — Checkpoint Routing and Fail-Closed Configuration Audit

### 3.1 Defect Identified in Initial Implementation
In Phase 57's initial implementation:
```python
# Initial Phase 57 code
cid = str(checkpoint_id).lower()
if "phase15" in cid:
    self.preprocessor = CalibratedPhysicsPreprocessor(...)
    self.active_checkpoint_id = "phase15"
else:
    self.preprocessor = PhysicsCSIPreprocessor(...)
    self.active_checkpoint_id = "phase13"
```
If an unknown or malformed checkpoint string was passed (e.g. `checkpoint_id="phase99_experimental"`), the method silently fell back to Phase 13 defaults without notifying the caller.

### 3.2 Corrective Engineering Applied
In [backend/app/services/live_pipeline_service.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py):
1. **Fail-Closed Preprocessor Configuration:**
   ```python
   elif "phase13" in cid or cid == "default":
       self.preprocessor = PhysicsCSIPreprocessor(...)
       self.active_checkpoint_id = "phase13"
   else:
       raise ValueError(f"Unknown or unsupported checkpoint_id '{checkpoint_id}'. Supported: 'phase13', 'phase15'.")
   ```
2. **Atomic Checkpoint Loading:**
   `load_checkpoint` validates that the checkpoint file exists on disk and that the checkpoint configuration can be inferred before attempting model deserialization. If an error occurs, `self.model = None` and the preprocessor configuration remains unchanged, preventing partial state mutations.
3. **Weightless Testing:**
   `configure_preprocessor_for_checkpoint()` can be invoked independently to configure and test the preprocessor pipeline without instantiating model weights or performing GPU allocation.

### 3.3 Consumer Backward Compatibility
Existing callers that invoke `LivePipelineService()` without arguments continue to initialize with the legacy Phase 13 preprocessor (`stft_window=32, stft_noverlap=24, stft_nfft=64, source_rate_hz=30.0`), preserving full compatibility with [backend/tests/test_phase37.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase37.py) and production defaults.

👉 **Finding: VERIFIED OFFLINE**

---

## 4. Task 3 — Audit of Loss Accounting Semantics

### 4.1 Tri-Counter Disambiguation

The architecture separates three distinct counters present in the system:

```
[ ESP32-S3 Firmware Callback ]
      │ packet_sequence (32-bit unsigned monotonic, Channel 7 physical arrivals)
      ▼
[ UART Serial Transport ] (921600 baud)
      │ Dropped bytes / frame corruptions
      ▼
[ Host Parser: parse_raw_telemetry_line ]
      │ Format B v2 extracts: sequence (firmware), rx_seq (802.11 MAC), hw_timestamp_us
      ▼
[ RealCSICollector: _process_parsed_frame ]
      │
      ├──> Evaluate packet_sequence BEFORE filtering:
      │      - If seq > last + 1: f_gap = seq - (last + 1)
      │        firmware_sequence_gaps += f_gap
      │        confirmed_transport_loss += f_gap
      │      - If seq == last: duplicate_packets += 1
      │      - If seq < last:
      │          - 32-bit wraparound (0xFFFFFFFF -> 0): f_gap handled cleanly
      │          - Genuine reboot (last - seq > 1000 or last >= 100 and seq <= 10): counter_resets += 1
      │          - Out-of-order jitter: out_of_order_packets += 1 (high-water mark preserved)
      │
      ├──> Source MAC Filtering (filter_by_mac=True):
      │      - If MAC != target_mac:
      │          filtered_non_target_packets += 1 (DOES NOT increment packets_lost!)
      │          return
      │
      └──> Admitted Target Records:
             packets_received += 1
             target_sequence_gaps tracked independently
```

### 4.2 Precision in Loss Semantics
A gap in `packet_sequence` observed by the host indicates that the ESP32 received frames on Channel 7 that did not reach admitted host frames. This can occur due to:
1. UART transmission drops (framing errors, buffer overflows in FTDI/CH343).
2. Serial line truncation causing JSON/CSV parsing rejection (`parse_errors`).
3. Host OS serial buffer exhaustion.

By decoupling `firmware_sequence_gaps` from `filtered_non_target_packets`:
- Ambient probe requests and beacon frames on Channel 7 are accounted for as `filtered_non_target_packets`.
- Transport gaps are recorded in `firmware_sequence_gaps` and `confirmed_transport_loss`.
- Legacy metric `packets_lost` maps strictly to `confirmed_transport_loss`.
- Interleaved streams with zero transport loss report `packet_loss_pct = 0.0%`, even in environments with heavy ambient Wi-Fi traffic.

### 4.3 Handling Edge Cases
- **32-Bit Wraparound:** Tested from `0xFFFFFFFF` to `0x00000000`. Handled without negative loss or overflow exceptions (`test_phase57_sequence_wraparound_32bit`).
- **Firmware Reboots:** Sequence drop from 5000 to 1 increments `counter_resets` and resets baseline without false loss attribution (`test_phase57_counter_reset_reboot_handling`).
- **Duplicates:** Arriving with identical sequence number increments `duplicate_packets` without false loss (`test_phase57_collector_duplicate_and_out_of_order_handling`).
- **Out-of-Order Packets:** Jittered arrivals increment `out_of_order_packets` while preserving the sequence high-water mark, preventing spurious gaps on subsequent packets.

👉 **Finding: VERIFIED OFFLINE**

---

## 5. Task 4 — Reconciliation of Regression Evidence

### 5.1 Investigation of the Test Count Discrepancy
The prompt requested investigation of a reported discrepancy: the Phase 56.2 report listed six tests for `test_phase56_2.py`, whereas Phase 57 test runner output displayed five passed tests.

An exhaustive audit of [reports/phase56_2_temporal_requirement_and_firmware_readiness_audit.md](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase56_2_temporal_requirement_and_firmware_readiness_audit.md) and [backend/tests/test_phase56_2.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase56_2.py) revealed:
1. In `reports/phase56_2_temporal_requirement_and_firmware_readiness_audit.md` lines 315–319, `test_phase56_2.py` contained **exactly five tests**:
   - `test_phase56_2_gate0_protected_file_invariance`
   - `test_phase56_2_preprocessor_invariance_to_source_rate`
   - `test_phase56_2_training_vs_live_preprocessor_divergence`
   - `test_phase56_2_sequence_gap_conflation_audit`
   - `test_phase56_2_calibration_metric_schema_and_threshold_provenance`
2. The suite that contains **six tests** is [backend/tests/test_phase56_1.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase56_1.py) (lines 309–314 of the Phase 56.2 report).
3. The total test count for Phase 56.2 was 35 items ($5 + 5 + 7 + 7 + 6 + 5 = 35$).
4. Therefore, **there was no missing test in `test_phase56_2.py`**. The runner output displaying 5 passed tests for `test_phase56_2.py` in Phase 57 was completely accurate.

### 5.2 Git Status of Test Files (Tracked vs Untracked)
Inspection of `git status --short backend/tests/` revealed:
- `test_phase16.py` through `test_phase22.py` are tracked and modified (`M`).
- `test_phase23.py` through `test_phase57.py` are untracked (`??`).

**Explanation of Git Working Tree State:**
Since Phase 23, every engineering audit phase has operated under strict change-control rules:
> *"Do not commit, push, reset, or perform destructive cleanup."*

Because commits are prohibited across all engineering audit phases, all test files authored after Phase 22 remain uncommitted in the working tree. This is intentional and consistent with project safety protocols.

### 5.3 Actual Test Runner Output (Python 3.11.9)

```bash
py -3.11 -m pytest backend/tests/test_phase52.py backend/tests/test_phase55.py backend/tests/test_phase55_1.py backend/tests/test_phase56.py backend/tests/test_phase56_1.py backend/tests/test_phase56_2.py backend/tests/test_phase57.py
```

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\saifu\Desktop\4-1 project
plugins: anyio-4.12.1, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 48 items

backend\tests\test_phase52.py .....                                      [ 10%]
backend\tests\test_phase55.py .....                                      [ 20%]
backend\tests\test_phase55_1.py .......                                  [ 35%]
backend\tests\test_phase56.py .......                                    [ 50%]
backend\tests\test_phase56_1.py ......                                   [ 62%]
backend\tests\test_phase56_2.py .....                                    [ 72%]
backend\tests\test_phase57.py .............                              [100%]

============================== warnings summary ===============================
..\..\AppData\Local\Programs\Python\Python311\Lib\site-packages\torch\nn\modules\transformer.py:379
  C:\Users\saifu\AppData\Local\Programs\Python\Python311\Lib\site-packages\torch\nn\modules\transformer.py:379: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 48 passed, 1 warning in 18.92s ========================
```

In addition, legacy regression suites were executed:
- `backend/tests/test_phase37.py`: **6 passed** in 6.42s
- `backend/tests/test_phase21.py`: **17 passed** in 7.45s

Total verified offline tests: **71 passed, 0 failed**.

---

## 6. Task 5 — Integration Readiness Decision

The seven integration dimensions are classified according to the mandatory status schema:

| Integration Dimension | Status | Justification / Evidence |
| :--- | :--- | :--- |
| **1. Historical Preprocessing Parity** | **VERIFIED OFFLINE** | Branch A and Branch B achieve bit-level $0.00000000$ error against both the internal calibrated preprocessor and the authoritative historical training script (`scratch/execute_phase15_adaptation_benchmark.py`). |
| **2. Checkpoint-Specific Configuration** | **VERIFIED OFFLINE** | `LivePipelineService` routes Phase 15 to calibrated preprocessor ($N_w=64, N_o=48, N_{fft}=128, \alpha=2.385$), Phase 13 to legacy defaults ($N_w=32, N_o=24, N_{fft}=64, \alpha=1.0$), and fails closed with `ValueError` on unknown checkpoints. |
| **3. Collector Loss-Metric Correctness** | **VERIFIED OFFLINE** | Ambient MAC filtering is completely decoupled from transport loss. 32-bit wraparound, reboots, duplicates, and out-of-order jitter are handled deterministically. Sequence gaps are accurately labeled as firmware-observed callback gaps. |
| **4. Backward Compatibility** | **VERIFIED OFFLINE** | Default instantiation of `LivePipelineService()` and `RealCSICollector()` preserves all legacy signatures, attributes (`packets_lost`), and behaviors required by Phase 21 and Phase 37 suites. |
| **5. Regression-Test Completeness** | **VERIFIED OFFLINE** | 48/48 phase-specific unit tests (Phases 52–57) and 23/23 legacy regression tests (Phases 21, 37) pass without failures or unhandled exceptions. |
| **6. Protected Artifact Integrity** | **VERIFIED OFFLINE** | MD5 checksums for `models/csiformer_phase13_best.pth`, `models/csiformer_phase15_adapted.pth`, and `data/real_csi_dataset/dataset_manifest.json` are verified 100% bit-for-bit pristine. |
| **7. Physical Acquisition-Rate Readiness** | **BLOCKED — EVIDENCE MISSING** | **Physical acquisition-rate adequacy remains strictly UNVERIFIED.** Offline tests cannot validate wireless channel coherence, active stimulator packet rates, or hardware timing. |

---

## 7. Recommendations for Separately Authorized Hardware Calibration (Phase 58)

The software architecture (preprocessing parity, routing, collector telemetry) is in a verified and stable offline state. However, physical calibration requires physical hardware interaction:

1. **Gate Decision:** **GO FOR OFFLINE INTEGRATION; HOLD FOR PHYSICAL HARDWARE EXECUTION.**
2. **Prerequisites for Physical Calibration:**
   - Physical hardware calibration must be separately authorized.
   - Initial physical baseline must test passive ambient capture on COM5 to confirm the $\approx 1.66\text{--}3.8\text{ Hz}$ passive baseline.
   - Active UDP stimulation must proceed stage-by-stage ($0, 5, 15, 30, 35\text{ pkts/s}$) with automated safety aborts if host inter-arrival interval $\Delta t_{host} > 100\text{ ms}$ or loss $> 15\%$.
3. **No Inference Overclaim:** Live model inference accuracy must not be claimed or inferred merely from preprocessing parity. True classification accuracy can only be assessed on physical CSI data once acquisition rate and temporal continuity are physically validated.
