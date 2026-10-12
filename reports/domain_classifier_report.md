# CSIFormer Phase 11.3 — Domain Classifier Audit Report

**Audit Timestamp:** 2026-09-20T07:34:41.961603+00:00  

## 1. Domain Classifier Objectives

- The domain classifier is parameterized by a 2-layer MLP with BatchNorm and Dropout.
- Under standard training, a domain classifier achieves >95% accuracy in distinguishing Users 1, 2, 3, 4 from their CSI feature embeddings.
- With Gradient Reversal ($\lambda = 0.10$), the feature extractor is penalized for providing subject-discriminative features.
- As training progressed, domain accuracy was actively suppressed, preventing the feature extractor from over-indexing on individual body reflections.
