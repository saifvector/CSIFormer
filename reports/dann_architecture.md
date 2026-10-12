# CSIFormer Phase 11.3 — Domain-Adversarial Architecture Specification

**Generated Date:** 2026-09-20T07:34:41.960163+00:00  

## 1. Network Topology

```text
Input CSI Packet Tensor X in R^[Batch, 50, 56]
        |
        v
Multi-Scale 1D-CNN Feature Extractor (Conv1D + BatchNorm + GELU)
        |
        v
3-Layer Pre-LN Transformer Encoder (8 Heads, d_model=128, dim_ff=512)
        |
        v
Temporal Attention Pooling Layer
        |
        +============================== z in R^[Batch, 128] =============================+
        |                                                                               |
        v (Forward Pass)                                                                v (Forward Pass)
Activity / Gesture Head (Linear -> GELU -> Dropout -> Linear)       Gradient Reversal Layer (GRL, -alpha)
        |                                                                               |
        v                                                                               v
12-Class Activity Logits                                            Domain Classifier (Linear -> BN -> ReLU -> Linear)
        |                                                                               |
        v                                                                               v
L_gesture (CrossEntropyLoss)                                        5-Domain Subject Logits (L_domain)
```

---

## 2. Mathematical Objective Function

$$\min_{\theta_f, \theta_y} \max_{\theta_d} \mathcal{L}(\theta_f, \theta_y, \theta_d) = \mathcal{L}_{\text{gesture}}(\theta_f, \theta_y) + 0.2\mathcal{L}_{\text{presence}} + 0.2\mathcal{L}_{\text{motion}} - \lambda \mathcal{L}_{\text{domain}}(\theta_f, \theta_d)$$

- In the forward pass, GRL acts as an identity operator: $R(z) = z$.
- In the backward pass, GRL inverts and scales the gradients: $\frac{\partial \mathcal{L}}{\partial z} = -\alpha \frac{\partial \mathcal{L}_{\text{domain}}}{\partial z}$.
- Selected Optimal Domain Adaptation Weight: $\mathbf{\lambda = 1.0}$.
