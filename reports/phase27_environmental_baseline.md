# CSIFormer Phase 27 — Environmental Coverage Baseline Report

**Audit Date:** October 19, 2026  
**Auditor:** Antigravity Autonomous Agent  
**Repository Root:** `C:\Users\saifu\Desktop\4-1 project`  
**Dataset Directory:** `data/real_csi_dataset/`  
**Manifest Path:** `data/real_csi_dataset/dataset_manifest.json`  

---

## 1. Executive Summary & Baseline Inventory

| Audit Dimension | Verified Baseline Value | Evidentiary Basis |
| :--- | :---: | :--- |
| **Total Indexed Sessions** | **39** | Verified in `dataset_manifest.json` |
| **Total Physical Frames** | **5,472** | Direct sum of `frames` arrays across all 39 session JSON files |
| **Total Validated Windows ($T=50$)** | **82** | Non-overlapping window extraction on verified 56-channel frames |
| **Distinct Participants** | **5** | `Participant_01`, `Participant_02`, `Participant_03`, `Participant_04`, `Participant_05` |
| **Distinct Environmental Settings** | **2 Physical Distances** | $2.5\text{ m}$ (29 sessions) and $2.0\text{ m}$ (10 sessions) |
| **Distinct Room Designations** | **2 Labels / 1 Facility** | `Laboratory_Room1` (23 sessions), `Laboratory` (16 sessions) |
| **Mean Empirical Sampling Rate** | **35.48 Hz** | Standardized mathematical calculation: $(N-1)/(t_{\text{last}} - t_{\text{first}})$ |
| **Packet Loss Rate** | **0.00%** | Sequence continuity check: $\sum \max(0, \Delta\text{seq} - 1) = 0$ |
| **Validation Pass Rate** | **100.0% (39/39)** | All sessions pass `DatasetIntegrityValidator` quality gates |
| **Production Checkpoint Hash** | `383b4d98c08f8970b0443738f170ec01` | MD5 of `models/csiformer_phase13_best.pth` (**MATCH**) |
| **Experimental Checkpoint Hash** | `ab3d97a04d78edf75d807178772bc828` | MD5 of `models/csiformer_phase15_adapted.pth` (**MATCH**) |

---

## 2. Environmental Coverage Breakdown

| Environment Key | Room Name | Tx-Rx Distance | Sessions | Packets | Windows ($T=50$) | Participants | Mean Sampling Rate | Mean Loss |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| **Env 1** | `Laboratory_Room1` | 2.5 m | 23 | 3,212 | 49 | Participant_01, Participant_02 | 35.51 Hz | 0.00% |
| **Env 2** | `Laboratory` | 2.5 m | 6 | 861 | 13 | Participant_03 | 35.83 Hz | 0.00% |
| **Env 3** | `Laboratory` | 2.0 m | 10 | 1,399 | 20 | Participant_04, Participant_05 | 34.91 Hz | 0.00% |
| **Total** | — | — | **39** | **5,472** | **82** | **5 Participants** | **35.48 Hz** | **0.00%** |

---

## 3. Comprehensive Session-by-Session Environmental Audit

Every indexed session was verified against its physical JSON and CSV data files:

