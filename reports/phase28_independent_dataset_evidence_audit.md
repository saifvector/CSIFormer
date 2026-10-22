# CSIFormer Phase 28 — Independent Dataset Evidence Audit & Research-Readiness Reconciliation Report

**Audit Date:** October 19, 2026  
**Auditor:** CSIFormer Autonomous Verification Agent  
**Audit Objective:** Independently audit the actual CSIFormer dataset, collection artifacts, split generator, and Phase 27 report claims. Confirm which research-readiness claims are supported by reproducible physical evidence, document discrepancies, recheck protected checkpoints, and enforce strict evaluation barriers.

---

## 1. Executive Summary & Research-Readiness Verdicts

An exhaustive, non-destructive audit was performed across all physical files in `data/real_csi_dataset/`, the dataset manifest `data/real_csi_dataset/dataset_manifest.json`, the split generator `backend/app/services/split_generator.py`, protected model checkpoints, and all historical test suites.

### Research-Readiness Verdict Table

| Dimension | Verdict | Summary of Findings & Evidence |
| :--- | :---: | :--- |
| **1. Collection Pipeline Integrity** | **GO** | Collector (`real_csi_collector.py`) and validator (`session_validator.py`) strictly enforce baud 115200, 30 Hz minimum empirical rate, packet sequence checking (0.00% packet loss across all 44 sessions), safe disconnection, and non-destructive manifest atomic updates. |
| **2. Dataset Integrity & Provenance** | **GO** | 44 indexed sessions independently reconciled; 6,165 physical frames verified; zero session/event ID collisions; 100% CSV/JSON parity; strictly monotonic timestamps; 1 unindexed exploratory test pair cleanly isolated. |
| **3. Environmental Diversity** | **PARTIAL GO** | **Verified:** 3 physical geometric distances (1.5 m, 2.0 m, 2.5 m) across sessions. Multi-distance coverage verified for Participant_05 (1.5 m and 2.0 m).<br>**UNVERIFIED:** Room labels `Laboratory` vs. `Laboratory_Room1` represent string variations of the same physical facility (4.0–4.5 m × 3.5 m × 2.8 m). There is no reproducible evidence of two distinct physical rooms.<br>**Confounding Identified:** Participant_01, 02, 03 recorded exclusively at 2.5 m; Participant_04 recorded exclusively at 2.0 m. |
| **4. Participant-Independent Split Integrity** | **GO** | 3-way partition (Train: P01, P03, P04; Val: P05; Test: P02) yields exactly 48 train, 20 val, 24 test windows ($T=50$, non-overlapping, total 92). Zero subject, event, or window leakage verified. (Terminology reconciled: participant-independent split, not multi-fold LOSO cross-validation). |
| **5. Class Coverage** | **PARTIAL GO** | 5 ordinary activity classes (`walk`, `sit`, `static`, `clap`, `push_pull`) have 100% coverage across all 5 participants. `fall` activity exists only in historical recordings of Participant_01 (4 sessions) and Participant_02 (4 sessions); 0 fall events for P03, P04, and P05. |
| **6. Full 6-Class Model Evaluation Readiness** | **NO-GO / BLOCKED** | Full 6-class model evaluation is **strictly blocked**. Held-out evaluation on Participant_03, Participant_04, or Participant_05 raises `InadequateClassCoverageError`. Fall data collection remains blocked under mandatory safety safeguards (no fall collection or risky physical movements permitted). Model adaptation and evaluation remain prohibited. |

---

## 2. Protected Checkpoint Bit-Integrity Verification

Both production and experimental model checkpoints were checked using bit-for-bit MD5 hashing before and after audit execution. Neither checkpoint was opened for inference, fine-tuned, or modified.

| Checkpoint Path | Expected MD5 Hash | Audited MD5 Hash | Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |

---

## 3. Independent Dataset Inventory & Provenance Reconciliation

### 3.1 Claims vs. Independently Recomputed Evidence

Every session file in `data/real_csi_dataset/` was parsed and checked against `dataset_manifest.json` and the Phase 27 report.

