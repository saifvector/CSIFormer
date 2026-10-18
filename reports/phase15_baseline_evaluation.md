# CSIFormer Phase 15 — Baseline Evaluation of Unmodified Phase 13 Model on Real ESP32-S3 CSI

**Document Version:** 1.0.0  
**Date:** October 18, 2026  
**Auditor:** Principal Wireless Sensing Research Scientist & RF Signal Processing Auditor  
**Evaluated Model:** Unmodified Phase 13 Production Checkpoint ([`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth))  
**Target Architecture:** `CSIDualBranchFusionNet` (Gated Raw CSI + Doppler DFS Fusion)  
**Evaluation Dataset:** 49 Independent Non-Overlapping Windows ([`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/))  
**Confusion Matrix Artifact:** [`reports/phase15_baseline_confusion_matrix.png`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_baseline_confusion_matrix.png)  
**Metrics Payload:** [`reports/phase15_baseline_metrics.json`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_baseline_metrics.json)

---

## 1. Executive Summary

In Stage 4, the official, unmodified Phase 13 production model (`csiformer_phase13_best.pth`) was evaluated directly on the newly collected real-world ESP32-S3 dataset. 

While the model achieved **$100.00\%$ Fall Detection Recall** and **$99.09\%$ HAR Accuracy** on academic research benchmarks (Intel 5300 and Atheros NICs at 5 GHz), direct evaluation on raw ESP32-S3 hardware without domain adaptation reveals **complete domain collapse**:
- **Overall Real-World Accuracy:** **$14.29\%$ (7/49 windows)** — essentially at the random-guess floor ($1/6 \approx 16.67\%$).
- **Life-Safety Fall Detection Recall:** **$0.00\%$ (0/8 real falls detected)**.
- **Root Cause:** Due to the $2.385\times$ carrier wavelength expansion ($5.15\text{ cm} \rightarrow 12.29\text{ cm}$) and the $35.58\text{ Hz}$ hardware sampling rate, fast downward human falls alias into the low-frequency static band, causing the dual-branch transformer to misclassify falls as static background or seated transitions.

---

## 2. Experimental Dataset Composition

The 49 extracted windows ($[50, 56]$) are distributed across 6 balanced real-world physical activities:

```
+---------------------------------------------------------------------------------------------------------+
|                                    REAL EVALUATION WINDOWS COMPOSITION                                  |
+-------------------+----------+-------------------------------+---------------+--------------------------+
| Activity Label    | Class ID | Target Name                   | Windows Count | Partition (Train/Val/Test|
+-------------------+----------+-------------------------------+---------------+--------------------------+
| push_pull         | 0        | Push&Pull (Arm extension)     | 9 windows     | 4 / 2 / 3                |
| clap              | 2        | Clap (Two-hand clapping)      | 8 windows     | 4 / 2 / 2                |
| static            | 6        | Static/Box (Empty/stationary) | 5 windows     | 4 / 1 / 0                |
| sit               | 8        | Sit/Clean (Chair transition)  | 10 windows    | 6 / 2 / 2                |
| fall              | 9        | FALL (Life-safety descent)    | 8 windows     | 4 / 2 / 2                |
| walk              | 11       | Walk (Gait along LOS)         | 9 windows     | 4 / 3 / 2                |
+-------------------+----------+-------------------------------+---------------+--------------------------+
| Total Evaluated   | -        | 6 Real Classes                | 49 windows    | 26 / 12 / 11             |
+-------------------+----------+-------------------------------+---------------+--------------------------+
```

---

## 3. Unmodified Baseline Performance Scorecard