| Session ID | Part | Activity | Room | Dist | Dur(s) | Frames | Wins | Rate (Hz) | Loss | Valid |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `p15_real_walk_t1_1792303867` | P01 | `walk` | `Laboratory_Room1` | 2.5m | 4.00 | 146 | 2 | 36.23 | 0.0% | **True** |
| `p15_real_walk_t2_1792303871` | P02 | `walk` | `Laboratory_Room1` | 2.5m | 4.00 | 155 | 3 | 38.40 | 0.0% | **True** |
| `p15_real_walk_t3_1792303876` | P01 | `walk` | `Laboratory_Room1` | 2.5m | 4.00 | 148 | 2 | 36.36 | 0.0% | **True** |
| `p15_real_walk_t4_1792303880` | P02 | `walk` | `Laboratory_Room1` | 2.5m | 4.00 | 141 | 2 | 34.97 | 0.0% | **True** |
| `p15_real_fall_t1_1792303885` | P01 | `fall` | `Laboratory_Room1` | 2.5m | 4.00 | 135 | 2 | 33.40 | 0.0% | **True** |
| `p15_real_fall_t2_1792303889` | P02 | `fall` | `Laboratory_Room1` | 2.5m | 4.00 | 136 | 2 | 33.50 | 0.0% | **True** |
| `p15_real_fall_t3_1792303894` | P01 | `fall` | `Laboratory_Room1` | 2.5m | 4.00 | 145 | 2 | 36.59 | 0.0% | **True** |
| `p15_real_fall_t4_1792303899` | P02 | `fall` | `Laboratory_Room1` | 2.5m | 4.00 | 145 | 2 | 35.30 | 0.0% | **True** |
| `p15_real_sit_t1_1792303903` | P01 | `sit` | `Laboratory_Room1` | 2.5m | 4.00 | 136 | 2 | 33.75 | 0.0% | **True** |
| `p15_real_sit_t2_1792303908` | P02 | `sit` | `Laboratory_Room1` | 2.5m | 4.00 | 150 | 3 | 36.98 | 0.0% | **True** |
| `p15_real_sit_t3_1792303913` | P01 | `sit` | `Laboratory_Room1` | 2.5m | 4.00 | 149 | 2 | 36.34 | 0.0% | **True** |
| `p15_real_sit_t4_1792303917` | P02 | `sit` | `Laboratory_Room1` | 2.5m | 4.00 | 160 | 3 | 39.14 | 0.0% | **True** |
| `p15_real_clap_t1_1792303922` | P01 | `clap` | `Laboratory_Room1` | 2.5m | 4.00 | 140 | 2 | 34.70 | 0.0% | **True** |
| `p15_real_clap_t2_1792303926` | P02 | `clap` | `Laboratory_Room1` | 2.5m | 4.00 | 142 | 2 | 34.63 | 0.0% | **True** |
| `p15_real_clap_t3_1792303931` | P01 | `clap` | `Laboratory_Room1` | 2.5m | 4.00 | 149 | 2 | 36.20 | 0.0% | **True** |
| `p15_real_clap_t4_1792303936` | P02 | `clap` | `Laboratory_Room1` | 2.5m | 4.00 | 148 | 2 | 36.73 | 0.0% | **True** |
| `p15_real_push_pull_t1_1792303940` | P01 | `push_pull` | `Laboratory_Room1` | 2.5m | 4.00 | 156 | 3 | 38.70 | 0.0% | **True** |
| `p15_real_push_pull_t2_1792303945` | P02 | `push_pull` | `Laboratory_Room1` | 2.5m | 4.00 | 142 | 2 | 35.66 | 0.0% | **True** |
| `p15_real_push_pull_t3_1792303950` | P01 | `push_pull` | `Laboratory_Room1` | 2.5m | 4.00 | 140 | 2 | 34.66 | 0.0% | **True** |
| `p15_real_push_pull_t4_1792303954` | P02 | `push_pull` | `Laboratory_Room1` | 2.5m | 4.00 | 140 | 2 | 34.44 | 0.0% | **True** |
| `p15_real_static_t1_1792303959` | P01 | `static` | `Laboratory_Room1` | 2.5m | 3.00 | 100 | 2 | 32.67 | 0.0% | **True** |
| `p15_real_static_t2_1792303963` | P02 | `static` | `Laboratory_Room1` | 2.5m | 3.00 | 98 | 1 | 31.77 | 0.0% | **True** |
| `p15_real_static_t3_1792303966` | P01 | `static` | `Laboratory_Room1` | 2.5m | 3.00 | 111 | 2 | 35.51 | 0.0% | **True** |
| `phase16_real_walk_P03_1792339078` | P03 | `walk` | `Laboratory` | 2.5m | 4.02 | 143 | 2 | 35.70 | 0.0% | **True** |
| `phase16_real_static_P03_1792388605` | P03 | `static` | `Laboratory` | 2.5m | 4.02 | 141 | 2 | 35.25 | 0.0% | **True** |
| `phase16_real_sit_P03_1792388631` | P03 | `sit` | `Laboratory` | 2.5m | 4.02 | 152 | 3 | 38.04 | 0.0% | **True** |
| `phase16_real_walk_P03_1792388657` | P03 | `walk` | `Laboratory` | 2.5m | 4.02 | 139 | 2 | 34.74 | 0.0% | **True** |
| `phase16_real_clap_P03_1792388686` | P03 | `clap` | `Laboratory` | 2.5m | 4.02 | 145 | 2 | 36.25 | 0.0% | **True** |
| `phase16_real_push_pull_P03_1792388712` | P03 | `push_pull` | `Laboratory` | 2.5m | 4.04 | 141 | 2 | 34.98 | 0.0% | **True** |
| `phase16_real_static_P04_1792389853` | P04 | `static` | `Laboratory` | 2.0m | 4.02 | 144 | 2 | 36.00 | 0.0% | **True** |
| `phase16_real_sit_P04_1792389881` | P04 | `sit` | `Laboratory` | 2.0m | 4.04 | 137 | 2 | 34.01 | 0.0% | **True** |
| `phase16_real_walk_P04_1792389907` | P04 | `walk` | `Laboratory` | 2.0m | 4.01 | 142 | 2 | 35.53 | 0.0% | **True** |
| `phase16_real_clap_P04_1792389936` | P04 | `clap` | `Laboratory` | 2.0m | 4.04 | 139 | 2 | 34.51 | 0.0% | **True** |
| `phase16_real_push_pull_P04_1792389966` | P04 | `push_pull` | `Laboratory` | 2.0m | 4.04 | 142 | 2 | 35.26 | 0.0% | **True** |
| `phase16_real_static_P05_1792390995` | P05 | `static` | `Laboratory` | 2.0m | 4.04 | 137 | 2 | 34.06 | 0.0% | **True** |
| `phase16_real_sit_P05_1792391028` | P05 | `sit` | `Laboratory` | 2.0m | 4.03 | 138 | 2 | 34.26 | 0.0% | **True** |
| `phase16_real_walk_P05_1792391056` | P05 | `walk` | `Laboratory` | 2.0m | 4.03 | 141 | 2 | 35.03 | 0.0% | **True** |
| `phase16_real_clap_P05_1792391082` | P05 | `clap` | `Laboratory` | 2.0m | 3.89 | 135 | 2 | 34.71 | 0.0% | **True** |
| `phase16_real_push_pull_P05_1792391109` | P05 | `push_pull` | `Laboratory` | 2.0m | 4.03 | 144 | 2 | 35.76 | 0.0% | **True** |

---

## 4. Key Environmental Gaps Identified

1. **Distance Range Restriction:** The dataset only spans two closely spaced distances: $2.0\text{ m}$ and $2.5\text{ m}$. No shorter range ($1.5\text{ m}$) or longer range ($3.0\text{ m}$) data currently exists.
2. **Room / Facility Homogeneity:** All 39 sessions were captured within the primary laboratory facility (`Laboratory` / `Laboratory_Room1`). Testing an alternative physical space (e.g. an Office, Corridor, or Meeting Room) or a distinct physical transmitter-receiver geometry is needed to evaluate pipeline robustness under varied multi-path profiles.
3. **Subject-Geometry Coupling:** `Participant_01` and `Participant_02` were exclusively recorded at $2.5\text{ m}$, whereas `Participant_04` and `Participant_05` were exclusively recorded at $2.0\text{ m}$. Recording a participant across multiple distinct distances would decouple participant-specific RF signatures from geometric multipath signatures.
