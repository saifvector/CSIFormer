# Phase 58.4: Offline Recorder Audit and Readiness Review Report

**Execution Date:** 2026-10-21  
**Operating Mode:** Strictly offline independent audit. Zero COM5 access, zero hardware communication, zero network traffic, zero firmware flashing, zero model operations.  
**Audited Artifacts:**
- Implementation: [`scratch/run_phase58_stage1_repro_evidence.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_phase58_stage1_repro_evidence.py)
- Test Suite: [`backend/tests/test_phase58_evidence_recorder.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase58_evidence_recorder.py)
- Phase 58.3 Report: [`reports/phase58_3_offline_evidence_recorder_report.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase58_3_offline_evidence_recorder_report.md)  
**Final Verdict:** **GO FOR FUTURE PASSIVE HARDWARE CAPTURE (STRICTLY ON HOLD PENDING SEPARATE EXPLICIT AUTHORIZATION)**

---

## 1. Executive Summary

This audit independently reviews the implementation, error-handling semantics, persistence architecture, and invocation safety of the passive evidence recorder developed in Phase 58.3.

The audit confirms:
1. **Parser Correctness & Line Classification:** The parser reliably parses Format B v1 `CSI_DATA` frames, correctly extracts MAC, RSSI, noise floor, sequence numbers, and subcarriers, and accurately separates target router frames from ambient transmitters without accepting malformed strings or crashing on split tokens.
2. **Evidence Integrity & Durability:** The JSONL streaming architecture records sub-microsecond monotonic timestamps (`time.perf_counter()`), assigns sequential 1-based line indexes, flushes buffers incrementally, and atomically generates companion session manifests with cryptographic MD5 verification.
3. **Canonical Dataset Isolation:** Active runtime path checks prevent writing evidence into `data/real_csi_dataset/`, preserving training dataset integrity bit-for-bit.
4. **Invocation Safety:** Running the script directly (`__main__`) displays safety notices and exits without touching hardware. Offline unit tests run entirely against in-memory synthetic fixtures.
5. **Regression Verification:** 14 focused evidence recorder tests and 22 existing core regression tests (`test_phase16.py`, `test_phase17.py`) passed with 100% success. Protected asset hashes remain completely unchanged.

---

## 2. Findings Ranked by Severity

| Finding ID | Severity | Category | Description | Status / Resolution |
|---|---|---|---|---|
| **F-01** | **Informational** | Baud Rate Alignment | `run_hardware_capture()` defaults to 115200 baud matching the deployed Phase 50 recovery firmware on `COM5`, whereas `main.c` source code has `#define SERIAL_BAUD 921600`. | **Documented & Expected.** 115200 baud matches the physical device state confirmed in Phase 58 Stage 1. |
| **F-02** | **Low** | Buffer Boundary Truncation | When a capture times out exactly at the duration boundary, an incomplete trailing line fragment may remain in the serial read buffer. | **Handled.** Any incomplete candidate prefix is classified as `PARSER_ERROR` with reason `"invalid_token_format_or_subcarrier_split"`, exactly matching Stage 1 behavior. |
| **F-03** | **Informational** | Durability Boundary | `flush()` flushes Python runtime buffers to OS page cache; physical media persistence requires `os.fsync()`. | **Handled & Documented.** `os.fsync()` is explicitly executed upon session finalization and when `sync_to_disk=True`. |

Zero Critical (Severity 1) or Moderate (Severity 2) defects were identified.

---

## 3. Parser Correctness & Telemetry Verification

### 3.1 Field Boundary and Extraction Rigor
The recorder delegates telemetry line extraction to `RealCSICollector.parse_raw_telemetry_line()`:
- **Format Header:** Detects `CSI_DATA` prefix without requiring `CSI_DATA_V2` or non-existent hardware timestamp headers.
- **Header Token Count:** Enforces `len(tokens) >= 6` (`prefix`, `mac`, `rssi`, `noise`, `seq`, `num_sc`). If fewer than 6 tokens are present, returns `None` $\rightarrow$ classified as `PARSER_ERROR`.
- **Numerical Type Safety:** Enforces integer conversion for `sequence`, float for `rssi` and `noise`. Any conversion failure inside `parse_raw_telemetry_line` is trapped by `try...except Exception` returning `None` $\rightarrow$ `PARSER_ERROR`.
- **Subcarrier Decoding:** Splits remainder string by comma/semicolon, extracts amplitude and phase pairs delimited by `:`. If subcarrier count is 0, returns `None` $\rightarrow$ `PARSER_ERROR`.
- **MAC Normalization:** Converts MAC to uppercase string (`.upper()`), preventing case-mismatch filtering errors.

### 3.2 Parser Misclassification Check

| Serial Line Type | Example String | Assigned `parse_status` | Assigned `rejection_reason` | Misclassification Risk |
|---|---|---|---|---|
| **Target CSI Frame** | `CSI_DATA,98:BA:5F:EF:28:26,-55,-93,6129,64,...` | `VALID_TARGET` | `null` | Zero |
| **Ambient Wi-Fi Frame** | `CSI_DATA,00:2D:F4:5B:4B:7D,-61,-93,6130,64,...` | `FILTERED_NON_TARGET` | `non_target_mac:00:2D:F4:5B:4B:7D` | Zero |
| **Truncated CSI Line** | `CSI_DATA,98:BA:5F:EF:28:26,-55` | `PARSER_ERROR` | `invalid_token_format...` | Zero |
| **Corrupt CSI Subcarrier** | `CSI_DATA,98:BA:5F:EF:28:26,-55,-93,6129,64,garbage` | `PARSER_ERROR` | `invalid_token_format...` | Zero |
| **ESP-IDF Boot Message** | `I (812) ESP32S3_CSI_COLLECTOR: Wi-Fi CSI Collection...` | `NON_CSI_LINE` | `non_candidate_prefix` | Zero |
| **Reset / Bootloader Log** | `rst:0x1 (POWERON_RESET),boot:0x8...` | `NON_CSI_LINE` | `non_candidate_prefix` | Zero |
| **Empty / Whitespace Line**| `\r\n` or `   ` | `NON_CSI_LINE` | `empty_line` | Zero |

---

## 4. Evidence Integrity & Durability Audit

### 4.1 Monotonic Timing and Inter-Arrival Precision
- **Monotonic Clock:** Each record captures `time.perf_counter()`, guaranteed to be monotonically non-decreasing on Windows and immune to system clock adjustments or daylight saving shifts.
- **Inter-Arrival Calculation:** $\Delta t_{\text{host}} = t_i - t_{i-1}$ is computed on high-resolution monotonic timestamps.
- **Zero-Duration Protection:** Verified by test `test_single_line_zero_duration_rate_safety` that rate calculations guard against zero division if $\Delta t = 0$.

### 4.2 Exact Count Reconciliation Formula
The mathematical reconciliation invariant was verified under test `test_sequential_line_indexes_and_count_reconciliation`:

$$\text{total\_lines\_read} \equiv \text{valid\_target\_records} + \text{filtered\_non\_target\_records} + \text{parser\_errors} + \text{non\_csi\_lines}$$
$$\text{candidate\_records} \equiv \text{valid\_records\_parsed} + \text{parser\_errors}$$
$$\text{valid\_records\_parsed} \equiv \text{valid\_target\_records} + \text{filtered\_non\_target\_records}$$

### 4.3 Atomic File Replacement & Cryptographic Hash
- The session manifest is written to `{session_id}_manifest.json.tmp`.
- After calling `f.flush()` and `os.fsync(f.fileno())`, it is atomically moved into place via `os.replace()`, guaranteeing that corrupt partial manifests can never exist on disk.
- The manifest records `evidence_file_md5`, which is verified against the actual bytes of `{session_id}_records.jsonl`.

### 4.4 Canonical Dataset Isolation
- The constructor explicitly checks:
  ```python
  canonical_dataset_dir = (PROJECT_ROOT / "data" / "real_csi_dataset").resolve()
  if canonical_dataset_dir in self.output_dir.resolve().parents or self.output_dir.resolve() == canonical_dataset_dir:
      raise ValueError("Safety Violation: Evidence recorder must NOT write to canonical dataset directory")
  ```
- Validated by unit test `test_dataset_directory_protection`.

---

## 5. Invocation Safety Review

1. **CLI Execution Safety:**
   - Direct execution of `py scratch/run_phase58_stage1_repro_evidence.py` prints informational instructions and explicitly notes that hardware capture is on HOLD.
   - It does **not** call `run_hardware_capture()`, open serial ports, or start background threads.
2. **Opt-In Hardware Execution (`run_hardware_capture`):**
   - Must be explicitly imported and called with defined arguments.
   - Sets `dtr=False, rts=False` before `ser.open()`, preventing device auto-reset into ROM bootloader.
   - Contains a hard wall-clock timeout (`while time.perf_counter() < end_perf:`).
   - Wrapped in a `try...finally` block ensuring `ser.close()` is guaranteed to execute even if an unexpected exception occurs.

---

## 6. Verification & Test Execution Evidence

### 6.1 Focused Evidence Recorder Test Suite
Command:
```powershell
py -3.11 -m pytest backend/tests/test_phase58_evidence_recorder.py -v
```
Output:
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\saifu\Desktop\4-1 project
collected 14 items

backend/tests/test_phase58_evidence_recorder.py::test_valid_target_record PASSED [  7%]
backend/tests/test_phase58_evidence_recorder.py::test_valid_non_target_record PASSED [ 14%]
backend/tests/test_phase58_evidence_recorder.py::test_malformed_csi_records PASSED [ 21%]
backend/tests/test_phase58_evidence_recorder.py::test_non_csi_boot_log_lines PASSED [ 28%]
backend/tests/test_phase58_evidence_recorder.py::test_unicode_and_decoding_error_handling PASSED [ 35%]
backend/tests/test_phase58_evidence_recorder.py::test_jsonl_roundtrip_validity PASSED [ 42%]
backend/tests/test_phase58_evidence_recorder.py::test_sequential_line_indexes_and_count_reconciliation PASSED [ 50%]
backend/tests/test_phase58_evidence_recorder.py::test_interrupted_capture_and_clean_shutdown PASSED [ 57%]
backend/tests/test_phase58_evidence_recorder.py::test_existing_collector_api_compatibility PASSED [ 64%]
backend/tests/test_phase58_evidence_recorder.py::test_dataset_directory_protection PASSED [ 71%]
backend/tests/test_phase58_evidence_recorder.py::test_file_overwrite_protection PASSED [ 78%]
backend/tests/test_phase58_evidence_recorder.py::test_valid_target_line_with_crlf_trailing PASSED [ 85%]
backend/tests/test_phase58_evidence_recorder.py::test_sequence_gap_accounting_with_non_target_interleaving PASSED [ 92%]
backend/tests/test_phase58_evidence_recorder.py::test_single_line_zero_duration_rate_safety PASSED [100%]

============================= 14 passed in 3.50s ==============================
```

### 6.2 Regression Test Suites
- **`backend/tests/test_phase16.py`:** 10 passed in 15.11s.
- **`backend/tests/test_phase17.py`:** 12 passed in 3.65s.

### 6.3 Cryptographic Hash Audit of Protected Assets

| Protected Asset | Canonical MD5 Hash | Verified Audited MD5 | Status |
|---|---|---|---|
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH** |

---

## 7. Audit Recommendation & Readiness Verdict

### Verdict:
**GO FOR FUTURE PASSIVE HARDWARE CAPTURE (STAGE 1 REPRODUCIBILITY)**

### Operational Conditions:
1. **Explicit Authorization Required:** Hardware capture must not run automatically. It requires explicit user authorization confirming:
   - Target port: `COM5` at `115200` baud.
   - Target BSSID: `98:BA:5F:EF:28:26` (Channel 7).
   - Duration: Exactly 30.0 seconds.
   - Mode: Strictly passive, read-only (`dtr=False, rts=False`).
   - Destination: `reports/evidence/`.
2. **Current State:** The hardware interface on `COM5` remains closed and released. All hardware operations remain on **HOLD**.
