# CSIFormer Phase 24.1 — Final Sampling-Rate and Dataset Consistency Audit Report

**Audit Date:** October 19, 2026  
**Environment:** Windows (x86_64), Python 3.11.9  
**Repository Root:** `C:\Users\saifu\Desktop\4-1 project`  
**Dataset Path:** `data/real_csi_dataset/`  
**Manifest Path:** `data/real_csi_dataset/dataset_manifest.json`  
**Audit Scope:** Independent mathematical, programmatic, file-level, and test verification of Phase 24 physical CSI recordings and dataset integrity.

---

## 1. Independent Audit of Phase 24 Physical CSI Recordings

Each of the five newly collected Phase 24 session recordings for `Participant_03` was independently parsed and audited from its raw JSON artifact. All metrics were recomputed directly from the underlying frame arrays without relying on precomputed metadata fields.

### 1.1 Session-by-Session Audit Table

| Session Identifier | Activity | Frame Count \(N\) | First Timestamp (\(t_0\)) | Last Timestamp (\(t_{N-1}\)) | Timestamp Span \(\Delta t\) | \((N-1)/\Delta t\) | \(1/\overline{\Delta t}\) | Stored `mean_sampling_rate_hz` | Stored `duration_seconds` | Wall Rate \(N/T_{\mathrm{wall}}\) | Seq Gaps | Dup TS | Non-Monotonic |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `phase16_real_static_Participant_03_1792388605_1792388605` | `static` | 141 | 1792388605.5487366 | 1792388609.5202889 | 3.971552 s | 35.2507 Hz | 35.2507 Hz | 35.25 Hz | 4.02 s | 35.0746 Hz | 0 | 0 | 0 |
| `phase16_real_sit_Participant_03_1792388631_1792388631` | `sit` | 152 | 1792388631.4369202 | 1792388635.4068372 | 3.969917 s | 38.0361 Hz | 38.0361 Hz | 38.04 Hz | 4.02 s | 37.8109 Hz | 0 | 0 | 0 |
| `phase16_real_walk_Participant_03_1792388657_1792388657` | `walk` | 139 | 1792388657.9383216 | 1792388661.9107916 | 3.972470 s | 34.7391 Hz | 34.7391 Hz | 34.74 Hz | 4.02 s | 34.5771 Hz | 0 | 0 | 0 |
| `phase16_real_clap_Participant_03_1792388686_1792388686` | `clap` | 145 | 1792388686.4152682 | 1792388690.3875222 | 3.972254 s | 36.2515 Hz | 36.2515 Hz | 36.25 Hz | 4.02 s | 36.0697 Hz | 0 | 0 | 0 |
| `phase16_real_push_pull_Participant_03_1792388712_1792388712` | `push_pull` | 141 | 1792388712.7844169 | 1792388716.7868321 | 4.002415 s | 34.9789 Hz | 34.9789 Hz | 34.98 Hz | 4.04 s | 34.9010 Hz | 0 | 0 | 0 |

### 1.2 Rate Agreement and Mathematical Integrity
- **Empirical Sampling Rate Consistency:** For all five sessions, \((N-1)/\Delta t\) equals \(1/\overline{\Delta t}\) down to machine precision.
- **Stored Rate Precision:** The serialized metadata field `mean_sampling_rate_hz` exactly equals the empirical physical rate rounded to 2 decimal places:
  - `static`: $|35.25 - 35.2507| = 0.0007\text{ Hz}$
  - `sit`: $|38.04 - 38.0361| = 0.0039\text{ Hz}$
  - `walk`: $|34.74 - 34.7391| = 0.0009\text{ Hz}$
  - `clap`: $|36.25 - 36.2515| = 0.0015\text{ Hz}$
  - `push_pull`: $|34.98 - 34.9789| = 0.0011\text{ Hz}$
- **Timing and Sequence Quality:**
  - **Zero dropped packets:** Sequence numbers increment strictly by +1 with zero gaps across all 718 new frames.
  - **Zero duplicate timestamps:** Minimum interval is $1.567\text{ ms}$, maximum interval is $64.763\text{ ms}$.
  - **Strict monotonicity:** $t_i > t_{i-1}$ for all frames; 0 backward jumps or clock reversals.
  - **Wall-clock rate transparency:** Stored `wall_clock_rate_hz` preserves the host process rate ($N/T_{\mathrm{wall}}$) without conflating it with the physical interval rate.

---

## 2. Dataset Reconciliation & Manifest Audit

An exhaustive scan comparing physical disk contents in `data/real_csi_dataset/` against `dataset_manifest.json` verified the following:

### 2.1 Inventory and Indexing
- **Total Indexed Sessions:** Exactly **29** sessions in `dataset_manifest.json`.
- **Total Physical Frames:** Exactly **4,073** frames reported in `splits_summary["total_frames"]` and independently confirmed by summing frame arrays across all 29 physical JSON files.
- **Session ID Uniqueness:** 29 unique session IDs / 29 entries (0 duplicate sessions).
- **Event ID Uniqueness:** 29 unique event IDs / 29 entries (0 duplicate events).
- **Occurrence of Phase 24 Sessions:** Each of the 5 new sessions appears **exactly once** in `dataset_manifest.json`.
- **CSV Mirror Consistency:** 29 out of 29 CSV files exist; each CSV contains exactly $N$ data rows plus 1 header row, perfectly matching its JSON counterpart (0 row count mismatches).

