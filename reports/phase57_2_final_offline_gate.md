# Phase 57.2 Report: Final Offline Gate and Loss-Metric Semantics

## Executive Summary

Phase 57.2 concludes the three-phase audit and corrective engineering sequence (Phases 57, 57.1, 57.2) dedicated to resolving preprocessing divergence, checkpoint routing fragility, and packet-loss accounting conflation before physical calibration.

This final gate resolves the loss-metric semantics in [RealCSICollector](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py). Observing missing numbers in the ESP32 firmware callback sequence counter (`packet_sequence`) proves that callback invocations occurred on the microcontroller that did not yield admitted frames on the host. However, attributing those gaps strictly to "confirmed transport loss" without physical bus telemetry is technically unverified: gaps can equally arise from firmware internal queue evictions, UART transmitter overflows, framing errors, USB bridge drops, serial parser rejections, or host OS serial buffer exhaustion.

In this phase:
1. **Semantics Decoupled and Formalized:** The primary metric is formalized as `firmware_sequence_gaps` (representing unobserved physical callback arrivals), while `confirmed_transport_loss` and `packets_lost` are maintained as backward-compatible aliases.
2. **Comprehensive Loss-Semantics Verification:** Added Test 13 (`test_phase57_loss_metric_semantics_and_parser_error_correlation`) in [backend/tests/test_phase57.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py), proving the exact interaction between parser errors, ambient MAC filtering, duplicate sequence discard, out-of-order jitter, 32-bit wraparound, and firmware reboots.
3. **Historical Preprocessing Parity Re-verified:** Both Branch A (temporal z-score) and Branch B (calibrated STFT with $2.385\times$ Doppler stretching) demonstrate bit-level exact parity ($0.00000000$ error) directly against the historical training script ([scratch/execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py)).
4. **Fail-Closed Checkpoint Routing:** [LivePipelineService](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) fails closed on unsupported checkpoint IDs with `ValueError` and ensures atomic error handling on missing files with `FileNotFoundError`.
5. **Full Regression Execution:** All 72 tests across all phase-specific suites (Phases 52, 55, 55.1, 56, 56.1, 56.2, 57) and legacy suites (Phases 37, 21) pass with a 100% pass rate.
6. **Integrity Maintained:** All three protected asset hashes are 100% bit-for-bit pristine.
7. **Operational Boundary:** Physical acquisition-rate adequacy remains **UNVERIFIED**. Hardware calibration remains on **HOLD** pending separate explicit authorization for Phase 58.

---

## 1. Gate 0 — Cryptographic Hash Ledger and State Preservation

Before and after all operations, the three protected repository assets were cryptographically verified using MD5 checksums.

### 1.1 Protected Hash Ledger

| Protected File Path | Expected Reference MD5 | Measured MD5 Checksum | Verification Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **PASS (BIT-FOR-BIT MATCH)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **PASS (BIT-FOR-BIT MATCH)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **PASS (BIT-FOR-BIT MATCH)** |

### 1.2 Strict Constraints Adherence
- **Serial Communication:** Port COM5 was never opened, polled, or configured.
- **Network Traffic:** No UDP datagrams or active stimulation packets were transmitted.
- **Firmware Compilation / Flashing:** Zero PlatformIO builds, zero flash commands executed.
- **Git State:** No commits, pushes, resets, or destructive cleanups were executed. All working-tree changes and untracked files are preserved intact.

---

## 2. Task 1 — Audit of Loss Terminology and Counter Semantics

### 2.1 The Multi-Layer Observation Model

