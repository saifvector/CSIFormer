# CSIFormer Phase 36 — Controlled Five-Class Cross-Room Evaluation Report

**Date:** October 19, 2026  
**Status:** GATE A & GATE B BLOCKED — MODEL INFERENCE NOT PERFORMED  
**Author:** Antigravity / CSIFormer Pair Programming Agent  
**Artifact Hash Audits:** Verified Bit-for-Bit Pristine  
**Model Inference / Evaluation:** NOT PERFORMED (BLOCKED AT GATE A & GATE B)  

---

## 1. Executive Summary

Phase 36 was chartered to execute a pre-registered five-class cross-room feasibility evaluation using the strict room-held-out and participant-held-out partition established in Phase 34 and audited in Phase 35. Crucially, the protocol required verifying that the evaluation software, label semantics, and production preprocessing path are genuinely compatible with the actual model artifacts before running any inference.

Following exhaustive source-code tracing, dataset provenance analysis, and training-history forensics:

1. **Gate A is BLOCKED:** Forensic inspection of original training labels, training code, and dataset documentation confirms that model output 6 was trained on **Dynamic Arm Boxing** (`box` from NTU-Fi) and model output 8 was trained on **Table Cleaning Motion** (`clean` from NTU-Fi). The real ESP32-S3 dataset labels `static` (stationary human body standing still) and `sit` (sitting transition into a chair) are **not semantically equivalent** to boxing or table cleaning. The alias pairings (`Static/Box` and `Sit/Clean`) were post-hoc ad-hoc constructs introduced in scratch evaluation scripts. Equating them produces scientifically invalid evaluation metrics.
2. **Gate B is BLOCKED:** The official production inference service (`LivePipelineService`) only implements streaming inference over live serial buffers and does not provide an offline window evaluation path. Furthermore, there is material training-versus-inference preprocessing disparity: during Phase 13 training, NTU-Fi samples bypassed STFT entirely (duplicating raw CSI into Doppler), whereas runtime preprocessing applies STFT Doppler extraction parameterized for 30.0 Hz.
3. **Gate C PASSED (GO):** The strict room-held-out and participant-held-out split was reproduced with 100% precision (75 train / 20 val / 11 test / 49 excluded windows) with zero leakage.
4. **Mandatory Protocol Action:** As strictly instructed by the Phase 36 protocol ("*If any gate is blocked, do not run inference. Produce the report documenting the blocker, preserve all protected artifacts, and recommend the smallest safe next step*"), **model inference was NOT executed**.
5. **Artifact Protection:** Both protected checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) were verified bit-for-bit pristine before and after all audits. The full repository test suite (232 tests across 33 test files) passed with 100% success.

---

## 2. Final Status Summary Table

| Evaluation Gate / Component | Status | Detailed Finding & Forensic Verification |
| :--- | :---: | :--- |
| **Semantic Label Compatibility (Gate A)** | **BLOCKED** | Output 6 is **Dynamic Arm Boxing** (`box`); output 8 is **Table Cleaning Motion** (`clean`). Zero semantic equivalence to `static` (standing still) or `sit` (chair descent). |
| **Production Preprocessing Path (Gate B)** | **BLOCKED** | `LivePipelineService` lacks offline batch evaluation; training-time NTU-Fi bypassed STFT whereas runtime inference computes STFT at 30.0 Hz. |
| **Strict Split Integrity (Gate C)** | **PASSED (GO)** | Non-mutating generation reproduced 75 train / 20 val / 11 test / 49 excluded windows. Zero `Office_Room2` or `Participant_02` leakage. |
| **Production Evaluation Status (Gate D)** | **NOT PERFORMED** | Halted at Gates A & B; zero inference forward passes executed. |
| **Experimental Comparison Status (Gate D)** | **NOT PERFORMED** | Halted at Gates A & B; zero inference forward passes executed. |
| **Checkpoint Integrity (Gate E)** | **PASSED (GO)** | Production MD5: `383b4d98c08f8970b0443738f170ec01` (**MATCH**)<br>Experimental MD5: `ab3d97a04d78edf75d807178772bc828` (**MATCH**) |
| **Regression Status (Gate E)** | **PASSED (GO)** | Full repository regression suite executed: **232 / 232 tests passed across 33 test files (0 failures, 100% pass rate)**. |
| **Claims Limitations** | **ENFORCED** | No room-invariance or generalization claims made; invalid aliases rejected. |

---

## 3. Gate A Audit — Verification of Training-Label Semantics

The protocol required tracing the original training datasets, training label encoders, model output indices, and real-CSI manifest to establish whether the target five-class mappings are semantically valid, not merely numerically equal.

### 3.1 Provenance of Model Output Indices