### 2.2 Unindexed File Traceability
- **Unindexed files detected on disk:** Exactly 1 pair:
  - `phase14_p15_real_walk_t1_1792303844_1792303844.json`
  - `phase14_p15_real_walk_t1_1792303844_1792303844.csv`
- **Reconciliation Assessment:** As documented in Phase 20 and Phase 22, this single session is a deliberate unindexed historical test trial from Phase 14 used by `test_phase20_unindexed_file_traceability` to verify quarantine and unindexed file detection.
- **No Accidental Files:** Zero accidental, duplicate, temporary, or unindexed files were introduced by Phase 24 or Phase 24.1.

### 2.3 Feature Separation Audit
- **Raw Measurements:** All 861 frames containing `raw_amplitudes` (143 frames from Phase 22 + 718 frames from Phase 24) have dimension **5** (5 complex IQ subcarriers).
- **Aligned Representation:** All 4,073 frames across all 29 sessions have dimension **56** (linear interpolation to 56 subcarriers).
- The raw physical measurement payload remains strictly segregated from derived model features.

---

## 3. Regression Test Verification

The complete regression suite spanning Phase 14 through Phase 24 was executed using Python 3.11:

**Command:**  
`py -3.11 -m pytest backend/tests/test_phase14.py backend/tests/test_phase16.py backend/tests/test_phase17.py backend/tests/test_phase18.py backend/tests/test_phase19.py backend/tests/test_phase20.py backend/tests/test_phase21.py backend/tests/test_phase22.py backend/tests/test_phase23.py backend/tests/test_safe_disconnection.py backend/tests/test_sampling_rate_audit.py -v`

### Results Breakdown
| Test Module | Focus Area | Tests Executed | Passed | Failed | Skipped | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `test_phase14.py` | Pipeline & Hardware Endpoints | 8 | 8 | 0 | 0 | **PASS** |
| `test_phase16.py` | Model Checkpoints & Invariance | 9 | 9 | 0 | 0 | **PASS** |
| `test_phase17.py` | Dataset Quality & Quality Gates | 15 | 15 | 0 | 0 | **PASS** |
| `test_phase18.py` | LOSO Splits & Leakage Safeguards | 12 | 12 | 0 | 0 | **PASS** |
| `test_phase19.py` | Validator & Quarantine Workflow | 10 | 10 | 0 | 0 | **PASS** |
| `test_phase20.py` | Dataset Manifest & Raw Separation | 10 | 10 | 0 | 0 | **PASS** |
| `test_phase21.py` | Serial Protocol & Telemetry Parser | 17 | 17 | 0 | 0 | **PASS** |
| `test_phase22.py` | First Physical Recording & Splits | 8 | 8 | 0 | 0 | **PASS** |
| `test_phase23.py` | Regression & Identity Consistency | 5 | 5 | 0 | 0 | **PASS** |
| `test_safe_disconnection.py` | ESP32-S3 Clean Shutdown & USB Safety | 8 | 8 | 0 | 0 | **PASS** |
| `test_sampling_rate_audit.py` | Sampling Rate Formula & Agreement | 8 | 8 | 0 | 0 | **PASS** |
| **Total** | **All 11 Modules** | **110** | **110** | **0** | **0** | **100% PASS** |

*Note on Warnings:* 4 harmless upstream library deprecation notices were reported (PyTorch `enable_nested_tensor` and Starlette `TestClient`).

---

## 4. Checkpoint Invariance Verification

Both production and experimental checkpoints were recomputed using MD5 hashing:

| Checkpoint | Target Path | Baseline Expected Hash | Measured Hash | Verification Verdict |
| :--- | :--- | :---: | :---: | :---: |
| **Production Checkpoint** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **UNCHANGED (MATCH)** |
| **Experimental Checkpoint** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **UNCHANGED (MATCH)** |

No checkpoint modifications, retraining, adaptation, or weight alterations occurred.

---

## 5. Documented Limitations & Evaluation Barriers

1. **Participant_03 Fall Class Absence:**  
   In compliance with safety rule 9, no falls were conducted during the Phase 24 physical campaign. Participant_03 has 6 physical recordings covering all ordinary activities (`walk`, `sit`, `clap`, `push_pull`, `static`), but contains **0 fall trials**.
2. **Model Evaluation Held on Barrier:**  
   Because of zero fall representation for Participant_03:
   - Participant_03 cannot currently serve as an independent test subject for Leave-One-Subject-Out (LOSO) fall detection evaluation.
   - `ParticipantIndependentSplitGenerator(strict_coverage=True)` strictly enforces this safeguard by raising `InadequateClassCoverageError`.
   - In accordance with project instructions, **model evaluation remains strictly on hold**.

---

## 6. Final Audit Verdict

### **PASS WITH DOCUMENTED LIMITATIONS**

**Verification Findings:**
1. **Sampling-Rate Agreement:** The mathematical formula \((N-1)/\Delta t\), the validator, the collector, the serialized JSON metadata, and the dataset manifest agree with 100% precision.
2. **Dataset Integrity:** All 29 sessions and 4,073 physical frames reconcile exactly across disk and manifest. CSV mirrors match frame-for-frame.
3. **Hardware & Subcarriers:** Raw 5-subcarrier measurements are preserved distinct from 56-channel derived features.
4. **Regression Quality:** 110 of 110 regression tests pass cleanly.
5. **Checkpoint Invariance:** Both model weights remain bit-for-bit identical to baseline records.
6. **Integrity Barrier:** Model evaluation is properly held on barrier due to the absence of supervised fall trials on Participant_03.
