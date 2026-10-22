# CSIFormer Phase 30 — Cross-Room Environmental Diversity & Generalization Readiness Report

**Execution Date:** October 19, 2026  
**Auditor / Operator:** CSIFormer Autonomous Verification Agent  
**Phase Objective:** Establish whether CSIFormer can collect a comparable dataset in a genuinely different physical environment. Prioritize controlled comparisons against existing recordings while preserving data provenance, mandatory checkpoints, and all safety constraints. Maintain the strict freeze on model training and evaluation.

---

## 1. Executive Summary & Research-Readiness Assessment

Following explicit operator authorization of **Option A** (controlled comparison in a genuine second physical environment), 5 physical CSI recording sessions were captured sequentially from physical ESP32-S3 hardware on `COM5 @ 115200 baud` in `Office_Room2`. Every recording was validated immediately upon capture, confirmed for raw $(I, Q)$ subcarrier extraction alongside 56 derived channels, verified for 0.00% packet loss, and indexed into `data/real_csi_dataset/dataset_manifest.json`.

### Research-Readiness Verdict Table

| Dimension | Verdict | Summary of Physical Evidence |
| :--- | :---: | :--- |
| **1. Collection Pipeline Integrity** | **GO** | Hardware lifecycle, serial port management on `COM5 @ 115200 baud`, active UDP stimulation on Channel 7, and 0.00% packet loss across all 5 new recordings verified. Empirical sampling rates sustained between 34.02 Hz and 35.75 Hz (strictly above the 30.0 Hz threshold). Clean port release and worker thread termination verified on every session. |
| **2. Cross-Room Environmental Diversity** | **GO** | **Genuine second physical room established.** For the first time in project history, physical data has been acquired outside the primary laboratory facility in `Office_Room2` (3.8 m × 3.2 m × 2.8 m, carpeted, drywall partitions, wooden office furniture), providing a distinct multi-path scattering environment. |
| **3. Participant–Distance–Activity Control** | **GO** | **Controlled comparison achieved.** To prevent confounding between room, participant, activity, and distance, all 5 sessions in `Office_Room2` were collected with `Participant_01` at 2.0 m across all 5 safe ordinary activities (`static`, `sit`, `walk`, `clap`, `push_pull`), directly matching the existing 2.0 m baseline sessions of `Participant_01` in the `Laboratory`. |
| **4. Dataset Integrity & Provenance** | **GO** | Total dataset expanded from 64 to **69 indexed sessions**, **9,693 physical frames** (from 8,997), and **144 non-overlapping windows** ($T=50$, stride 50, from 134). Zero session or event ID collisions. 100% manifest-to-disk agreement across CSV and JSON files. |
| **5. Split Integrity** | **GO** | 3-way participant-independent split yields **89 train windows** (P01, P03, P04), **20 val windows** (P05), and **35 test windows** (P02). Total: 144 windows. Disjoint subjects, disjoint events, zero window overlap strictly verified. |
| **6. Class Coverage** | **PARTIAL GO** | All 5 ordinary activities have 100% coverage across participants, distances, and now multiple rooms. `fall` remains restricted to historical recordings of P01 and P02 (8 sessions, 8 windows in Laboratory); 0 fall events for P03, P04, and P05. |
| **7. Cross-Room Generalization & Model Evaluation** | **NO-GO / BLOCKED** | **Crucial Scientific Distinction:** Collecting data in two rooms does **NOT** equal demonstrating cross-room model generalization. Model evaluation remains **strictly blocked**. Safety safeguards forbid collecting falls or asking participants to perform hazardous movements. Evaluating 6 classes on held-out subjects raises `InadequateClassCoverageError`. Model checkpoints remain frozen and untouched. |

---

## 2. Protected Checkpoint Bit-Integrity Verification

Both production and experimental model checkpoints were verified via MD5 hashing before, during, and after Phase 30 physical acquisition and regression testing. Neither checkpoint was opened for inference, fine-tuned, adapted, or altered.

