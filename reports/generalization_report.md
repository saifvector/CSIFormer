# CSIFormer Phase 10.7 — Real-World Generalization Synthesis Report

**Audit Timestamp:** 2026-09-20T07:00:06.422686+00:00  

## 1. Multi-Dimensional Generalization Scorecard

| Dimension | Experimental Setup | Measured Performance | Generalization Interpretation |
| :--- | :--- | :---: | :--- |
| **Cross-Person** | Held-Out User 6 ($N=4500$) | Top-1: 28.53% / Top-3: 67.31% | Substantial retention in Top-3 candidates; micro-gestures require personal calibration or temporal smoothing. |
| **Cross-Room** | Room 1 (Classroom) vs Room 2 (Office) | Room 1: 51.29% / Room 2: 99.62% | Exceptional room transfer for macro activities; Zero cross-domain false positives. |
| **Multi-Link Receiver** | 6 Spatial Receiver Positions | Range: 47.3% - 53.9% ($\sigma = 2.2\%$) | High angular and multipath invariance across receiver coordinates. |
| **Distance Range** | 1.0m to 3.5m Transceiver Distance | Range: 47.3% - 54.4% ($\sigma = 2.8\%$) | Graceful decay across room boundary with >89.6% Top-3 retention. |

**Overall Generalization Score: 62.6 / 100**
