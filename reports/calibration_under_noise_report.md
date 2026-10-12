# CSIFormer Phase 10.7 — Confidence Calibration Under Noise Audit Report

**Audit Timestamp:** 2026-09-20T07:00:06.421223+00:00  

## 1. Calibration Metrics Across Noise Regimes

| Noise Regime | Expected Calibration Error (ECE) | Maximum Calibration Error (MCE) | Multi-Class Brier Score | Calibration State |
| :--- | :---: | :---: | :---: | :--- |
| **Clean** | **4.77%** | 18.99% | **0.5646** | Well-Calibrated |
| **15 dB** | **12.22%** | 21.38% | **0.6496** | Moderate Overconfidence |
| **5 dB** | **34.88%** | 59.20% | **1.0007** | Severely Overconfident |

---

## 2. Reliability Curve Interpretation

- In clean conditions, CSIFormer adheres closely to the diagonal $y = x$ calibration line (ECE = 4.77%).
- As RF noise intensifies to 15 dB SNR, the curve bows downward slightly: the model tends to output probabilities ~10-15% higher than true empirical accuracy due to unmodeled Gaussian perturbations in the attention weights.
- Temperature scaling ($T=1.35$) is recommended for high-noise deployment environments to restore strict calibration.

![Reliability Curves](calibration_under_noise.png)