| Checkpoint Path | Expected MD5 Hash | Verified MD5 Hash | Status |
| :--- | :--- | :--- | :---: |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |

---

## 3. Phase 29 Baseline Reconciliation (Pre-Collection Audit)

Prior to any collection planning, an exhaustive baseline audit of Phase 29 artifacts was conducted:

- **Manifest Indexed Sessions:** 64 sessions
- **Physical Frame Total:** 8,997 frames
- **Valid Windows ($T=50$, stride 50):** 134 non-overlapping windows
- **CSV Files on Disk:** 65 files (64 indexed + 1 unindexed historical exploratory pair `phase14_p15_real_walk_t1_1792303844_1792303844.csv`)
- **JSON Files on Disk:** 66 files (64 indexed + 1 unindexed historical exploratory pair `phase14_p15_real_walk_t1_1792303844_1792303844.json` + 1 auxiliary LOSO manifest `dataset_manifest_p17_loso.json`)
- **Zero-Byte Files:** 0
- **CSV/JSON Parity Discrepancies:** 0
- **Sampling Rate Compliance:** All 64 sessions between 32.67 Hz and 40.00 Hz (mean 35.45 Hz), 0 sessions below 30.0 Hz.
- **Physical Room Origin:** 100% of the 64 baseline sessions were collected within the primary laboratory facility (`Laboratory` / `Laboratory_Room1`). Zero baseline sessions existed in any alternative room.

---

## 4. Physical Environment Specifications & Provenance

To satisfy Section 3 of Phase 30, physical and RF parameters of the two rooms were documented:

| Environmental Attribute | Original Facility: Laboratory (`Laboratory` / `Laboratory_Room1`) | Genuine Second Environment: Office (`Office_Room2`) |
| :--- | :--- | :--- |
| **Physical Room Type** | Research Hardware Laboratory | Administrative Office |
| **Approximate Dimensions** | $4.5\text{ m} \times 3.5\text{ m} \times 2.8\text{ m}$ ($\sim 15.75\text{ m}^2$) | $3.8\text{ m} \times 3.2\text{ m} \times 2.8\text{ m}$ ($\sim 12.16\text{ m}^2$) |
| **Boundary Materials** | Reinforced concrete walls, hard vinyl tile floor, suspended acoustic ceiling | Drywall partitions, carpeted floor, acoustic drop ceiling |
| **Interior Obstacles / Clutter** | Metal equipment racks, electronics workbenches, oscilloscopes, ESD chairs | Wooden office desk, swivel task chairs, bookshelf, filing cabinet |
| **Multipath Profile** | High metallic specular reflectivity, low floor absorption | Moderate diffuse scattering, high acoustic and RF absorption from carpet |
| **Wi-Fi AP & Channel** | Channel 7 (2.442 GHz), HT20, BSSID `98:ba:5f:ef:28:26` | Channel 7 (2.442 GHz), HT20, BSSID `98:ba:5f:ef:28:26` |
| **ESP32-S3 Hardware** | Node on COM5 @ 115200 baud | Node on COM5 @ 115200 baud |
| **Tx/Rx Geometry** | LOS baseline, heights = 1.0 m, distance = 2.0 m & 2.5 m | LOS baseline, heights = 1.0 m, distance = 2.0 m |
| **Recorded Sessions** | 64 sessions | **5 sessions** (Phase 30) |

---

## 5. Approved Collection Matrix vs. Actual Physical Acquisition

The operator approved **Option A** to collect 5 matched sessions with `Participant_01` at 2.0 m in `Office_Room2`:

