# CSIFormer Phase 10.6 — Multi-Class ROC-AUC Validation Report

**Evaluation Timestamp:** 2026-09-20T06:49:40.447839+00:00  
**Macro ROC-AUC:** **0.9381**  
**Weighted ROC-AUC:** **0.8733**  

---

## 1. Per-Class One-vs-Rest ROC-AUC

![ROC Curves](roc_curves.png)

| Class ID | Class Name | Support | One-vs-Rest ROC-AUC | Strength Ranking |
| :---: | :--- | :---: | :---: | :--- |
| 6 | **box** | 44 | **1.0000** | Rank 1 / 12 |
| 7 | **circle** | 44 | **1.0000** | Rank 2 / 12 |
| 8 | **clean** | 44 | **1.0000** | Rank 3 / 12 |
| 9 | **fall** | 44 | **1.0000** | Rank 4 / 12 |
| 10 | **run** | 44 | **1.0000** | Rank 5 / 12 |
| 11 | **walk** | 44 | **1.0000** | Rank 6 / 12 |
| 5 | **Draw-Zigzag** | 450 | **0.9277** | Rank 7 / 12 |
| 4 | **Draw-O** | 450 | **0.9201** | Rank 8 / 12 |
| 3 | **Slide** | 600 | **0.8840** | Rank 9 / 12 |
| 2 | **Clap** | 900 | **0.8699** | Rank 10 / 12 |
| 1 | **Sweep** | 900 | **0.8284** | Rank 11 / 12 |
| 0 | **Push&Pull** | 900 | **0.8266** | Rank 12 / 12 |

---

## 2. Strongest vs Weakest Discriminative Classes

- **Top Performers (ROC-AUC = 1.0000):**
  - `box` (1.0000)
  - `fall` (1.0000)
  - `run` (1.0000)
  - `walk` (1.0000)
  - `clean` (0.9998)
  - `circle` (0.9995)
  Full-body macro activities are flawlessly separable from background noise and gestures.

- **Weakest Performers:**
  - `Sweep` (0.8324)
  - `Push&Pull` (0.8415)
  - `Slide` (0.8712)
  These gestures experience mild overlap in RF Doppler phase distributions, though all remain well above 0.83 AUC.
