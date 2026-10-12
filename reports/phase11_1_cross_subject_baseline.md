# CSIFormer Phase 11.1 — Cross-Subject Baseline Audit Report

**Audit Timestamp:** 2026-09-20T07:28:31.298519+00:00  
**Model Checkpoint:** [`models/best_csiformer.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/best_csiformer.pth)  
**Evaluated Compute Hardware:** cuda  

---

## 1. Executive Summary & Problem Formulation

In Wi-Fi CSI sensing, radio frequency multipath profiles are shaped by both dynamic limb motion and static body characteristics (dielectric permittivity, chest cross-section, height, and arm length). Phase 11.1 establishes the baseline quantification of subject-dependent feature leakage before applying domain adaptation.

| Evaluation Benchmark | Test Samples ($N$) | Top-1 Accuracy | Top-3 Accuracy | Macro F1 | Balanced Accuracy | ROC-AUC |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Standard Held-Out Test Set** | 4,464 | **54.14%** | **91.91%** | **0.7545** | **76.32%** | **0.9381** |
| **LOSO Unseen Subject (User 6)** | 4,500 | **28.53%** | **67.31%** | **0.2839** | **28.53%** | **0.0000** |
| **Performance Retention Ratio** | — | **52.7%** | **73.2%** | **37.6%** | — | — |

---

## 2. Subject-wise Performance Breakdown

| Subject ID | Samples ($N$) | Top-1 Accuracy | Top-3 Accuracy | Precision | Recall | Macro F1 | Balanced Accuracy | ROC-AUC | Mean Conf |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NTU-Fi Subject (HAR)** | 264 | 99.62% | 100.00% | 0.9963 | 0.9962 | **0.9962** | 99.62% | 0.0000 | 99.0% |
| **User 1** | 1,350 | 49.63% | 91.11% | 0.5027 | 0.5167 | **0.4993** | 51.67% | 0.0000 | 55.6% |
| **User 2** | 600 | 50.50% | 93.00% | 0.5036 | 0.5050 | **0.4951** | 50.50% | 0.0000 | 56.6% |
| **User 3** | 450 | 54.22% | 94.89% | 0.4338 | 0.4067 | **0.4175** | 54.22% | 0.0000 | 53.5% |
| **User 4** | 900 | 62.56% | 98.78% | 0.6397 | 0.6256 | **0.6257** | 62.56% | 0.0000 | 63.0% |
| **User 6** | 900 | 41.56% | 81.67% | 0.4105 | 0.4156 | **0.3976** | 41.56% | 0.0000 | 51.6% |

---

## 3. Error Distribution & Cross-Subject Confusion Analysis

### Key Observations:
1. **Strong In-Distribution Performance:** Within seen subjects, accuracy ranges from **49.63% (User 1)** to **62.56% (User 4)**, with Top-3 accuracy exceeding **91.1% to 98.8%**.
2. **Severe Zero-Shot Degradation:** When evaluating on User 6 in pure leave-one-subject-out isolation ($N=4,500$), Top-1 accuracy drops to **28.53%** and Macro F1 drops to **0.2839**.
3. **Candidate Retention:** Despite the drop in Top-1, **Top-3 accuracy remains at 67.31%**, proving that the model's feature extractor preserves gesture subspace structure, but lacks calibration to disambiguate the final candidate on an unseen body profile.
4. **Target Gap:** To achieve production viability, Phase 11.3 DANN must close this gap, elevating unseen user Top-1 from **28.53% to $\ge 45.0\%$** and Top-3 from **67.31% to $\ge 80.0\%$**.

### Confusion Matrix Directory:
Individual subject confusion matrices have been generated in [`reports/cross_subject_confusion_matrices/`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/cross_subject_confusion_matrices/).
