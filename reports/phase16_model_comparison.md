# CSIFormer Phase 16 — Fair Baseline & Adaptation Model Comparison

**Comparison Scope:** Head-to-Head Evaluation of Phase 13 Production Checkpoint vs. Phase 15 Experimental Adapted Checkpoint  
**Evaluation Dates:** October 18, 2026  
**Evaluator:** Principal Wireless Sensing Research Scientist & Lead Agent  
**Checkpoints Audited:**
- **Production Baseline:** `models/csiformer_phase13_best.pth` (MD5: `383b4d98c08f8970b0443738f170ec01`)
- **Experimental Adapted:** `models/csiformer_phase15_adapted.pth` (MD5: `ab3d97a04d78edf75d807178772bc828`)

---

## 1. Executive Summary & Core Comparison

This report presents a controlled, fair head-to-head evaluation of both model checkpoints on the exact same real-world hardware CSI recordings.

```
========================================================================================
                      HELD-OUT TEST SPLIT COMPARISON (N = 11 Windows)
========================================================================================
Metric                   | Phase 13 (Baseline) | Phase 13 (Calibrated) | Phase 15 (Adapted)
-------------------------+---------------------+-----------------------+----------------
Overall Accuracy         |        27.27%       |        27.27%         |      18.18%
Balanced Accuracy        |        25.00%       |        25.00%         |      18.33%
Macro F1-Score           |        0.1689       |        0.2061         |      0.2000
Fall Recall (Sensitivity)|   0.00% (0/2 falls) |   0.00% (0/2 falls)   |  50.00% (1/2 falls)
Fall Specificity         |       100.00%       |       100.00%         |      88.89%
Fall Precision           |         0.00%       |         0.00%         |      50.00%
Fall F1-Score            |        0.0000       |        0.0000         |      0.5000
Fall 95% Wilson CI       |     [0.0%, 65.8%]   |     [0.0%, 65.8%]     |  [9.5%, 90.5%]
False Alarms (FP)        |       0 alarms      |       0 alarms        |     1 alarm
Missed Falls (FN)        |       2 missed      |       2 missed        |     1 missed
========================================================================================
```

---

## 2. Life-Safety Fall Detection Analysis

### 2.1 Confusion Contingency Table (Fall vs. Non-Fall) on Held-Out Test Set:

#### Phase 13 Production Baseline:
```
                 Predicted FALL    Predicted Non-Fall    Total
Actual FALL             0 (TP)            2 (FN)           2
Actual Non-Fall         0 (FP)            9 (TN)           9
Total                   0                11               11
```
- **Missed Falls:** 2 out of 2 ($100\%$ missed!).
- **False Alarms:** 0 out of 9 ($0\%$ false alarms).

#### Phase 15 Experimental Adapted Model:
```
                 Predicted FALL    Predicted Non-Fall    Total
Actual FALL             1 (TP)            1 (FN)           2
Actual Non-Fall         1 (FP)            8 (TN)           9
Total                   2                 9               11
```
- **Missed Falls:** 1 out of 2 ($50\%$ missed).
- **False Alarms:** 1 false alarm (`sit` misclassified as `fall`).

### 2.2 Statistical Confidence & Sample Size Limitation
With only $N = 2$ fall windows in the held-out test split:
- **Baseline Recall:** $0.00\%$, with 95% Wilson CI $[0.00\%, 65.79\%]$.
- **Adapted Recall:** $50.00\%$, with 95% Wilson CI $[9.45\%, 90.55\%]$.

**Scientific Judgment:**
The confidence interval $[9.5\%, 90.5\%]$ spans almost the entire probability spectrum. While detecting 1 real hardware fall is a clear positive sign that the fine-tuned dual-branch attention learned transient fall energy, **it is impossible to state with statistical confidence that the adapted model achieves reliable fall detection**. As proven in the Phase 16 collection protocol, achieving $\pm 10\%$ confidence intervals on a $90\%$ sensitive system mathematically requires **at least 35 independent fall test windows**.

---

## 3. Full Dataset Evaluation (N = 49 Windows Across All Splits)

