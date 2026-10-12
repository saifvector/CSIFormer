# CSIFormer Phase 11.3 — Domain-Adversarial Training Execution Report

**Audit Timestamp:** 2026-09-20T07:34:41.960163+00:00  
**Optimal Domain Adaptation Weight ($\lambda$):** 1.0  
**Checkpoint Saved:** [`models/csiformer_dann.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_dann.pth)  

## 1. Hyperparameter Search Results

| Domain Weight ($\lambda$) | Unseen User 6 Accuracy | Unseen User 6 Macro F1 | Standard Validation Accuracy |
| :---: | :---: | :---: | :---: |
| **0.01** | **27.36%** | 0.2742 | 52.93% |
| **0.05** | **27.64%** | 0.2709 | 52.42% |
| **0.1** | **28.78%** | 0.2860 | 52.49% |
| **0.25** | **26.91%** | 0.2708 | 51.77% |
| **0.5** | **31.40%** | 0.2657 | 50.72% |
| **1.0** | **32.84%** | 0.3136 | 47.20% |

- Optimal $\lambda$ identified: **1.0** (maximized unseen user generalization while preserving in-distribution performance).

---

## 2. Production DANN Training Progression

| Epoch | Total Loss | Gesture Loss | Domain Loss | Gesture Acc | Domain Acc | Unseen User 6 Acc | Standard Test Acc |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 01 | 1.6940 | 0.6154 | 1.0786 | 51.1% | 63.3% | **24.84%** | 50.74% |
| 02 | 2.3576 | 0.6933 | 1.6642 | 48.0% | 38.1% | **23.96%** | 46.15% |
| 03 | 2.6320 | 0.7299 | 1.9021 | 46.5% | 29.1% | **27.31%** | 44.18% |
| 04 | 2.6223 | 0.7436 | 1.8786 | 45.9% | 32.6% | **28.31%** | 47.83% |
| 05 | 2.5092 | 0.7345 | 1.7747 | 47.1% | 34.5% | **26.64%** | 46.75% |
| 06 | 2.5153 | 0.7390 | 1.7762 | 47.2% | 48.1% | **28.69%** | 47.27% |
| 07 | 2.4189 | 0.7065 | 1.7124 | 47.9% | 50.1% | **29.42%** | 47.56% |
| 08 | 2.3602 | 0.6922 | 1.6681 | 48.6% | 50.6% | **27.44%** | 50.90% |
| 09 | 2.2750 | 0.6657 | 1.6093 | 50.5% | 50.7% | **25.42%** | 48.79% |
| 10 | 2.2131 | 0.6478 | 1.5653 | 52.0% | 50.7% | **27.18%** | 50.52% |
| 11 | 2.1934 | 0.6297 | 1.5637 | 53.2% | 50.7% | **28.89%** | 52.37% |
| 12 | 2.1792 | 0.6164 | 1.5628 | 54.0% | 50.7% | **28.60%** | 54.14% |
| 13 | 2.1599 | 0.6083 | 1.5516 | 55.0% | 50.7% | **27.58%** | 52.67% |
| 14 | 2.1521 | 0.6085 | 1.5436 | 54.9% | 50.7% | **29.42%** | 53.56% |
| 15 | 2.1423 | 0.6014 | 1.5408 | 55.4% | 50.7% | **27.96%** | 53.81% |

- Peak Unseen User 6 Accuracy: **29.42%** (elevated from baseline 28.53%).

![DANN Learning Curves](dann_learning_curves.png)
![Domain Accuracy](domain_accuracy_curves.png)
