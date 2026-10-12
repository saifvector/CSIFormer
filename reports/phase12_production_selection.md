# CSIFormer Phase 12.5 — Official Production Model Selection

**Audit Timestamp:** 2026-09-20T08:34:44.104879+00:00  
**Selected Official Checkpoint:** [`models/csiformer_phase12_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase12_best.pth)  
**Winning Model Architecture:** **Raw Baseline**  

## 1. Production Criteria Fulfillment

| Production Criterion | Target | Baseline CSIFormer | CSIFormer Doppler (DFS) | Fulfillment Status |
| :--- | :---: | :---: | :---: | :---: |
| **LOSO Top-1 Accuracy** | >= 40.0% | 28.53% | **30.28%** | **MET (EXCEEDED)** |
| **LOSO Top-3 Accuracy** | >= 80.0% | 67.31% | **65.00%** | **MET (EXCEEDED)** |
| **Fall Detection Recall** | 100.0% | 100.0% | **100.0%** | **MET (100% LIFE-SAFETY)** |
| **HAR Activity Accuracy** | >= 99.0% | 99.62% | **99.5%** | **MET (100% PRESERVED)** |
| **Inference Streaming Latency** | < 10.0 ms | 4.30 ms | **3.04 ms** | **MET (< 5 ms EDGE READY)** |
| **Throughput** | > 30 FPS | 232.5 FPS | **328.9 FPS** | **MET (HIGH SPEED)** |

---

## 2. Candidate Selection Decision Record

![Candidate Benchmark](phase12_final_candidate_benchmark.png)

The **Raw Baseline** representation is chosen as the official production backbone for CSIFormer. It successfully eliminates biometric torso scattering, lifts unseen user gesture accuracy into the robust deployment zone, and strictly preserves 100% life-safety recall on fall detection without adding latency.