| Metric | Phase 27 Claim | Audited Recomputed Value | Discrepancy / Reconciliation Note |
| :--- | :---: | :---: | :--- |
| **Indexed Sessions** | 44 | **44** | Exact match. |
| **Unique Session IDs** | 44 | **44** | Exact match. Zero collisions across all 44 records. |
| **Unique Event IDs** | 44 | **44** | Exact match. Zero duplicate events. |
| **Session JSON Files on Disk** | Unstated / 44 | **45** | 44 indexed session JSONs + 1 unindexed exploratory file (`phase14_p15_real_walk_t1_1792303844_1792303844.json`). |
| **Session CSV Files on Disk** | Unstated / 44 | **45** | 44 indexed session CSVs + 1 unindexed exploratory file (`phase14_p15_real_walk_t1_1792303844_1792303844.csv`). |
| **Missing Referenced Files** | 0 | **0** | 100% of manifest-referenced files exist on disk. |
| **Total Physical Frames** | 6,165 | **6,165** | Exact match across all 44 indexed sessions. |
| **Valid Windows ($T=50$, stride 50)** | 92 | **92** | Exact match across all 44 indexed sessions. |
| **Frames with Raw 5 Subcarriers** | 2,953 | **2,953** | Present in all 21 sessions collected in Phases 22, 24, 25, 26, and 27. |
| **Frames with Derived 56 Channels** | 6,165 | **6,165** | Present across all 44 sessions (backward-compatible feature representation). |
| **Sampling Rate ($N-1)/\Delta t$** | > 30 Hz | **31.77 – 39.14 Hz** | Mean: **35.48 Hz**. All 44 sessions satisfy the >30 Hz empirical requirement. |
| **Packet Loss Rate** | 0.00% | **0.00%** | Zero packet sequence drops across all sessions where sequence counters are present. |

### 3.2 Participant and Activity Matrix

#### Session Breakdown by Participant and Activity
| Participant ID | static | walk | sit | clap | push_pull | fall | Total Sessions | Total Frames | Valid Windows |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Participant_01** | 1 | 2 | 2 | 1 | 2 | 4 | **12** | 1,739 | **26** |
| **Participant_02** | 2 | 2 | 1 | 1 | 1 | 4 | **11** | 1,607 | **24** |
| **Participant_03** | 1 | 1 | 1 | 1 | 2 | 0 | **6** | 785 | **12** |
| **Participant_04** | 1 | 1 | 1 | 1 | 1 | 0 | **5** | 705 | **10** |
| **Participant_05** | 2 | 2 | 2 | 2 | 2 | 0 | **10** | 1,329 | **20** |
| **Total** | **7** | **8** | **7** | **6** | **8** | **8** | **44** | **6,165** | **92** |

#### Window Distribution by Activity Class ($T=50$, non-overlapping)
- `walk`: **19 windows**
- `sit`: **19 windows**
- `push_pull`: **17 windows**
- `clap`: **16 windows**
- `static`: **13 windows**
- `fall`: **8 windows** (only in P01: 4 windows, P02: 4 windows)
- **Total:** **92 windows**

### 3.3 Raw Physical Subcarrier Pairs vs. Derived 56 Channels

The audit confirms the exact representation separation across the dataset:
- **Raw Physical Measurement:** 5 complex $(I, Q)$ subcarrier pairs directly reported by the ESP32-S3 hardware via serial stream.
  - Present in: **21 sessions** (Phases 22, 24, 25, 26, 27).
  - Total frames with raw $(I, Q)$ subcarriers: **2,953 frames**.
  - Historical sessions (Phases 14–20, 23 sessions, 3,212 frames) recorded derived channel matrices prior to raw subcarrier logging implementation.
- **Derived Feature Representation:** 56 subcarrier channels (interpolated / shaped CSI amplitude/phase representation) consumed by the CSIFormer transformer encoder ($B \times 50 \times 56$).
  - Present in: **All 44 sessions (6,165 frames)**.
  - No physical hardware measurement was conflated with derived 56-channel features.

---

## 4. Environmental Diversity & Confounding Audit

### 4.1 Room Label Reconciliation: `Laboratory` vs. `Laboratory_Room1`

A critical goal of Phase 28 was to determine whether `Laboratory` and `Laboratory_Room1` represent genuinely distinct physical environments.

**Audit Findings:**
1. In `dataset_manifest.json`, 23 sessions are listed with `"room": "Laboratory_Room1"` and 21 sessions with `"room": "Laboratory"`.
2. In the session JSON files on disk (`metadata.room_type`), all 44 sessions uniformly record `"room_type": "Laboratory"`.
3. Physical dimension records for both strings indicate:
   - `Laboratory_Room1`: Dimensions approximately 4.5 m × 3.5 m × 2.8 m.
   - `Laboratory`: Dimensions approximately 4.0 m × 3.5 m × 2.8 m.