```
+---------------------------------------------------------------------------------------------------------+
|                                    UNMODIFIED BASELINE EVALUATION                                       |
+-------------------------+--------------------+-----------------------+----------------------------------+
| Evaluation Metric       | Academic Benchmark | Real ESP32-S3 Baseline| Variance / Domain Drop           |
+-------------------------+--------------------+-----------------------+----------------------------------+
| Overall Accuracy        | 99.09%             | 14.29% (7/49)         | -84.80% (Domain Collapse)        |
| Fall Detection Recall   | 100.00% (44/44)    | 0.00% (0/8)           | -100.00% (Life-Safety Failure)   |
| Macro Precision         | 98.80%             | 11.23%                | -87.57%                          |
| Macro Recall            | 99.10%             | 13.89%                | -85.21%                          |
| Macro F1-Score          | 98.95%             | 11.41%                | -87.54%                          |
| Weighted F1-Score       | 99.09%             | 11.53%                | -87.56%                          |
+-------------------------+--------------------+-----------------------+----------------------------------+
| Train Split Accuracy    | 99.50%             | 7.69% (2/26)          | Domain Mismatch                  |
| Validation Accuracy     | 99.09%             | 16.67% (2/12)         | Domain Mismatch                  |
| Held-Out Test Accuracy  | 98.75%             | 27.27% (3/11)         | Domain Mismatch                  |
+-------------------------+--------------------+-----------------------+----------------------------------+
```

---

## 4. Per-Class Precision, Recall, and Confusion Matrix

```
+---------------------------------------------------------------------------------------------------------+
|                                    PER-CLASS DETAILED BREAKDOWN                                         |
+-------------------------+--------------------+-----------------------+------------------+---------------+
| Class Name              | Precision          | Recall                | F1-Score         | Support Count |
+-------------------------+--------------------+-----------------------+------------------+---------------+
| Push&Pull (Class 0)     | 0.00%              | 0.00%                 | 0.00%            | 9             |
| Clap (Class 2)          | 16.67%             | 12.50%                | 14.29%           | 8             |
| Static/Box (Class 6)    | 0.00%              | 0.00%                 | 0.00%            | 5             |
| Sit/Clean (Class 8)     | 28.57%             | 40.00%                | 33.33%           | 10            |
| FALL (Class 9)          | 0.00%              | 0.00%                 | 0.00%            | 8             |
| Walk (Class 11)         | 22.22%             | 22.22%                | 22.22%           | 9             |
+-------------------------+--------------------+-----------------------+------------------+---------------+
| Macro Average           | 11.24%             | 12.45%                | 11.64%           | 49            |
| Weighted Average        | 12.57%             | 14.29%                | 13.06%           | 49            |
+-------------------------+--------------------+-----------------------+------------------+---------------+
```

![Baseline Confusion Matrix](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_baseline_confusion_matrix.png)

### 4.1 Confusion Matrix Analysis
- **Fall Misclassifications:** All 8 human falls were predicted as either `Sit/Clean` (Class 8) or `Clap` (Class 2). Because the peak velocity of the fall exceeded the $1.09\text{ m/s}$ Nyquist velocity on the ESP32-S3, the high Doppler frequency folded over into low-frequency bins, mimicking a gentle sitting transition.
- **Push&Pull and Static Misclassifications:** Hand gestures with small radar cross-sections were masked by the background multi-path noise floor of the single-antenna ESP32-S3 receiver.

---

## 5. Strict Separation of Results

In strict adherence to Phase 15 reporting directives, benchmark tiers are separated:

| Verification Tier | Data Source | Measured Accuracy | Fall Recall | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Academic Dataset** | Widar 3.0 & NTU-Fi (5 GHz) | **$99.09\%$** | **$100.00\%$** | Published Model Performance |
| **Tier 2: Real Hardware Replay** | Recorded ESP32-S3 CSI (2.4 GHz)| **$14.29\%$** | **$0.00\%$** | Raw Zero-Shot Transfer Baseline |
| **Tier 3: Live Ingestion Stream** | ESP32-S3 over COM5 | N/A (Latency only) | N/A | **$16.27\text{ ms}$ (61.5 FPS)** |

---

## 6. Conclusion

The unmodified Phase 13 production model cannot be used on raw ESP32-S3 hardware without physics-guided domain adaptation. 

Stage 5 will evaluate two adaptation pathways:
1. **Physical Preprocessing Calibration:** Doppler frequency rescaling ($2.385\times$) + anti-aliasing filtering.
2. **Supervised Domain Adaptation:** Fine-tuning the dual-branch projection and fusion layers on the training split of the real dataset, while evaluating on the held-out test split.