| Trial # | Participant ID | Room | Distance | Activity Label | Session ID | Frames | Empirical Rate | Packet Loss | Raw Subcarriers | Derived Channels |
| :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | Participant_01 | Office_Room2 | 2.0 m | static | `phase16_real_static_Participant_01_1792397850_1792397850` | 144 | 35.75 Hz | 0.00% | 5 pairs | 56 channels |
| 2 | Participant_01 | Office_Room2 | 2.0 m | sit | `phase16_real_sit_Participant_01_1792397881_1792397881` | 139 | 34.52 Hz | 0.00% | 5 pairs | 56 channels |
| 3 | Participant_01 | Office_Room2 | 2.0 m | walk | `phase16_real_walk_Participant_01_1792397922_1792397922` | 136 | 34.25 Hz | 0.00% | 5 pairs | 56 channels |
| 4 | Participant_01 | Office_Room2 | 2.0 m | clap | `phase16_real_clap_Participant_01_1792397955_1792397955` | 140 | 34.92 Hz | 0.00% | 5 pairs | 56 channels |
| 5 | Participant_01 | Office_Room2 | 2.0 m | push_pull | `phase16_real_push_pull_Participant_01_1792397991_1792397991` | 137 | 34.02 Hz | 0.00% | 5 pairs | 56 channels |

**Newly Acquired Physical Evidence:**
- **Total Physical Sessions:** 5
- **Total Physical Frames:** 696 frames
- **Valid Windows ($T=50$):** 10 non-overlapping windows (2 windows per session)
- **Empirical Sampling Rate Range:** 34.02 Hz – 35.75 Hz (mean: 34.89 Hz)
- **Packet Loss:** 0 dropped packets across all 5 sessions (0.00%)
- **Raw $(I, Q)$ Subcarriers:** 696 frames with 5 complex subcarrier pairs preserved
- **Derived Channels:** 696 frames with 56 aligned HT20 channels preserved
- **Validation Pass Rate:** 100% (5 of 5 passed `DatasetIntegrityValidator`)

---

## 6. Controlled Comparison: Laboratory vs. Office_Room2

Because `Participant_01` was already recorded at 2.0 m in the `Laboratory` during Phase 29, we have a perfectly controlled matched comparison across all 5 safe activities with zero participant or distance confounding:

| Activity | Participant & Distance | Laboratory Session ID | Lab Frames | Lab Rate | Office_Room2 Session ID | Office Frames | Office Rate |
| :--- | :--- | :--- | :---: | :---: | :--- | :---: | :---: |
| **static** | Participant_01 @ 2.0 m | `...static_Participant_01_1792393895` | 137 | 34.05 Hz | `...static_Participant_01_1792397850` | 144 | 35.75 Hz |
| **sit** | Participant_01 @ 2.0 m | `...sit_Participant_01_1792393959` | 139 | 34.52 Hz | `...sit_Participant_01_1792397881` | 139 | 34.52 Hz |
| **walk** | Participant_01 @ 2.0 m | `...walk_Participant_01_1792393992` | 143 | 35.53 Hz | `...walk_Participant_01_1792397922` | 136 | 34.25 Hz |
| **clap** | Participant_01 @ 2.0 m | `...clap_Participant_01_1792394020` | 141 | 35.04 Hz | `...clap_Participant_01_1792397955` | 140 | 34.92 Hz |
| **push_pull** | Participant_01 @ 2.0 m | `...push_pull_Participant_01_1792394048` | 143 | 35.52 Hz | `...push_pull_Participant_01_1792397991` | 137 | 34.02 Hz |

*Physical Observation:* The empirical sampling rates and frame counts between the two physical rooms are closely aligned (Lab mean: 34.93 Hz vs. Office mean: 34.89 Hz), confirming that the ESP32-S3 hardware bridge and UDP stimulation pipeline perform consistently across differing physical multipath environments.

---

## 7. Reconciled Total Dataset Inventory

Every session file in `data/real_csi_dataset/` was audited against `dataset_manifest.json`:

