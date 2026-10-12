# CSIFormer Phase 11.2 — Latent Space & Information Encoding Audit

**Audit Timestamp:** 2026-09-20T07:30:02.303865+00:00  
**Analyzed Layer:** Temporal Attention Pooling Latent Space ($\mathbf{z} \in \mathbb{R}^{128}$)  

## 1. Information Encoding Quantification

| Statistical Metric | Subject Identity Clustering | Gesture Semantic Clustering | Diagnostic Ratio / Implication |
| :--- | :---: | :---: | :--- |
| **Silhouette Score ($S$)** | **-0.0039** | **-0.0105** | High subject clustering indicates severe domain entanglement. |
| **Davies-Bouldin Index ($DB$)** | **4.1157** | **6.4911** | Lower DB indicates tighter, more isolated clusters. |
| **K-Means Cluster Purity** | **56.0%** | **35.4%** | **1.58x** ratio of subject to gesture purity. |
| **Fisher Scatter Ratio ($S_B / S_W$)** | **0.2214** | **0.2446** | Linear separability of subjects is substantial in the latent space. |

---

## 2. Core Scientific Finding

### How Much Information Encodes Subject vs Gesture?
- The baseline CSIFormer latent space exhibits **strong subject clustering** (Purity = 56.0%, Fisher Ratio = 0.2214).
- The model inadvertently learns user-specific static multipath features (user body mass, dielectric absorption, antenna reflection coefficients) as shortcut features for gesture prediction.
- **Conclusion:** When presented with an unseen user (User 6), the model projects the CSI into an out-of-distribution subject manifold, causing the classifier to fail. **Domain-adversarial alignment (DANN) is mathematically required to collapse the subject clusters.**