A rigorous audit of [firmware/esp32s3_csi_collector/main/main.c](file:///C:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c) and [backend/app/services/real_csi_collector.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) defines precisely what each layer's counter measures and proves:

| Telemetry Quantity | Signal Layer | Underlying Mechanism | What the Metric Proves | What the Metric DOES NOT Prove |
| :--- | :--- | :--- | :--- | :--- |
| `packet_sequence` (`seq`) | ESP32 Firmware Callback | 32-bit unsigned integer incremented on **every** physical Wi-Fi frame received on Channel 7. | Monotonic arrival of frames at the radio physical layer before filtering. | Does not indicate whether a frame was target BSSID or ambient noise. |
| `rx_seq` | 802.11 MAC Layer | 12-bit modulo-4096 sequence control field from the 802.11 MAC header. | Sequence of frames transmitted by that specific MAC address. | Gaps do not prove transport loss if the transmitter sent unmonitored frames. |
| `parse_errors` | Host Serial Demux | Counter of serial lines that failed regex/CSV parsing. | Host received malformed, truncated, or corrupted ASCII lines. | Does not prove whether corruption occurred in UART cable, USB bridge, or host buffer. |
| `filtered_non_target_packets` | Host Application | Counter of valid frames whose source MAC did not match `target_mac`. | Intentional software rejection of ambient probe requests, beacons, etc. | **Proves frames were delivered intact over serial, not lost.** |
| `firmware_sequence_gaps` | Host Application | Gaps in `packet_sequence` between consecutive parsed records ($f_{\text{gap}} = \text{seq} - (\text{last} + 1)$). | **Proves that one or more callback events occurred on ESP32 that were not parsed on the host.** | **Does NOT prove that loss occurred specifically in the UART transport.** |
| `target_sequence_gaps` | Host Application | Gaps between admitted target-filtered frames. | Number of non-target or missing frames between target arrivals. | Does not distinguish between filtered ambient frames and physical drops. |
| `out_of_order_packets` | Host Application | Counter of frames arriving with $\text{seq} < \text{last}$ where $\text{last} - \text{seq} \le 1000$ and $\text{last} < 100$. | Delivery jitter / thread preemption where a packet arrived slightly reordered. | Does not represent a hardware reboot. |
| `counter_resets` | Host Application | Counter of frames where sequence dropped drastically ($(\text{last} - \text{seq}) > 1000$ or $\text{last} \ge 100 \land \text{seq} \le 10$). | Firmware reboot or MCU power cycle resetting counter to zero. | Does not represent a single dropped frame. |
| `duplicate_packets` | Host Application | Counter of frames arriving with $\text{seq} == \text{last}$. | Duplicate serial transmission or repeated line delivery. | Discarded; not counted as fresh physical observation. |

### 2.2 Redefinition of Transport Loss Terminology
In Phase 57's initial implementation, sequence gaps were termed `confirmed_transport_loss`. 

As documented in [backend/app/services/real_csi_collector.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L110-L125), claiming a specific transport-layer cause without a physical hardware bus monitor or logic analyzer is an overclaim. When a serial line is corrupted on the wire and fails parsing (`parse_errors`), the subsequent valid line observes a jump in `packet_sequence`. That gap was triggered by host parser rejection of a corrupted line, not because bytes vanished from the serial bus.

Therefore:
- **Primary Metric:** `self.firmware_sequence_gaps` measures total unobserved callback frames.
- **Backward-Compatible Aliases:** `self.confirmed_transport_loss` and `self.packets_lost` are maintained and set equal to `self.firmware_sequence_gaps`.
- **Stream Health Schema:** Exposes `firmware_sequence_gaps`, `target_sequence_gaps`, `filtered_non_target_packets`, `parse_errors`, `duplicate_packets`, `out_of_order_packets`, and `counter_resets` independently.

### 2.3 Synthetic Test Evidence ([backend/tests/test_phase57.py::test_phase57_loss_metric_semantics_and_parser_error_correlation](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py#L501-L570))
A multi-stage synthetic test was authored to verify this model:
1. Target record seq 100 admitted (`packets_received = 1`).
2. Duplicate record seq 100 discarded (`duplicate_packets = 1, packets_received = 1`).
3. Malformed line seq 101 rejected by parser (`parse_errors = 1`).
4. Ambient record seq 102 filtered by MAC (`filtered_non_target_packets = 1`, `firmware_sequence_gaps = 1`).
5. Out-of-order target record seq 101 admitted (`out_of_order_packets = 1, packets_received = 2`).
6. Target record seq 103 admitted (`packets_received = 3, target_sequence_gaps = 1`).

This test proves that `firmware_sequence_gaps` accurately reflects missing callback numbers without corrupting target admittance or inflating loss from ambient filtering.

---

## 3. Task 2 — Review of Final Code Changes

### 3.1 Diffs and Architectural Rationale

#### 1. [backend/app/services/physics_csi_preprocessor.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py)
- **Change:** Updated `CalibratedPhysicsPreprocessor.__init__` to accept optional `stft_window`, `stft_noverlap`, `stft_nfft`, and `doppler_scale`.
- **Rationale:** Enables parameterized instantiation while preserving default parameters ($N_w=64, N_o=48, N_{fft}=128, \alpha=2.3853$) matching the Phase 15 training benchmark.

#### 2. [backend/app/services/live_pipeline_service.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py)
- **Change:** Added `configure_preprocessor_for_checkpoint(checkpoint_id)` and `load_checkpoint(checkpoint_path, checkpoint_id)`. Added `preprocess_window(raw_win)`.
- **Rationale:** 
  - Resolves the $3.0318$ tensor error when running inference on Phase 15.
  - Fails closed with `ValueError` on unrecognized checkpoint IDs instead of silently defaulting.
  - Ensures atomic failure on missing checkpoint files without leaving corrupted state.
  - Preserves default Phase 13 preprocessor on bare initialization, maintaining 100% backward compatibility with [backend/tests/test_phase37.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase37.py).

#### 3. [backend/app/services/real_csi_collector.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py)
- **Change:**
  - Evaluates `last_firmware_seq` across all physical arrivals before MAC filtering.
  - Isolates filtered ambient packets into `filtered_non_target_packets` without incrementing `packets_lost`.
  - Discards duplicate sequence records (`duplicate_packets`).
  - Distinguishes out-of-order jitter (`out_of_order_packets`) from genuine reboots (`counter_resets`).
  - Seamlessly handles 32-bit unsigned wraparound ($2^{32}-1 \to 0$).
  - Maps `packets_lost` and `confirmed_transport_loss` to `firmware_sequence_gaps` with documented semantics.

#### 4. [backend/tests/test_phase57.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase57.py)
- **Change:** Authored 14 deterministic offline tests covering:
  - Gate 0 MD5 verification.
  - Preprocessing parity against fixed-seed random complex CSI, constant static signals, and known sinusoids.
  - Direct independent cross-script parity against [scratch/execute_phase15_adaptation_benchmark.py](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py).
  - Fail-closed checkpoint routing and atomic error handling.
  - Ambient filtering decoupling, transport loss detection, 32-bit wraparound, reboots, duplicates, out-of-order jitter, and tri-counter distinction.

---

## 4. Task 3 — Comprehensive Test Suite Execution

All 72 tests across all phase test files and legacy regression suites were executed in Python 3.11.9:

```bash
py -3.11 -m pytest backend/tests/test_phase52.py backend/tests/test_phase55.py backend/tests/test_phase55_1.py backend/tests/test_phase56.py backend/tests/test_phase56_1.py backend/tests/test_phase56_2.py backend/tests/test_phase57.py backend/tests/test_phase37.py backend/tests/test_phase21.py
```

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\saifu\Desktop\4-1 project
plugins: anyio-4.12.1, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 72 items

backend\tests\test_phase52.py .....                                      [  6%]
backend\tests\test_phase55.py .....                                      [ 13%]
backend\tests\test_phase55_1.py .......                                  [ 23%]
backend\tests\test_phase56.py .......                                    [ 33%]
backend\tests\test_phase56_1.py ......                                   [ 41%]
backend\tests\test_phase56_2.py .....                                    [ 48%]
backend\tests\test_phase57.py ..............                             [ 68%]
backend\tests\test_phase37.py ......                                     [ 76%]
backend\tests\test_phase21.py .................                          [100%]

============================== warnings summary ===============================
..\..\AppData\Local\Programs\Python\Python311\Lib\site-packages\torch\nn\modules\transformer.py:379
  C:\Users\saifu\AppData\Local\Programs\Python\Python311\Lib\site-packages\torch\nn\modules\transformer.py:379: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 72 passed, 1 warning in 24.29s ========================
```

### 4.1 Reconciled Test Inventory

| Test Suite File | Test Count | Pass Count | Fail Count | Focus Area |
| :--- | :--- | :--- | :--- | :--- |
| `backend/tests/test_phase52.py` | 5 | 5 | 0 | Source MAC filtering, fail-closed metadata, HT20 subcarrier masking. |
| `backend/tests/test_phase55.py` | 5 | 5 | 0 | Passive rate gate, temporal dilation, sequence reconciliation. |
| `backend/tests/test_phase55_1.py`| 7 | 7 | 0 | Record count vs rate separation, window span, STFT scaling. |
| `backend/tests/test_phase56.py` | 7 | 7 | 0 | Historical rate audit, Format B v2 parser, safety abort simulation. |
| `backend/tests/test_phase56_1.py`| 6 | 6 | 0 | Buffer lockstep alignment, parser mutual exclusivity, telemetry robustness. |
| `backend/tests/test_phase56_2.py`| 5 | 5 | 0 | Temporal rate invariance, preprocessor divergence audit, sequence conflation. |
| `backend/tests/test_phase57.py` | 14 | 14 | 0 | Bit parity, independent script parity, fail-closed routing, decoupled loss semantics. |
| `backend/tests/test_phase37.py` | 6 | 6 | 0 | Production LivePipelineService backward compatibility. |
| `backend/tests/test_phase21.py` | 17 | 17 | 0 | Diagnostic state machine, serial reconnect, stream health contract. |
| **Total** | **72** | **72** | **0** | **100% Pass Rate Across All Suites** |

---

## 5. Task 4 — Project Integrity and Git State

### 5.1 Verification of Protected Artifacts
Checksums verified immediately following all test executions:
- `models/csiformer_phase13_best.pth`: `383b4d98c08f8970b0443738f170ec01` (**MATCH**)
- `models/csiformer_phase15_adapted.pth`: `ab3d97a04d78edf75d807178772bc828` (**MATCH**)
- `data/real_csi_dataset/dataset_manifest.json`: `a58e1280fb2c0a6649335a9a381d00c6` (**MATCH**)

### 5.2 Git Working Tree Inspection
`git status --short` confirms:
- Tracked modified files: `backend/app/services/live_pipeline_service.py`, `backend/app/services/physics_csi_preprocessor.py`, `backend/app/services/real_csi_collector.py`, `backend/tests/test_phase16.py`–`test_phase22.py`.
- Untracked files: `backend/tests/test_phase23.py`–`test_phase57.py` and reports from Phase 23 through Phase 57.2.
- In accordance with audit change-control rules, zero commits or pushes were performed.

---

## 6. Offline Gate Decision and Recommendations

### 6.1 Status Matrix

| Gate Dimension | Status | Audit Finding |
| :--- | :--- | :--- |
| **Historical Preprocessing Parity** | **VERIFIED OFFLINE** | $0.00000000$ error confirmed against historical benchmark script. |
| **Checkpoint Routing Integrity** | **VERIFIED OFFLINE** | Fail-closed routing and atomic checkpoint loading verified. |
| **Loss Metric Accounting Semantics** | **VERIFIED OFFLINE** | Sequence gaps decoupled from MAC filtering and precisely modeled. |
| **Regression Suite Pass Rate** | **VERIFIED OFFLINE** | 72/72 tests pass (100%). |
| **Protected Artifact Invariance** | **VERIFIED OFFLINE** | MD5 checksums 100% bit-for-bit pristine. |
| **Physical Acquisition Rate Adequacy** | **UNVERIFIED (BLOCKED)** | **Passive acquisition rate ($\approx 1.66\text{--}3.8\text{ Hz}$) cannot be physically accelerated offline.** |

---

### 6.2 Formal Gate Recommendation for Phase 58

> [!IMPORTANT]
> **GATE VERDICT: GO FOR OFFLINE INTEGRATION; HOLD FOR PHYSICAL HARDWARE EXECUTION.**
> 
> The software signal processing chain, checkpoint routing logic, and serial loss accounting are fully verified, mathematically aligned, and regression-free.
> 
> However, physical acquisition-rate adequacy and wireless temporal coherence **cannot be established offline**. Phase 58 (physical acquisition calibration) must only proceed under **separate, explicit authorization** with physical hardware access to COM5 and controlled stimulator hardware.
> 
> **Do not execute Phase 58 in this turn.**
