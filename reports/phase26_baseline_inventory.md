# CSIFormer Phase 26 — Baseline Dataset Inventory & Gap Analysis

**Audit Date:** October 19, 2026  
**Auditor:** Antigravity Autonomous Agent  
**Repository Root:** `C:\Users\saifu\Desktop\4-1 project`  
**Dataset Directory:** `data/real_csi_dataset/`  
**Dataset Manifest:** `data/real_csi_dataset/dataset_manifest.json`  

---

## 1. Executive Baseline Summary

| Metric | Measured Value | Verification Method | Status |
| :--- | :---: | :--- | :---: |
| **Manifest Indexed Sessions** | **34** | Parsed `dataset_manifest.json` entries | **VERIFIED** |
| **Session JSON Files on Disk** | **35** | `data/real_csi_dataset/*.json` (excluding 2 manifest files) | **AUDITED** |
| **Session CSV Files on Disk** | **35** | `data/real_csi_dataset/*.csv` | **AUDITED** |
| **Indexed File Pair Correspondence** | **34 / 34** | Manifest `json_file` and `csv_file` existence check | **100% MATCH** |
| **Unindexed Recordings on Disk** | **1 pair** | `phase14_p15_real_walk_t1_1792303844_1792303844` (.json & .csv) | **ISOLATED** |
| **Corrupted / Invalid Sessions** | **0** | `DatasetIntegrityValidator.validate_session_file` on all 34 files | **0 ERRORS** |
| **Quarantined Sessions** | **0** | `data/real_csi_dataset/quarantine/` empty | **CLEAN** |
| **Total Physical Frames** | **4,777** | Sum of frame arrays across 34 session JSON files | **VERIFIED** |
| **Total Non-Overlapping Windows ($T=50$)** | **72** | Window extraction ($\sum \lfloor N_{\text{frames}} / 50 \rfloor$) | **VERIFIED** |
| **Distinct Participants** | **4** | `Participant_01`, `Participant_02`, `Participant_03`, `Participant_04` | **VERIFIED** |
| **Distinct Event IDs** | **34** | Unique UUIDs/session event mappings across all sessions | **NO COLLISION** |
| **Duplicate Session IDs** | **0** | Manifest session ID set uniqueness check | **NO COLLISION** |
| **Geometric Environments** | **3** | `Laboratory_Room1 @ 2.5m` (23), `Laboratory @ 2.5m` (6), `Laboratory @ 2.0m` (5) | **VERIFIED** |
| **Raw Physical Subcarriers** | **5** | Measured complex IQ pairs (`raw_amplitudes`, `raw_phases`) | **VERIFIED** |
| **Derived Channel Features** | **56** | HT20 interpolated channels (`amplitudes`, `phases`) | **VERIFIED** |
| **Frames with Raw 5-Subcarriers** | **1,565** | Present in all sessions collected in Phases 22, 24, and 25 | **VERIFIED** |
| **Production Checkpoint Hash** | `383b4d98c08f8970b0443738f170ec01` | MD5 of `models/csiformer_phase13_best.pth` | **MATCH** |
| **Experimental Checkpoint Hash** | `ab3d97a04d78edf75d807178772bc828` | MD5 of `models/csiformer_phase15_adapted.pth` | **MATCH** |

---

## 2. Model Checkpoint Protection & Hash Verification

In accordance with Safeguards 7, 8, and 10:
- No model training, adaptation, fine-tuning, or benchmarking was performed.
- Both checkpoint weights were audited for bit-for-bit invariance:

```text
models/csiformer_phase13_best.pth:     383b4d98c08f8970b0443738f170ec01 (MD5 VERIFIED)
models/csiformer_phase15_adapted.pth:  ab3d97a04d78edf75d807178772bc828 (MD5 VERIFIED)
```

---

## 3. Detailed Participant-by-Activity Matrix

Breakdown of physical sessions and validated non-overlapping windows ($T=50$) per participant and activity:

| Participant ID | `static` | `sit` | `walk` | `clap` | `push_pull` | `fall` | Total Sessions | Total Packets | Valid Windows ($T=50$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Participant_01** | 2 (4) | 2 (4) | 2 (4) | 2 (4) | 2 (5) | 2 (4) | 12 | 1,655 | 25 |
| **Participant_02** | 1 (1) | 2 (6) | 2 (5) | 2 (4) | 2 (4) | 2 (4) | 11 | 1,557 | 24 |
| **Participant_03** | 1 (2) | 1 (3) | 2 (4) | 1 (2) | 1 (2) | 0 (0) | 6 | 861 | 13 |
| **Participant_04** | 1 (2) | 1 (2) | 1 (2) | 1 (2) | 1 (2) | 0 (0) | 5 | 704 | 10 |
| **Total** | **5 (9)** | **6 (15)** | **7 (15)** | **6 (12)** | **6 (13)** | **4 (8)** | **34** | **4,777** | **72** |

*Notation: `Sessions (Windows)`.*

---

## 4. Environmental Distribution & Diversity

| Environment Setting | Room Name | Distance (m) | Session Count | Contributing Participants | Notes |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Env 1** | `Laboratory_Room1` | 2.5 m | 23 | Participant_01, Participant_02 | Baseline sessions from Phases 14–17 |
| **Env 2** | `Laboratory` | 2.5 m | 6 | Participant_03 | Phase 22 & Phase 24 sessions |
| **Env 3** | `Laboratory` | 2.0 m | 5 | Participant_04 | Phase 25 initial distance variation |

---

## 5. File System & Manifest Reconciliation

1. **Manifest File Registry:**
   - Primary Manifest: `data/real_csi_dataset/dataset_manifest.json` (34 sessions).
   - Versioned Split Manifest: `data/real_csi_dataset/dataset_manifest_p17_loso.json` (Phase 17 reference split).
2. **Session Data Files:**
   - 34 session JSON files and 34 CSV mirrors are fully indexed in `dataset_manifest.json`.
   - 1 unindexed session file pair exists on disk:
     - `phase14_p15_real_walk_t1_1792303844_1792303844.json` (144 frames)
     - `phase14_p15_real_walk_t1_1792303844_1792303844.csv`
     - *Audit finding:* This was an exploratory test recording from Phase 14 before final standardized naming and manifest registration. It remains safely isolated and is not indexed into the formal manifest.
3. **Data Quality & Integrity:**
   - 34 / 34 indexed sessions passed all checks in `DatasetIntegrityValidator`.
   - 0 duplicate timestamps, 0 non-monotonic steps, 0 packet loss inside records.
   - All frame counts match between metadata and actual frame arrays.

---

## 6. Raw vs. Derived CSI Telemetry

- **Physical Baseband Measurement:** 5 complex subcarrier pairs (10 floating-point values: 5 amplitudes, 5 phases) extracted directly from ESP32-S3 serial stream.
- **Model Tensor Alignment:** 56 subcarriers linearly interpolated to standard IEEE 802.11n HT20 subcarrier indexing.
- **Dimensionality Audit:**
  - `raw_amplitudes` and `raw_phases`: length 5 in all 1,565 frames across Phases 22, 24, and 25.
  - `amplitudes` and `phases`: length 56 in all 4,777 frames across all 34 sessions.

---

## 7. Split Leakage & LOSO Invariance Audit

Using `ParticipantIndependentSplitGenerator(manifest_path)`:
- **3-Way Leave-One-Subject-Out Partition:**
  - `Train`: `['Participant_01', 'Participant_03']` (18 sessions, 38 windows)
  - `Val`: `['Participant_04']` (5 sessions, 10 windows)
  - `Test`: `['Participant_02']` (11 sessions, 24 windows)
- **Leakage Prevention Checks:**
  - Participant Overlap: $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$ (0.0%).
  - Event Overlap: 0 common event IDs across partitions (0.0%).
  - Window Overlap: Non-overlapping slices of length $T=50$, zero shared frames across windows (0.0%).
- **Class Coverage Finding:**
  - `fall` activity exists in `Participant_01` (4 windows) and `Participant_02` (4 windows).
  - `Participant_03` and `Participant_04` have 0 `fall` records (due to safety restrictions).
  - Therefore, Leave-One-Subject-Out evaluation with `Participant_03` or `Participant_04` as held-out test subject raises `InadequateClassCoverageError`. Evaluation must remain safely blocked.

---

## 8. Current Git Working Tree Status

- **Branch:** `main` (ahead of `origin/main` by 8 local commits)
- **Unstaged modified files:** 12 files (collector, workflow, validator, test modules, manifest)
- **Untracked files:** Test suites for Phases 23 and 25, session data files for Participant_03 and Participant_04, Phase 23–25 markdown reports.
- **Remote / Commit Status:** Zero unauthorized commits or remote pushes executed.