Both protected checkpoints (`models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`) were trained using the unified 12-class spatial-temporal taxonomy defined in [`backend/app/datasets/combined_dataset.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/datasets/combined_dataset.py#L44-L57):

```python
UNIFIED_CLASSES = [
    "Push&Pull",     # Index 0 (Widar 3.0 gesture)
    "Sweep",         # Index 1 (Widar 3.0 gesture)
    "Clap",          # Index 2 (Widar 3.0 gesture)
    "Slide",         # Index 3 (Widar 3.0 gesture)
    "Draw-O",        # Index 4 (Widar 3.0 gesture)
    "Draw-Zigzag",   # Index 5 (Widar 3.0 gesture)
    "box",           # Index 6 (NTU-Fi activity, offset +6)
    "circle",        # Index 7 (NTU-Fi activity, offset +6)
    "clean",         # Index 8 (NTU-Fi activity, offset +6)
    "fall",          # Index 9 (NTU-Fi activity, offset +6)
    "run",           # Index 10 (NTU-Fi activity, offset +6)
    "walk"           # Index 11 (NTU-Fi activity, offset +6)
]
```

### 3.2 Granular Forensic Analysis by Activity

| Candidate Mapping | Manifest Class ID | Model Output Logit | Physical Activity in Real Dataset | Ground-Truth Training Source & Activity Definition | Semantic Validity |
| :--- | :---: | :---: | :--- | :--- | :---: |
| `push_pull` $\rightarrow$ `Push&Pull` | `0` | `0` | Arm pushing and pulling in LOS | Widar 3.0 Gestures 1 & 7: Arm push and pull | **VALID** |
| `clap` $\rightarrow$ `Clap` | `2` | `2` | Two-hand rhythmic clapping | Widar 3.0 Gestures 3 & 9: Hand clapping | **VALID** |
| `walk` $\rightarrow$ `walk` | `11` | `11` | Ambient forward locomotion in LOS | NTU-Fi HAR Class 5: Ambient walking locomotion | **VALID** |
| `static` $\rightarrow$ `box` | `6` | `6` | **Static / Background**: Stationary human standing still with torso still (zero gross movement) | NTU-Fi HAR Class 0: **Dynamic Arm Boxing** (`reports/full_training_audit.md:37`: *"Dynamic Arm Boxing"*; `generate_dataset_reports.py:307`: *"Punching / boxing arm extension"*) | **FATAL MISMATCH (BLOCKED)** |
| `sit` $\rightarrow$ `clean` | `8` | `8` | **Sitting Transition**: Gross-motor vertical body descent into a chair | NTU-Fi HAR Class 2: **Table Cleaning Motion** (`reports/full_training_audit.md:39`: *"Table Cleaning Motion"*; `generate_dataset_reports.py:309`: *"Sweeping surface motion"*) | **FATAL MISMATCH (BLOCKED)** |

### 3.3 Supporting Forensic Evidence for Gate A Blocker

1. **Original Dataset Specification:**
   - [`datasets/ntufi_har/metadata/config.json`](file:///C:/Users/saifu/Desktop/4-1%20project/datasets/ntufi_har/metadata/config.json) defines the classes as: `["box", "circle", "clean", "fall", "run", "walk"]`.
   - In the underlying SenseFi benchmark paper (*Chen et al., "SenseFi: A Library and Benchmark for WiFi CSI-based Human Sensing"*), `box` corresponds to boxing punches, and `clean` corresponds to cleaning a tabletop.
2. **Repository Training Documentation:**
   - [`reports/full_training_audit.md:L37`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/full_training_audit.md#L37):
     `| 06 | box | NTU-Fi HAR (Atheros) | Dynamic Arm Boxing | 200 | 0.90% |`
   - [`reports/full_training_audit.md:L39`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/full_training_audit.md#L39):
     `| 08 | clean | NTU-Fi HAR (Atheros) | Table Cleaning Motion | 200 | 0.90% |`
   - [`backend/app/services/generate_dataset_reports.py:L307-309`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/generate_dataset_reports.py#L307-L309):
     `1. box (Punching / boxing arm extension)`  
     `3. clean (Sweeping surface motion)`
3. **Production Live Service Mapping:**
   - [`backend/app/services/live_pipeline_service.py:L29-31`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L29-L31) explicitly maps:
     - `6: "Box (NTU-Fi)"`
     - `8: "Clean (NTU-Fi)"`
4. **Origin of the False Equivalence:**
   - In Phase 15, physical data was acquired for `static` (stationary human standing still) and `sit` (sitting down into a chair).
   - In [`scratch/evaluate_phase15_baseline.py:L39-40`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/evaluate_phase15_baseline.py#L39-L40), the author paired them as `6: "Static/Box"` and `8: "Sit/Clean"` simply because the model output had available slots at indices 6 and 8.
   - The checkpoints were **never trained on static standing or chair sitting**.
   - Physically, dynamic arm boxing produces rapid high-frequency Doppler shifts ($\pm 20\text{ Hz}$ to $\pm 40\text{ Hz}$), whereas static standing produces near-zero Doppler shifts ($\approx 0\text{ Hz}$). Evaluating static CSI against a boxing classifier is scientifically invalid.

**Gate A Determination:** **BLOCKED**. Evaluated mappings for `static` $\rightarrow$ `box` and `sit` $\rightarrow$ `clean` lack semantic foundation.

---

## 4. Gate B Audit — Verification of Complete Production Inference Path

The protocol required tracing production code from a raw `[50, 56]` window through preprocessing to both model inputs and final logits.

### 4.1 Production Pipeline Architecture Traced

In [`backend/app/services/live_pipeline_service.py:L194-207`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L194-L207):

```python
# Raw Branch Normalization:
amp_mean = raw_win.mean(axis=0, keepdims=True)
amp_std = raw_win.std(axis=0, keepdims=True) + 1e-6
norm_raw = (raw_win - amp_mean) / amp_std
tensor_raw = torch.tensor(norm_raw, dtype=torch.float32).unsqueeze(0).to(self.device)

# Doppler Branch STFT:
doppler_mat = self.preprocessor.compute_doppler_spectrogram(raw_win)
tensor_dopp = torch.tensor(doppler_mat, dtype=torch.float32).unsqueeze(0).to(self.device)

# Dual-Branch Forward Pass:
out = self.model(tensor_raw, tensor_dopp)
logits = out["activity_logits"]  # [1, 12]
```

### 4.2 Material Discrepancies Identified

1. **Absence of Offline Batch Inference Method:**
   - `LivePipelineService` is strictly architected around `self.collector.get_latest_window()`, which depends on a live serial connection to COM5.
   - There is no production service API to ingest pre-recorded `[50, 56]` window arrays from disk dataset files.
   - Performing evaluation would require writing an ad-hoc test harness script, which directly conflicts with the constraint: "*Do not replace the production pipeline with an ad hoc NumPy extraction or a newly invented STFT implementation.*"
2. **Training-Time vs. Runtime Preprocessing Disparity:**
   - In [`scratch/execute_phase13_2_dual_branch_and_benchmark.py:L325-326`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase13_2_dual_branch_and_benchmark.py#L325-L326), NTU-Fi training samples bypassed STFT entirely:
     `nt_dopp_train.append(s["csi"])  # Supply csi to both branches for Atheros`
   - In contrast, runtime preprocessing in `LivePipelineService` computes STFT with `carrier_freq=2.442e9, source_rate_hz=30.0, stft_window=32, stft_noverlap=24, stft_nfft=64`.
   - The actual ESP32-S3 physical collection rate is $\approx 35.58\text{ Hz}$, creating a mismatch with the hardcoded $30.0\text{ Hz}$ STFT preprocessor configuration in `LivePipelineService`.

**Gate B Determination:** **BLOCKED**. Material implementation and preprocessing discrepancies exist.

---

## 5. Gate C Audit — Strict Partition Reproduction

The strict evaluation partition was reproduced using the verified non-mutating method `ParticipantIndependentSplitGenerator(manifest_path).generate_strict_cross_room_split(output_manifest_path=None)`:

### 5.1 Partition Accounting & Membership

| Partition | Assigned Participants | Physical Room | Sessions | Frames | 50-Frame Sliced Windows | Target Classes Present |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Train** | `Participant_01`, `Participant_03`, `Participant_04` | `Laboratory_Room1` | 36 | 5,051 | 75 | `static` (15), `sit` (15), `walk` (16), `clap` (14), `push_pull` (15) |
| **Validation** | `Participant_05` | `Laboratory_Room1` | 10 | 1,388 | 20 | `static` (4), `sit` (4), `walk` (4), `clap` (4), `push_pull` (4) |
| **Test** | `Participant_02` | `Office_Room2` | 5 | 714 | 11 | `static` (2), `sit` (2), `walk` (2), `clap` (2), `push_pull` (3) |
| **Excluded** | `Participant_01` (Office), `Participant_02` (Lab), Falls | Both | 23 | 3,254 | 49 | 4 falls, 14 Lab P02, 5 Office P01 |
| **Total** | All 5 Participants | Both Rooms | **74** | **10,407** | **155** | Complete dataset preservation |

### 5.2 Test Set Windows Breakdown

The 11 test windows are derived exclusively from `Participant_02` in `Office_Room2` at 2.0 m:
1. `phase16_real_static_Participant_02_1792404586_1792404586`: 142 frames $\rightarrow$ **2 windows**
2. `phase16_real_sit_Participant_02_1792404619_1792404619`: 139 frames $\rightarrow$ **2 windows**
3. `phase16_real_walk_Participant_02_1792404736_1792404736`: 141 frames $\rightarrow$ **2 windows**
4. `phase16_real_clap_Participant_02_1792404793_1792404793`: 142 frames $\rightarrow$ **2 windows**
5. `phase16_real_push_pull_Participant_02_1792404825_1792404825`: 150 frames $\rightarrow$ **3 windows**

- **Zero Leakage:** `Office_Room2` and `Participant_02` are strictly excluded from train and val.
- **Manifest Immutability:** `data/real_csi_dataset/dataset_manifest.json` on disk remained completely untouched.

**Gate C Determination:** **PASSED (GO)**.

---

## 6. Gate D — Controlled Inference Execution Status

Because **Gate A is BLOCKED** (semantic incompatibility of `static` and `sit`) and **Gate B is BLOCKED** (production inference path limitations), the project instructions strictly mandate:

> *"Proceed only if Gates A, B, and C all pass."*  
> *"If any gate is blocked, do not run inference. Produce the report documenting the blocker, preserve all protected artifacts, and recommend the smallest safe next step."*

### Inference Status Confirmation
- **Primary Production Checkpoint (`csiformer_phase13_best.pth`):** **INFERENCE NOT PERFORMED**.
- **Secondary Experimental Checkpoint (`csiformer_phase15_adapted.pth`):** **INFERENCE NOT PERFORMED**.
- **Zero Forward Passes:** No model weights were loaded; no synthetic or real logits were generated.
- **Denominators & Support:** Pre-registered denominator is 11 windows across 5 sessions. Zero predictions were fabricated or evaluated under false label assumptions.

---

## 7. Gate E — Integrity and Regression Verification

### 7.1 Checkpoint MD5 Hash Invariance

MD5 checksums were calculated before and after all forensic investigations:

| Model Artifact File | Protected Reference MD5 | Actual Computed MD5 | Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (BIT-FOR-BIT IDENTICAL)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (BIT-FOR-BIT IDENTICAL)** |

### 7.2 Dataset and Manifest Integrity

- `data/real_csi_dataset/dataset_manifest.json`: Verified unmodified.
- All raw CSV and JSON recording files: Verified unmodified.

### 7.3 Regression Suite Execution

A complete regression audit was performed across the entire repository test suite:

1. **Targeted Gate Tests:**
   - Command: `py -3.11 -m pytest backend/tests/test_phase36.py -v`
   - Result: **4 passed in 11.23s (Exit code 0)**.
2. **Cross-Room Protocol Suite (Phases 34–36):**
   - Command: `py -3.11 -m pytest backend/tests/test_phase34.py backend/tests/test_phase35.py backend/tests/test_phase36.py -v`
   - Result: **16 passed in 6.45s (Exit code 0)**.
3. **Full Repository Regression Suite:**
   - Command: `py -3.11 -m pytest backend/tests/ -v`
   - Result: **232 passed, 0 failed across all 33 test files in 71.09s (Exit code 0)**.
   - Skips: 0. Failures: 0. Pass rate: **100.0%**.

---

## 8. Scientific Interpretation & Recommended Safe Next Steps

### 8.1 Why This Gate Block Protects the Research

Evaluating `static` against a model trained on `Dynamic Arm Boxing`, and `sit` against a model trained on `Table Cleaning Motion`, would produce meaningless numbers that corrupt the literature:
- If the model predicted class 6 for `static`, it would be falsely credited for recognizing a stationary body when it was actually looking for boxing punches.
- Conversely, when the model correctly rejects `static` as NOT being boxing, it would be penalized as a "cross-room failure" when it is actually behaving as trained.

### 8.2 Recommended Smallest Safe Next Steps

To resolve the blocker without violating project invariants or modifying protected checkpoints:

1. **Option 1 (Recommended — Restricted 3-Class Cross-Room Evaluation):**
   - Perform a controlled cross-room evaluation strictly on the **3 verified, semantically compatible classes**:
     - `walk` $\rightarrow$ Class 11 (`walk`)
     - `clap` $\rightarrow$ Class 2 (`Clap`)
     - `push_pull` $\rightarrow$ Class 0 (`Push&Pull`)
   - Test partition would contain 7 windows across 3 sessions (2 walk, 2 clap, 3 push_pull) from `Participant_02` in `Office_Room2`.
   - This provides a scientifically valid, unambiguous cross-room probe on genuinely shared classes.
2. **Option 2 (Production Inference Service Method Addition):**
   - Implement an explicit `predict_window(raw_window: np.ndarray) -> Dict[str, Any]` method on `LivePipelineService` that standardizes offline batch inference through the exact production preprocessing path, eliminating any need for scratch evaluation scripts.
3. **Option 3 (Explicit Domain Adaptation Phase):**
   - If a true 5-class or 6-class model including `static` and `sit` is required, specify a separate authorized retraining or head-adaptation phase that explicitly introduces physical standing and sitting supervision into the training loss.