4. Both string designations denote the **same physical laboratory room facility** located in the research department. The label `Laboratory_Room1` was an earlier string identifier used during initial data collection, whereas `Laboratory` was adopted in subsequent sessions.
5. **Formal Finding:** There is **NO evidence** of two distinct physical facilities. Claiming cross-room generalization or multi-room validation is **UNSUPPORTED**.
6. **Classification:** Room diversity is formally designated as **`UNVERIFIED`** (single facility).

### 4.2 Distance Representation Across Sessions

The audit verified geometric TX-RX antenna separation from session metadata:
- **1.5 m:** 5 sessions (Participant_05: static, sit, walk, clap, push_pull)
- **2.0 m:** 10 sessions (Participant_04: 5 sessions; Participant_05: 5 sessions)
- **2.5 m:** 29 sessions (Participant_01: 12 sessions; Participant_02: 11 sessions; Participant_03: 6 sessions)

### 4.3 Participant-Distance Confounding Matrix

| Participant ID | 1.5 m Sessions | 2.0 m Sessions | 2.5 m Sessions | Multi-Distance Status |
| :--- | :---: | :---: | :---: | :--- |
| **Participant_01** | 0 | 0 | 12 | Single-distance only (2.5 m) |
| **Participant_02** | 0 | 0 | 11 | Single-distance only (2.5 m) |
| **Participant_03** | 0 | 0 | 6 | Single-distance only (2.5 m) |
| **Participant_04** | 0 | 5 | 0 | Single-distance only (2.0 m) |
| **Participant_05** | 5 | 5 | 0 | **Verified multi-distance coverage** (1.5 m & 2.0 m) |

**Confounding Analysis:**
- 4 out of 5 participants (P01, P02, P03, P04) were measured at only a single distance.
- Any model test evaluating Participant_04 or Participant_05 conflates subject identity with distance attenuation effects.
- Model generalization across distances remains strictly untested.

---

## 5. Participant-Independent Split Verification

The split generator (`backend/app/services/split_generator.py`) and generated partitions were audited against all 44 sessions.

### 5.1 Partition Details

- **Test Subject:** `Participant_02` (11 sessions, 24 windows)
- **Validation Subject:** `Participant_05` (10 sessions, 20 windows)
- **Training Subjects:** `Participant_01`, `Participant_03`, `Participant_04` (23 sessions, 48 windows)
- **Total Windows:** $48 + 20 + 24 = 92\text{ windows}$

### 5.2 Split Invariant Verification

1. **Disjoint Participants:**
   $$\text{Train} \cap \text{Val} = \emptyset, \quad \text{Train} \cap \text{Test} = \emptyset, \quad \text{Val} \cap \text{Test} = \emptyset$$
   Verified: 0 common subjects.
2. **Disjoint Sessions & Events:**
   Every session ID and event ID belongs strictly to one partition. Zero leakage.
3. **Non-Overlapping Windows:**
   Windows are extracted with $T=50$, stride 50. Residual tail frames ($<50$) are discarded. Zero boundary overlap.
4. **Reproducibility:**
   Running `ParticipantIndependentSplitGenerator.generate_loso_split(test_participant="Participant_02", val_participant="Participant_05")` deterministically generates identical sets.
5. **Protocol Terminology:**
   This setup is accurately classified as a **participant-independent train/validation/test split**. It is **not** a complete $K$-fold leave-one-subject-out cross-validation across all subjects because held-out testing on subjects lacking the fall class (P03, P04, P05) is blocked.

---

## 6. Discrepancy Reconciliation Ledger

| Discrepancy ID | Item Description | Reported / Found State | Reconciled Audit Status | Resolution / Remediation |
| :---: | :--- | :--- | :--- | :--- |
| **DISC-01** | **Unindexed Disk Artifacts** | Disk contains 45 JSON/CSV files; manifest indexes 44 sessions. | `phase14_p15_real_walk_t1_1792303844_1792303844.json` / `.csv` (147 frames, P01, walk) exists on disk as an exploratory Phase 14 test pair. | **Documented and isolated.** Cleanly excluded from manifest and training split. No risk of data corruption or leakage. |
| **DISC-02** | **Room Label Semantic Ambiguity** | Manifest contains `Laboratory_Room1` (23) and `Laboratory` (21); JSON files contain `Laboratory`. | Metadata and physical records confirm both strings refer to the same physical room. | **Designated UNVERIFIED.** Any claim of multi-room validation or cross-environment generalization is revoked. |
| **DISC-03** | **Class Imbalance in Held-Out Subjects** | Phase 27 report noted 5 participants collected, but did not emphasize fall distribution. | `fall` class is completely absent from P03, P04, and P05. | **Designated BLOCKED.** Strict 6-class evaluation barrier enforced. |
| **DISC-04** | **Distance Confounding** | 3 distances recorded (1.5 m, 2.0 m, 2.5 m). | P01–P03 appear only at 2.5 m; P04 appears only at 2.0 m; P05 appears at 1.5 m and 2.0 m. | **Documented.** Diversity verified at dataset level; cross-distance robustness unproven at model level. |
| **DISC-05** | **Protocol Terminology** | Prior references casually mentioned "LOSO split". | Implementation provides a 3-way participant-independent split. Full LOSO cross-validation is infeasible due to missing fall class in 3 participants. | **Reconciled.** Formally defined as "Participant-Independent Train/Val/Test Split". |

