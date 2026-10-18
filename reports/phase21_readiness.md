# CSIFormer Phase 21.1 — Master Readiness Gate Report

## Executive Summary

**CSIFormer Phase 21.1** completes the empirical diagnosis and live stream verification of the ESP32-S3 hardware acquisition pipeline on `COM5`.

Key achievements:
- **Zero-Packet Root Cause Proven & Solved:** Resolved the pySerial DTR control pin trap and the 10.6-second boot/Wi-Fi latency mismatch.
- **Physical CSI Streaming Established:** Received and parsed **157 live CSI frames** at **$40.4\text{ Hz}$** with **$-56.0\text{ dBm}$ mean RSSI** under active Wi-Fi stimulation (`Tp link`, Channel 7).
- **Physical Dimensions Decoded:** Formally verified that the firmware transmits **5 raw complex subcarriers** ($10\text{ signed integers}$) per frame to prevent UART buffer overrun at 115200 baud.
- **Full Parser Hardening:** Upgraded the dual parser with regex-based extraction, passing all 81 regression tests with zero failures.
- **Strict Integrity Safeguards:** Preserved model checkpoints bit-for-bit, verified the 23-session historical dataset, and designated the end-to-end recording trial as **`PENDING OPERATOR RECORDING`** without data fabrication.

---

## 1. Summary of Code & Implementation Changes

| Component | File Path | Modification Summary |
| :--- | :--- | :--- |
| **Serial Collector** | [`backend/app/services/real_csi_collector.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) | • Upgraded `parse_raw_telemetry_line` with regex extraction to robustly parse Format A (5-subcarrier physical stream and 64-subcarrier historical stream) and Format B (CSV and bracketed semicolons).<br>• Enhanced control pin handling (`dtr=False, rts=False`) and flash boot pulse (`trigger_normal_reset`).<br>• Integrated 6-state diagnostic state machine and comprehensive health telemetry counters. |
| **Workflow Manager** | [`backend/app/services/collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) | • Configurable verification duration (default $12.0\text{s}$, tested $15.0\text{s}$).<br>• Added stream stabilization loop in `start_session` that waits up to 15s for the first physical CSI packet before initiating recording. |
| **Operator CLI** | [`scratch/run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py) | • Added `--duration` flag support for `--verify` mode.<br>• Comprehensive diagnostic summary display. |
| **Regression Tests** | [`backend/tests/test_phase21.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase21.py) | • Extended test suite to 17 tests covering 5-subcarrier physical parsing, bracketed semicolons, whitespace tolerance, timeouts, state transitions, and checkpoint invariance. |
| **Reports** | [`reports/phase21_*.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/) | • Updated Hardware Diagnostics, Live Stream Validation, and Readiness reports. |

---

## 2. Checkpoint Cryptographic Hash Invariance

Both model checkpoints were verified bit-for-bit identical before and after all changes:

| Model Checkpoint | Expected MD5 | Actual Before MD5 | Actual After MD5 | Verification Status |
| :--- | :--- | :--- | :--- | :---: |
| **Production:** [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH** |
| **Experimental:** [`models/csiformer_phase15_adapted.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase15_adapted.pth) | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH** |

---

## 3. Verified Physical Dataset Baseline & Inventory

No physical sessions were fabricated or artificially added during this phase.

### Target vs. Current Dataset Totals:
| Metric | Baseline Count | Newly Added | Current Verified Total | Pilot Target | Remaining Deficit | Audit Reference |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Physical Sessions** | 23 | 0 | **23** | $\ge 50$ | **-27 sessions** | [`dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json) |
| **Physical Packets** | 3,212 | 0 | **3,212** | $\ge 10,000$ | **-6,788 packets** | Sum of 23 physical JSON session files |
| **Valid Windows ($T=50$)** | 49 | 0 | **49** | $\ge 150$ | **-101 windows** | Discrete non-overlapping 50-frame windows |
| **Distinct Participants** | 2 | 0 | **2** | $\ge 5$ | **-3 participants** | `Participant_01`, `Participant_02` |
| **Distinct Rooms** | 1 | 0 | **1** | $\ge 3$ | **-2 rooms** | `Laboratory_Room1` exclusively |
| **Tx-Rx Distances** | 1 | 0 | **1** | $\ge 3$ | **-2 distances** | $2.5\text{ m}$ baseline exclusively |
| **Held-Out Test Fall Windows** | 4 | 0 | **4** | $\ge 35$ | **-31 windows** | [`dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json) |
| **Held-Out Test Fall Events** | 2 | 0 | **2** | $\ge 12$ | **-10 events** | Distinct physical fall sessions in test split |

*(Note: Exactly 24 physical JSON session files exist in [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/); 23 are indexed in the primary manifest, and 1 unindexed aborted trial [`phase14_p15_real_walk_t1_1792303844_1792303844.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/phase14_p15_real_walk_t1_1792303844_1792303844.json) with 147 frames remains preserved on disk unindexed.)*

---

## 4. Full Automated Regression Test Results

The complete test suite across all phases was executed:

```powershell
py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py -v
```

### Result:
- **Total Tests:** **81 passed, 0 failed** in 11.74s
  - `test_phase14.py`: 10 passed
  - `test_phase16.py`: 10 passed
  - `test_phase17.py`: 12 passed
  - `test_phase18.py`: 12 passed
  - `test_phase19.py`: 10 passed
  - `test_phase20.py`: 10 passed
  - `test_phase21.py`: **17 passed**
- **Warnings:** 4 standard PyTorch/Starlette deprecation warnings (identical to baseline).

---

## 5. Master Gate Verdicts

### Verdict A: Software Readiness — **GO**
- **Rationale:** Dual parser upgraded with regex extraction; Format A (5-subcarrier physical stream and 64-subcarrier historical format) and Format B fully supported; 6-state diagnostic machine operational; 81/81 regression tests passing.

### Verdict B: Hardware Stream Readiness — **GO**
- **Rationale:** Live serial communication verified on `COM5`; zero-packet root cause resolved; 157 genuine physical CSI frames captured at $40.4\text{ Hz}$ with $-56.0\text{ dBm}$ RSSI under active Wi-Fi stimulation (`CSI_STREAM_ACTIVE`).

### Verdict C: End-to-End Physical Recording Acceptance Test — **PENDING OPERATOR RECORDING**
- **Rationale:** Live streaming is confirmed. Per operator consultation, actual session recording is held pending human participant trial execution.

### Verdict D: Phase 22 Model Evaluation Gate — **NO-GO**
- **Rationale:** Evaluation remains strictly blocked by sample-size and diversity deficits ($N=2$ participants vs. $\ge 5$; 23 sessions vs. $\ge 50$; 4 test fall windows vs. $\ge 35$; 2 test fall events vs. $\ge 12$). Model evaluation must not occur until the real-world dataset expansion campaign fulfills these criteria.

*Disclaimer: CSIFormer is an academic prototype and has not been clinically certified or validated as a safety-critical fall-detection system.*