Evaluating across all 49 physical windows provides a broader perspective on general multi-class feature extraction:

| Metric | Phase 13 Production Baseline | Phase 15 Adapted Checkpoint | Delta ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **Overall Accuracy** | 14.29% (7/49) | **30.61% (15/49)** | **+16.32%** |
| **Balanced Accuracy** | 15.00% | **29.72%** | **+14.72%** |
| **Macro F1-Score** | 0.1342 | **0.2858** | **+0.1516** |
| **Fall Recall (N=8 falls)** | 0.00% (0/8) | **62.50% (5/8)** | **+62.50%** |
| **Fall False Positives (FP)** | **0 alarms** | 4 alarms | +4 alarms |
| **Fall Precision** | 0.00% | 55.56% | +55.56% |
| **Fall F1-Score** | 0.0000 | **0.5882** | **+0.5882** |

Across all 49 physical windows, the adapted checkpoint demonstrated strong training and validation fitting, correctly capturing **5 out of 8 falls** ($62.50\%$) compared to the baseline's **0 out of 8** ($0.00\%$). However, on unseen held-out test windows, the overall accuracy dropped to 18.18%, demonstrating classic low-data overfitting.

---

## 4. Participant Breakdown

The evaluation broken down by participant reveals the impact of participant leakage:

### Test Split (All `Participant_02`):
- `Participant_02` Test Windows: 11
- Phase 13 Baseline Accuracy: 27.27% (3/11)
- Phase 15 Adapted Accuracy: 18.18% (2/11)
- Phase 15 Fall Recall: 50.00% (1/2)

### Full Dataset (`Participant_01` vs. `Participant_02`):
- `Participant_01` (25 windows):
  - Phase 13 Accuracy: 16.00% (4/25) | Fall Recall: 0.00% (0/4)
  - Phase 15 Accuracy: **40.00% (10/25)** | Fall Recall: **75.00% (3/4)**
- `Participant_02` (24 windows):
  - Phase 13 Accuracy: 12.50% (3/24) | Fall Recall: 0.00% (0/4)
  - Phase 15 Accuracy: **20.83% (5/24)** | Fall Recall: **50.00% (2/4)**

Notice that `Participant_01` (who contributed 13 windows to Train and 12 to Val, but 0 to Test) achieved 40% accuracy and 75% fall recall under the adapted model, while `Participant_02` (who was in Test) achieved only 20.83% accuracy. This indicates that the model learned subject-specific features rather than fully invariant RF representations.

---

## 5. Visual Artifacts

The side-by-side confusion matrices for both models on the held-out test set are displayed below:

![Confusion Matrices](file:///C:/Users/saifu/.gemini/antigravity-ide/brain/083e1e55-965f-4ffe-ae19-2dc1f8efd037/phase16_comparison_confusion_matrices.png)

*Figure 1: Confusion matrices comparing Phase 13 Production Baseline (left) vs. Phase 15 Adapted Checkpoint (right) on the held-out test split.*

---

## 6. Stage 6 Decision: Is Further Adaptation Justified Now?

### Scientific Assessment:
1. **Model Capacity vs. Data Volume Mismatch:**  
   `CSIDualBranchFusionNet` possesses **1,189,457 trainable parameters**. The current training split provides only **26 windows** ($\sim 4$ windows per class). Retraining or attempting advanced adversarial domain adaptation on 26 samples is statistically ill-posed and will merely cycle between different modes of severe overfitting.
2. **Preprocessing vs. Weights Trade-Off:**  
   Physics-calibrated preprocessing (`CalibratedPhysicsPreprocessor` with $2.385	imes$ Doppler stretching) improved Macro F1 from 0.1689 to 0.2061 without altering a single weight of the production model.
3. **Safety Protection:**  
   `models/csiformer_phase13_best.pth` must remain the official production checkpoint. `models/csiformer_phase15_adapted.pth` must remain an experimental checkpoint.
4. **Actionable Decision:**  
   **Further neural network retraining or adaptation is NOT justified until the physical dataset has been expanded to at least Stage 1 pilot targets ($\ge 35$ fall windows, $\ge 100$ total sessions across 3+ participants).**