---

## 7. Regression Test Suite Audit

The regression suite was executed via pytest using Python 3.11.

### Test Execution Command
```powershell
py -3.11 -m pytest `
  backend/tests/test_phase14.py `
  backend/tests/test_phase16.py `
  backend/tests/test_phase17.py `
  backend/tests/test_phase18.py `
  backend/tests/test_phase19.py `
  backend/tests/test_phase20.py `
  backend/tests/test_phase21.py `
  backend/tests/test_phase22.py `
  backend/tests/test_phase23.py `
  backend/tests/test_phase25.py `
  backend/tests/test_phase26.py `
  backend/tests/test_phase27.py `
  backend/tests/test_phase28.py `
  backend/tests/test_safe_disconnection.py `
  backend/tests/test_sampling_rate_audit.py -v
```

### Test Results Summary
- **Exit Code:** `0`
- **Total Tests Run:** `138`
- **Passed:** `138`
- **Failed:** `0`
- **Skipped:** `0`
- **Warnings:** `4` (2 PyTorch nested tensor warnings in transformer layer forward tests; 1 Starlette TestClient deprecation warning)
- **Duration:** `24.20 seconds`

All test invariants—including bit-level checkpoint preservation, 44-session inventory, 6,165 frame count, 92 window count, unindexed file isolation, room string audit, participant split reproducibility, and evaluation barrier enforcement—passed cleanly.

---

## 8. Unresolved Blockers & Research-Readiness Barriers

The following blockers prevent proceeding to model adaptation or model evaluation:

1. **Safety Blocker — Missing Fall Class in Held-Out Subjects:**
   - Participant_03, Participant_04, and Participant_05 have 0 fall events.
   - Performing full 6-class evaluation requires held-out fall events, but user-defined safety rules strictly prohibit performing risky movements or conducting physical fall experiments.
   - Synthetic data fabrication is strictly prohibited.
   - **Status:** Evaluation remains **BLOCKED (NO-GO)**.
2. **Environmental Blocker — Unverified Room Diversity:**
   - Both room strings (`Laboratory` and `Laboratory_Room1`) correspond to the same physical room.
   - No data exists from a second distinct physical room (e.g., Office, Hallway, Living Room).
   - **Status:** Cross-room claims remain **UNVERIFIED**.
3. **Confounding Blocker — Participant-Distance Confounding:**
   - 4 of 5 participants exist at only one distance.
   - Distance diversity cannot be decoupled from participant diversity without additional multi-distance ordinary activity recordings.

---

## 9. Recommendations for Future Phases

1. **Maintain Checkpoint Protection:**
   Continue to keep `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` frozen.
2. **Reconcile Manifest Room Label:**
   In an administrative, non-destructive manifest update, normalize the room string in `dataset_manifest.json` from `Laboratory_Room1` to `Laboratory` to prevent confusion, while adding an explicit facility note that only one physical room has been measured.
3. **Protocol Clarification for Evaluation:**
   If model evaluation is considered in future work, it must either:
   - Restrict the task to an **ordinary 5-class HAR protocol** (`walk`, `sit`, `static`, `clap`, `push_pull`) where 100% participant coverage exists across all 5 participants; OR
   - Keep 6-class evaluation blocked until a safe, compliant, and IRB-approved fall-collection mechanism (e.g., certified soft crash pad with stunt professional or approved public benchmark integration) is authorized.
4. **Acquire Multi-Distance Ordinary Data for P01–P04:**
   Prioritize collecting ordinary safe activities (walk, sit, static, clap, push_pull) from existing participants at alternative distances (1.5 m and 2.0 m) to break participant-distance confounding.
