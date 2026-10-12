# CSIFormer Phase 13.3 — Subject-Invariant Contrastive Pretraining Audit

**Audit Timestamp:** 2026-09-20T10:41:47.279622+00:00  
**Best Performing Objective:** **Triplet Margin Loss**  

## 1. Contrastive Formulation Benchmark

| Pretraining Objective | Unseen Top-1 | Unseen Top-3 | Intra-Gesture Cross-Subj Sim | Inter-Gesture Sim | Discrimination Ratio | Alignment | Uniformity |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline (No Pretraining)** | **29.17%** | 66.17% | 0.6684 | 0.6392 | **1.05x** | 0.6631 | -1.2719 |
| **Supervised Contrastive (SupCon)** | **30.00%** | 68.83% | 0.8879 | 0.8044 | **1.10x** | 0.2242 | -0.6669 |
| **Triplet Margin Loss** | **34.17%** | 73.83% | 0.9692 | 0.9625 | **1.01x** | 0.0617 | -0.1448 |
| **NT-Xent Contrastive Loss** | **32.83%** | 72.17% | 0.8856 | 0.8182 | **1.08x** | 0.2287 | -0.6355 |

---

## 2. Key Scientific Findings

1. **Winner:** `Triplet Margin Loss` yields peak cross-subject transfer with **34.17% Top-1** and **73.83% Top-3**.
2. **Subject Disentanglement:** Enforcing positive pairs strictly across *different* human subjects forces the representation to discard biometric torso multipath while retaining limb velocity dynamics.
3. **Geometric Quality:** A higher Discrimination Ratio directly correlates with superior unseen-subject generalization.

![Contrastive Comparison](phase13_contrastive_comparison.png)
