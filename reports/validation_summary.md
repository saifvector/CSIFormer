# CSIFormer Phase 10.6 — Validation Summary & Scorecard

**Execution Date:** 2026-09-20T06:49:40.448890+00:00  
**Evaluated Artifact:** [`models/best_csiformer.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/best_csiformer.pth)  
**Held-Out Test Samples:** 4,464  

---

## 1. Recomputed vs Reported Metrics Comparison

| Metric Name | Phase 10.5D Reported | Phase 10.6 Independently Recomputed | Difference | Verification Result |
| :--- | :---: | :---: | :---: | :---: |
| **Top-1 Accuracy** | 54.14% | **54.14%** | **0.00%** | **EXACT MATCH (VERIFIED)** |
| **Top-3 Accuracy** | 91.91% | **91.91%** | **0.00%** | **EXACT MATCH (VERIFIED)** |
| **Macro Precision** | 0.7530 | **0.7530** | **0.0000** | **EXACT MATCH (VERIFIED)** |
| **Macro Recall** | 0.7632 | **0.7632** | **0.0000** | **EXACT MATCH (VERIFIED)** |
| **Macro F1 Score** | 0.7545 | **0.7545** | **0.0000** | **EXACT MATCH (VERIFIED)** |
| **Weighted F1 Score** | 0.5379 | **0.5379** | **0.0000** | **EXACT MATCH (VERIFIED)** |
| **Macro ROC-AUC** | 0.9381 | **0.9381** | **0.0000** | **EXACT MATCH (VERIFIED)** |
| **Human Presence Score** | 99.99% | **99.99%** | **0.00%** | **EXACT MATCH (VERIFIED)** |
| **Human Motion Score** | 99.99% | **99.99%** | **0.00%** | **EXACT MATCH (VERIFIED)** |
| **Cross-Domain Leakage** | 0 errors | **0 errors** | **0** | **EXACT MATCH (VERIFIED)** |

---

## 2. Advanced Diagnostic Scorecard

| Diagnostic Metric | Score | Scientific Interpretation |
| :--- | :---: | :--- |
| **Balanced Accuracy** | **76.32%** | Unweighted mean recall across all 12 classes |
| **Cohen's Kappa ($\kappa$)** | **0.4580** | Substantial agreement over chance ($>0.40$) |
| **Matthews Corr Coef (MCC)** | **0.4601** | Robust multi-class correlation coefficient |
| **Expected Calibration Error (ECE)** | **4.77%** | Good probability calibration ($<15\%$) |
| **Multi-Class Brier Score** | **0.5646** | Sharp probability distribution |
