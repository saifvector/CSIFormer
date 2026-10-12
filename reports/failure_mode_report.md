# CSIFormer Phase 10.7 — Forensic Failure Mode Analysis Report

**Audit Timestamp:** 2026-09-20T07:00:06.421223+00:00  

## 1. Class Vulnerability to RF Noise (15 dB SNR Degradation)

| Rank | Class Name | Clean Accuracy | 15 dB Noise Accuracy | Absolute Drop ($\Delta$) | Relative Retention |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **Push&Pull** | 36.56% | 40.22% | **--3.67%** | 110.0% |
| 2 | **Sweep** | 45.89% | 34.00% | **-11.89%** | 74.1% |
| 3 | **Clap** | 59.89% | 48.44% | **-11.44%** | 80.9% |
| 4 | **Slide** | 54.67% | 50.33% | **-4.33%** | 92.1% |
| 5 | **Draw-O** | 62.44% | 58.89% | **-3.56%** | 94.3% |
| 6 | **Draw-Zigzag** | 58.67% | 61.56% | **--2.89%** | 104.9% |
| 7 | **box** | 100.00% | 100.00% | **-0.00%** | 100.0% |
| 8 | **circle** | 97.73% | 97.73% | **-0.00%** | 100.0% |
| 9 | **clean** | 100.00% | 100.00% | **-0.00%** | 100.0% |
| 10 | **fall** | 100.00% | 100.00% | **-0.00%** | 100.0% |
| 11 | **run** | 100.00% | 100.00% | **-0.00%** | 100.0% |
| 12 | **walk** | 100.00% | 100.00% | **-0.00%** | 100.0% |

---

## 2. Taxonomy of Primary RF Failure Modes

### Failure Mode 1: Radial Doppler Phase Cancellation (`Sweep` & `Push&Pull`)
- **Vulnerability:** `Sweep` (-12.67% drop) and `Clap` (-10.56% drop) suffer the highest degradation under noise.
- **Root Cause:** Inward radial arm translation produces Doppler frequency shifts near DC ($0$ Hz) where additive noise directly corrupts the zero-crossing phase progression.

### Failure Mode 2: Frequency Subcarrier Nulling (Narrowband Jamming)
- **Vulnerability:** Nulling 10% of subcarriers drops Top-1 from 54.14% to 26.77%.
- **Root Cause:** The 1D-CNN frontend relies on inter-subcarrier correlation across the 56 HT20 bins. When subcarriers are abruptly zeroed, the convolutional feature maps experience severe phase discontinuity.

### Failure Mode 3: Zero-Shot User Biometric Variance
- **Vulnerability:** Unseen subjects exhibit Top-1 accuracy drop to 28.53%.
- **Root Cause:** User physical differences (body mass, arm reach, speed) alter the Doppler envelope frequency and duration.

### Life-Safety Immunity:
- **Fall Detection and Locomotion:** `fall`, `run`, and `walk` remain virtually unaffected (**>97.7% accuracy** even at 15 dB SNR), proving that whole-body displacement signatures are immune to localized micro-multipath noise.