| Metric | Phase 29 Baseline | Phase 30 Addition | Reconciled Total Dataset | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Indexed Sessions** | 64 | +5 | **69** | Verified |
| **Unique Session IDs** | 64 | +5 | **69** | 0 collisions |
| **Unique Event IDs** | 64 | +5 | **69** | 0 collisions |
| **Physical Frames** | 8,997 | +696 | **9,693** | Verified |
| **Valid Windows ($T=50$, stride 50)** | 134 | +10 | **144** | Verified |
| **Frames with Raw 5 Subcarriers** | 5,785 | +696 | **6,481** | Verified |
| **Frames with Derived 56 Channels** | 8,997 | +696 | **9,693** | Verified |
| **Sessions in Laboratory / Lab_Room1** | 64 | 0 | **64** | Verified |
| **Sessions in Office_Room2** | 0 | +5 | **5** | Verified |
| **Sessions at 1.5 m** | 5 | 0 | **5** | Verified |
| **Sessions at 2.0 m** | 25 | +5 | **30** | Verified |
| **Sessions at 2.5 m** | 34 | 0 | **34** | Verified |
| **Manifest Integrity Pass Rate** | 100% (64/64) | 100% (5/5) | **100% (69/69)** | Verified |

---

## 8. Participant-Independent Split Verification

The updated 69-session manifest was processed using `ParticipantIndependentSplitGenerator`:

- **Split Protocol:** Participant-independent train/val/test partition
- **Test Participant:** `Participant_02` (16 sessions, 35 windows: 24 at 2.5 m, 11 at 2.0 m)
- **Validation Participant:** `Participant_05` (10 sessions, 20 windows: 10 at 1.5 m, 10 at 2.0 m)
- **Training Participants:** `Participant_01`, `Participant_03`, `Participant_04` (43 sessions, 89 windows across Laboratory and Office_Room2)
- **Total Windows:** $89 + 20 + 35 = 144\text{ windows}$

### Disjointness & Zero-Leakage Audit
$$\text{Train} \cap \text{Val} = \emptyset, \quad \text{Train} \cap \text{Test} = \emptyset, \quad \text{Val} \cap \text{Test} = \emptyset$$
- Common subjects between any partition: **0**
- Common sessions/events between any partition: **0**
- Window boundary overlap ($T=50$, stride 50): **0**

---

## 9. Regression Test Suite Execution

The full regression test suite across all 17 test files (including [backend/tests/test_phase30.py](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase30.py)) was executed:

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
  backend/tests/test_phase29.py `
  backend/tests/test_phase30.py `
  backend/tests/test_safe_disconnection.py `
  backend/tests/test_sampling_rate_audit.py -v
```

### Execution Summary
- **Exit Code:** `0`
- **Total Tests Run:** `149`
- **Passed:** `149`
- **Failed:** `0`
- **Skipped:** `0`
- **Warnings:** `4` (2 PyTorch nested-tensor encoder warnings, 1 Starlette TestClient deprecation warning)
- **Duration:** `26.21 seconds`

---

## 10. Unresolved Limitations & Research Barriers

1. **Dataset Environmental Coverage vs. Model Generalization Claim:**
   - Although the dataset now contains physical recordings from 2 distinct rooms (`Laboratory` and `Office_Room2`), this phase does **not** prove cross-room model generalization.
   - Proving cross-room generalization requires training exclusively on one room and evaluating on another held-out room under an authorized, safe protocol.
   - **Status:** Generalization claims remain **UNVERIFIED / FROZEN**.
2. **Safety Barrier — Missing Fall Class in Held-Out Subjects:**
   - Participants 03, 04, and 05 have 0 fall events.
   - Full 6-class model evaluation requires held-out fall events, but user-defined safety rules strictly prohibit performing risky movements or conducting physical fall experiments.
   - Synthetic data fabrication is strictly prohibited.
   - **Status:** Full 6-class evaluation remains **BLOCKED (NO-GO)**.

---

## 11. Recommendations for Phase 31

1. **Maintain Checkpoint Protection:** Keep `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth` frozen and untouched.
2. **Consider Cross-Room Ordinary 5-Class Evaluation:** If model evaluation is authorized in Phase 31, evaluate the **5 safe ordinary classes** across rooms (`Laboratory` train vs. `Office_Room2` test) to assess environmental transfer without violating fall safety safeguards.
3. **Public Fall Benchmark Ingestion:** If 6-class evaluation is mandatory, integrate public certified Wi-Fi CSI datasets (e.g. Stanford/Widar/UT-HAR) for fall benchmark comparisons rather than physical human fall trials.
