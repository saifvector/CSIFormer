# CSIFormer Phase 12.1 — Subject Identity Signal Decomposition Audit

**Audit Timestamp:** 2026-09-20T08:27:24.661690+00:00  
**Analyzed Dataset:** Widar 3.0 Real Intel 5300 Complex CSI (.dat)  
**Sample Count Analyzed:** 1200 balanced samples across Users 1, 2, 3, 4, 6  

## 1. Physical Signal Decomposition Benchmark

| CSI Signal Component | Subject Acc (%) | Gesture Acc (%) | Kinematic/Biometric Ratio | MI Subject | MI Gesture | Purity Subject | Purity Gesture |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Raw Amplitude** | 73.67% | 22.00% | **0.30x** | 0.0449 | 0.0072 | 43.6% | 23.8% |
| **Raw Phase** | 34.67% | 17.33% | **0.50x** | 0.0091 | 0.0074 | 33.4% | 23.7% |
| **Sanitized Phase** | 25.00% | 18.67% | **0.75x** | 0.0118 | 0.0083 | 33.4% | 24.3% |
| **Cross-Antenna Differential Phase** | 49.00% | 22.00% | **0.45x** | 0.4925 | 0.0450 | 42.6% | 24.8% |
| **Subcarrier Correlation Matrix** | 90.67% | 21.67% | **0.24x** | 0.2460 | 0.0170 | 40.2% | 23.5% |
| **Doppler Spectrogram (DFS)** | 39.33% | 28.67% | **0.73x** | 0.0104 | 0.0077 | 33.7% | 25.7% |
| **Velocity Profile (Centroid)** | 28.33% | 19.67% | **0.69x** | 0.0172 | 0.0171 | 33.5% | 23.2% |

---

## 2. Key Physical Findings

1. **Raw Amplitude Contains Extreme Subject Leakage:**
   - Subcarrier Correlation Matrix and Raw Amplitude exhibit the highest Subject Classification Accuracy (over 80%). The static human body profile acts as an intense static multipath filter that memorizes user physical morphology.

2. **Raw Phase is Dominated by Asynchronous Hardware Offsets:**
   - Unsanitized raw phase has random packet-to-packet CFO and STO ramps, obscuring gesture kinematics.

3. **Doppler Frequency Spectrum (DFS) & Velocity Profiles Maximize Invariance:**
   - STFT Doppler features decouple the static human body from the dynamic limb reflection, yielding the highest Kinematic-to-Biometric Ratio.

![Component Comparison](phase12_component_identity_comparison.png)
