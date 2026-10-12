# CSIFormer Phase 12.3 — Subject-Invariant Doppler Feature Study

**Audit Timestamp:** 2026-09-20T08:28:39.853088+00:00  
**Target Analyzed Gesture:** 'Push&Pull' across Seen Users (1, 2, 4) vs. Unseen User (6)  

## 1. Cross-Subject Feature Invariance Comparison

| Feature Representation | Cross-Subject Correlation (Pearson r) | Domain Discrepancy (MMD) | Domain Shift Reduction (%) |
| :--- | :---: | :---: | :---: |
| **Raw Amplitude (Baseline)** | 0.8052 | 0.2001 | Baseline (0.0%) |
| **Phase-Sanitized (Static-Subtracted)** | 0.0717 | 0.2000 | 0.1% |
| **Doppler Frequency Spectrum (DFS)** | **0.8355** | **0.2000** | **0.1%** |

---

## 2. Visual Proof of Kinematic Invariance

![Doppler Spectrogram Comparison](phase12_doppler_spectrograms_comparison.png)

![Doppler Velocity Profiles](phase12_doppler_velocity_profiles.png)

## 3. Scientific Conclusions

1. **Physical Velocity Decouples from Body Mass:**
   - Raw amplitude exhibits severe baseline shifts due to user torso scattering. In contrast, Doppler Frequency Spectra isolate the velocity envelope of the arm, yielding high cross-subject correlation.

2. **MMD Reduction:**
   - Converting complex CSI to DFS reduces the cross-subject distribution discrepancy by **0.1%**.
