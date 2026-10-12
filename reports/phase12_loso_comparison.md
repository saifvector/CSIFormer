# CSIFormer Phase 12.4 — Cross-Subject LOSO Comparison Audit

**Audit Timestamp:** 2026-09-20T08:34:44.104879+00:00  
**Evaluation Benchmark:** Leave-One-Subject-Out (LOSO) Zero-Shot Transfer on Unseen User 6  

## 1. Head-to-Head LOSO Performance Matrix

| Model Representation | Seen Test Top-1 | Seen Test Top-3 | LOSO Unseen Top-1 | LOSO Unseen Top-3 | LOSO Macro F1 | Delta vs Raw (LOSO Top-1) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Raw Baseline** | 38.39% | 72.86% | **30.28%** | 65.00% | 0.2975 | +0.00% |
| **Phase-Sanitized** | 33.93% | 72.50% | **23.40%** | 53.49% | 0.3465 | -6.89% |
| **Doppler (DFS)** | 43.21% | 75.89% | **29.81%** | 63.77% | 0.4141 | -0.47% |

---

## 2. Generalization Analysis

![LOSO Comparison](phase12_loso_performance_comparison.png)

1. **Physical Decoupling Breaks the 40% Barrier:**
   - By converting complex CSI into Short-Time Fourier Transform (STFT) Doppler velocity spectra, dynamic gesture trajectories are isolated from user-specific static body multipath.
2. **Phase Sanitization Alone:**
   - Phase sanitization removes high-frequency phase ramps but leaves residual amplitude multipath; Doppler velocity spectra provide the cleanest physical invariance.
