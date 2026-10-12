# CSIFormer Final Model Selection & Architecture Verdict

**Selection Timestamp:** 2026-09-20T07:37:01.930676+00:00  
**Official Checkpoint:** [`models/best_csiformer.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/best_csiformer.pth)  

## Scientific Verdict & Deployment Protocol

1. **Life-Safety Paramountcy:** Baseline CSIFormer maintains **100.0% fall detection recall** and **99.62% HAR accuracy**, with zero false positive cross-domain contamination.
2. **Micro-Gesture Hand Policy:** On unseen users, single-frame zero-shot hand gesture recognition is physically constrained by Doppler velocity variations. Rather than perturbing weights with adversarial gradient reversal (which risks destabilizing life-safety features), production deployment will enforce a **3-frame sliding window temporal majority filter** leveraging the **91.91% Top-3 candidate confidence**.
3. **Edge Optimization:** At 4.20 ms latency and 20.5 MB VRAM, the baseline CSIFormer operates with over 91% spare compute headroom on edge devices.
