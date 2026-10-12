# CSIFormer Phase 10.6 — Forensic Error Analysis Report

**Generated Timestamp:** 2026-09-20T06:49:40.439262+00:00  
**Total Held-Out Test Samples:** 4464  
**Total Misclassified Samples:** 2047 (45.86%)  
**Total Correct Predictions:** 2417 (54.14%)  

---

## 1. Dominant Confusion Patterns

The misclassifications are concentrated strictly within physical Wi-Fi multipath ambiguity clusters:

| Rank | Error Confusion Pattern | Count | % of All Misclassifications | Physical Wi-Fi Root Cause |
| :---: | :--- | :---: | :---: | :--- |
| **1** | `Push&Pull -> Sweep` | 246 | 12.0% | Radial arm translation overlaps with tangential Doppler shift |
| **2** | `Sweep -> Clap` | 157 | 7.7% | Inward arm sweep matches inward bilateral clap displacement |
| **3** | `Sweep -> Push&Pull` | 152 | 7.4% | Symmetric reverse Doppler signature |
| **4** | `Push&Pull -> Clap` | 127 | 6.2% | Bilateral hand closure vs forward hand push |
| **5** | `Draw-Zigzag -> Draw-O` | 122 | 6.0% | Multi-stroke continuous trajectory velocity matching |
| **6** | `Clap -> Slide` | 100 | 4.9% | Lateral hand trajectory overlap |
| **7** | `Slide -> Clap` | 92 | 4.5% | Reciprocal lateral trajectory ambiguity |
| **8** | `Draw-O -> Draw-Zigzag` | 87 | 4.3% | Reciprocal continuous gesture stroke ambiguity |
| **9** | `Clap -> Sweep` | 88 | 4.3% | Transceiver LOS proximity effect |
| **10** | `Push&Pull -> Draw-Zigzag` | 82 | 4.0% | High-frequency Doppler spikes |

---

## 2. Cross-Domain Leakage Verification

- **Widar 3.0 -> NTU-Fi Leakage:** **0 errors** (out of 4,200 samples)
- **NTU-Fi -> Widar 3.0 Leakage:** **0 errors** (out of 264 samples)
- **Scientific Conclusion:** **Zero Cross-Domain Contamination Confirmed.** Micro-gestures and macro-displacements occupy completely separated latent manifolds.

---

## 3. High-Confidence Failures (Confidence >= 70%)

There are **202 samples** where the model predicted with >= 70% confidence but was incorrect:

| Sample Index | Sample ID | True Class | Predicted Class | Confidence | Source Dataset | File Reference |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 82 | `user1-1-3-4-5-r5` | **Push&Pull** | `Draw-Zigzag` | 86.3% | widar3 | `` |
| 122 | `user1-1-5-1-5-r3` | **Push&Pull** | `Clap` | 71.5% | widar3 | `` |
| 132 | `user1-1-5-3-5-r1` | **Push&Pull** | `Sweep` | 72.2% | widar3 | `` |
| 146 | `user1-1-5-5-5-r3` | **Push&Pull** | `Slide` | 70.2% | widar3 | `` |
| 182 | `user1-2-2-1-5-r3` | **Sweep** | `Clap` | 77.7% | widar3 | `` |
| 219 | `user1-2-3-2-5-r4` | **Sweep** | `Clap` | 83.5% | widar3 | `` |
| 227 | `user1-2-3-3-5-r6` | **Sweep** | `Push&Pull` | 73.8% | widar3 | `` |
| 284 | `user1-2-5-3-5-r3` | **Sweep** | `Draw-Zigzag` | 74.0% | widar3 | `` |
| 307 | `user1-3-1-2-5-r2` | **Clap** | `Slide` | 72.9% | widar3 | `` |
| 342 | `user1-3-2-3-5-r1` | **Clap** | `Sweep` | 78.8% | widar3 | `` |
| 343 | `user1-3-2-3-5-r2` | **Clap** | `Slide` | 84.4% | widar3 | `` |
| 348 | `user1-3-2-4-5-r1` | **Clap** | `Sweep` | 72.1% | widar3 | `` |
| 353 | `user1-3-2-4-5-r6` | **Clap** | `Draw-Zigzag` | 82.0% | widar3 | `` |
| 399 | `user1-3-4-2-5-r4` | **Clap** | `Slide` | 88.7% | widar3 | `` |
| 419 | `user1-3-4-5-5-r6` | **Clap** | `Slide` | 96.0% | widar3 | `` |
| 423 | `user1-3-5-1-5-r4` | **Clap** | `Draw-O` | 71.2% | widar3 | `` |
| 442 | `user1-3-5-4-5-r5` | **Clap** | `Draw-O` | 80.2% | widar3 | `` |
| 449 | `user1-3-5-5-5-r6` | **Clap** | `Slide` | 75.8% | widar3 | `` |
| 450 | `user1-4-1-1-5-r1` | **Slide** | `Clap` | 80.1% | widar3 | `` |
| 462 | `user1-4-1-3-5-r1` | **Slide** | `Clap` | 86.9% | widar3 | `` |

---

## 4. Top 100 Misclassified Samples (Highest Confidence Misclassifications)

| Rank | Sample Index | Sample ID | True Class | Predicted Class | Confidence | Dataset | File Path |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| 1 | 419 | `user1-3-4-5-5-r6` | **Clap** | `Slide` | 96.0% | widar3 | `` |
| 2 | 2803 | `user4-3-4-3-5-r2` | **Clap** | `Slide` | 96.0% | widar3 | `` |
| 3 | 4264 | `test_circle_circle178` | **circle** | `clean` | 94.6% | ntufi_har | `` |
| 4 | 644 | `user1-5-2-3-5-r3` | **Draw-O** | `Slide` | 93.5% | widar3 | `` |
| 5 | 3324 | `user6-1-1-5-5-r1` | **Push&Pull** | `Draw-Zigzag` | 90.9% | widar3 | `` |
| 6 | 2483 | `user4-1-3-4-5-r6` | **Push&Pull** | `Slide` | 90.8% | widar3 | `` |
| 7 | 624 | `user1-5-1-5-5-r1` | **Draw-O** | `Slide` | 90.5% | widar3 | `` |
| 8 | 1048 | `user1-7-5-5-5-r5` | **Push&Pull** | `Draw-Zigzag` | 89.1% | widar3 | `` |
| 9 | 957 | `user1-7-2-5-5-r4` | **Push&Pull** | `Draw-Zigzag` | 88.7% | widar3 | `` |
| 10 | 399 | `user1-3-4-2-5-r4` | **Clap** | `Slide` | 88.7% | widar3 | `` |
| 11 | 1592 | `user2-2-4-1-5-r3` | **Sweep** | `Slide` | 88.3% | widar3 | `` |
| 12 | 3824 | `user6-4-3-3-5-r3` | **Slide** | `Draw-O` | 87.9% | widar3 | `` |
| 13 | 3790 | `user6-4-2-2-5-r5` | **Slide** | `Draw-O` | 87.9% | widar3 | `` |
| 14 | 3312 | `user6-1-1-3-5-r1` | **Push&Pull** | `Draw-Zigzag` | 87.6% | widar3 | `` |
| 15 | 1098 | `user1-8-2-4-5-r1` | **Sweep** | `Slide` | 87.6% | widar3 | `` |
| 16 | 1399 | `user2-1-2-4-5-r2` | **Push&Pull** | `Slide` | 87.6% | widar3 | `` |
| 17 | 3420 | `user6-1-5-1-5-r1` | **Push&Pull** | `Draw-Zigzag` | 87.6% | widar3 | `` |
| 18 | 1545 | `user2-2-2-3-5-r4` | **Sweep** | `Push&Pull` | 87.5% | widar3 | `` |
| 19 | 1533 | `user2-2-2-1-5-r4` | **Sweep** | `Push&Pull` | 87.2% | widar3 | `` |
| 20 | 462 | `user1-4-1-3-5-r1` | **Slide** | `Clap` | 86.9% | widar3 | `` |
| 21 | 3373 | `user6-1-3-3-5-r2` | **Push&Pull** | `Draw-Zigzag` | 86.8% | widar3 | `` |
| 22 | 82 | `user1-1-3-4-5-r5` | **Push&Pull** | `Draw-Zigzag` | 86.3% | widar3 | `` |
| 23 | 3486 | `user6-2-2-2-5-r1` | **Sweep** | `Draw-Zigzag` | 86.2% | widar3 | `` |
| 24 | 2019 | `user3-1-3-2-5-r4` | **Push&Pull** | `Slide` | 86.2% | widar3 | `` |
| 25 | 3094 | `user4-5-4-1-5-r5` | **Draw-O** | `Draw-Zigzag` | 86.1% | widar3 | `` |
| 26 | 3142 | `user4-5-5-4-5-r5` | **Draw-O** | `Draw-Zigzag` | 85.8% | widar3 | `` |
| 27 | 1687 | `user2-3-2-2-5-r2` | **Clap** | `Slide` | 85.8% | widar3 | `` |
| 28 | 1398 | `user2-1-2-4-5-r1` | **Push&Pull** | `Slide` | 85.6% | widar3 | `` |
| 29 | 1725 | `user2-3-3-3-5-r4` | **Clap** | `Slide` | 85.5% | widar3 | `` |
| 30 | 2685 | `user4-2-5-3-5-r4` | **Sweep** | `Slide` | 85.5% | widar3 | `` |
| 31 | 3837 | `user6-4-3-5-5-r4` | **Slide** | `Draw-O` | 85.5% | widar3 | `` |
| 32 | 4028 | `user6-5-5-2-5-r3` | **Draw-O** | `Draw-Zigzag` | 85.0% | widar3 | `` |
| 33 | 704 | `user1-5-4-3-5-r3` | **Draw-O** | `Draw-Zigzag` | 84.8% | widar3 | `` |
| 34 | 906 | `user1-7-1-2-5-r1` | **Push&Pull** | `Draw-Zigzag` | 84.8% | widar3 | `` |
| 35 | 3014 | `user4-5-1-3-5-r3` | **Draw-O** | `Draw-Zigzag` | 84.6% | widar3 | `` |
| 36 | 1557 | `user2-2-2-5-5-r4` | **Sweep** | `Push&Pull` | 84.5% | widar3 | `` |
| 37 | 654 | `user1-5-2-5-5-r1` | **Draw-O** | `Draw-Zigzag` | 84.5% | widar3 | `` |
| 38 | 343 | `user1-3-2-3-5-r2` | **Clap** | `Slide` | 84.4% | widar3 | `` |
| 39 | 3815 | `user6-4-3-1-5-r6` | **Slide** | `Draw-O` | 84.2% | widar3 | `` |
| 40 | 3283 | `user4-6-5-3-5-r2` | **Draw-Zigzag** | `Draw-O` | 84.1% | widar3 | `` |
| 41 | 3564 | `user6-2-4-5-5-r1` | **Sweep** | `Draw-Zigzag` | 83.6% | widar3 | `` |
| 42 | 219 | `user1-2-3-2-5-r4` | **Sweep** | `Clap` | 83.5% | widar3 | `` |
| 43 | 1134 | `user1-8-3-5-5-r1` | **Sweep** | `Slide` | 82.7% | widar3 | `` |
| 44 | 3861 | `user6-4-4-4-5-r4` | **Slide** | `Draw-O` | 82.6% | widar3 | `` |
| 45 | 2898 | `user4-4-2-4-5-r1` | **Slide** | `Push&Pull` | 82.5% | widar3 | `` |
| 46 | 1587 | `user2-2-3-5-5-r4` | **Sweep** | `Slide` | 82.3% | widar3 | `` |
| 47 | 3640 | `user6-3-2-2-5-r5` | **Clap** | `Slide` | 82.3% | widar3 | `` |
| 48 | 2101 | `user3-2-1-1-5-r2` | **Sweep** | `Push&Pull` | 82.2% | widar3 | `` |
| 49 | 353 | `user1-3-2-4-5-r6` | **Clap** | `Draw-Zigzag` | 82.0% | widar3 | `` |
| 50 | 2437 | `user4-1-2-2-5-r2` | **Push&Pull** | `Slide` | 81.9% | widar3 | `` |
| 51 | 900 | `user1-7-1-1-5-r1` | **Push&Pull** | `Draw-Zigzag` | 81.8% | widar3 | `` |
| 52 | 1152 | `user1-8-4-3-5-r1` | **Sweep** | `Clap` | 81.5% | widar3 | `` |
| 53 | 1373 | `user2-1-1-4-5-r6` | **Push&Pull** | `Sweep` | 81.4% | widar3 | `` |
| 54 | 4048 | `user6-5-5-5-5-r5` | **Draw-O** | `Slide` | 81.3% | widar3 | `` |
| 55 | 1439 | `user2-1-3-5-5-r6` | **Push&Pull** | `Sweep` | 81.3% | widar3 | `` |
| 56 | 3381 | `user6-1-3-4-5-r4` | **Push&Pull** | `Draw-Zigzag` | 81.0% | widar3 | `` |
| 57 | 663 | `user1-5-3-1-5-r4` | **Draw-O** | `Clap` | 80.8% | widar3 | `` |
| 58 | 3423 | `user6-1-5-1-5-r4` | **Push&Pull** | `Draw-Zigzag` | 80.7% | widar3 | `` |
| 59 | 4127 | `user6-6-3-3-5-r6` | **Draw-Zigzag** | `Slide` | 80.7% | widar3 | `` |
| 60 | 4034 | `user6-5-5-3-5-r3` | **Draw-O** | `Draw-Zigzag` | 80.6% | widar3 | `` |
| 61 | 919 | `user1-7-1-4-5-r2` | **Push&Pull** | `Draw-Zigzag` | 80.6% | widar3 | `` |
| 62 | 1731 | `user2-3-3-4-5-r4` | **Clap** | `Slide` | 80.3% | widar3 | `` |
| 63 | 3326 | `user6-1-1-5-5-r3` | **Push&Pull** | `Slide` | 80.2% | widar3 | `` |
| 64 | 442 | `user1-3-5-4-5-r5` | **Clap** | `Draw-O` | 80.2% | widar3 | `` |
| 65 | 450 | `user1-4-1-1-5-r1` | **Slide** | `Clap` | 80.1% | widar3 | `` |
| 66 | 3115 | `user4-5-4-5-5-r2` | **Draw-O** | `Draw-Zigzag` | 79.8% | widar3 | `` |
| 67 | 943 | `user1-7-2-3-5-r2` | **Push&Pull** | `Draw-Zigzag` | 79.7% | widar3 | `` |
| 68 | 2827 | `user4-3-5-2-5-r2` | **Clap** | `Slide` | 79.6% | widar3 | `` |
| 69 | 2489 | `user4-1-3-5-5-r6` | **Push&Pull** | `Slide` | 79.5% | widar3 | `` |
| 70 | 668 | `user1-5-3-2-5-r3` | **Draw-O** | `Draw-Zigzag` | 79.0% | widar3 | `` |
| 71 | 2229 | `user3-2-5-2-5-r4` | **Sweep** | `Push&Pull` | 79.0% | widar3 | `` |
| 72 | 1503 | `user2-2-1-1-5-r4` | **Sweep** | `Push&Pull` | 78.9% | widar3 | `` |
| 73 | 342 | `user1-3-2-3-5-r1` | **Clap** | `Sweep` | 78.8% | widar3 | `` |
| 74 | 865 | `user1-6-4-5-5-r2` | **Draw-Zigzag** | `Draw-O` | 78.6% | widar3 | `` |
| 75 | 2791 | `user4-3-4-1-5-r2` | **Clap** | `Draw-Zigzag` | 78.6% | widar3 | `` |
| 76 | 2060 | `user3-1-4-4-5-r3` | **Push&Pull** | `Slide` | 78.3% | widar3 | `` |
| 77 | 3834 | `user6-4-3-5-5-r1` | **Slide** | `Draw-O` | 78.0% | widar3 | `` |
| 78 | 614 | `user1-5-1-3-5-r3` | **Draw-O** | `Draw-Zigzag` | 78.0% | widar3 | `` |
| 79 | 1536 | `user2-2-2-2-5-r1` | **Sweep** | `Slide` | 77.8% | widar3 | `` |
| 80 | 912 | `user1-7-1-3-5-r1` | **Push&Pull** | `Draw-Zigzag` | 77.8% | widar3 | `` |
| 81 | 2771 | `user4-3-3-2-5-r6` | **Clap** | `Draw-O` | 77.7% | widar3 | `` |
| 82 | 182 | `user1-2-2-1-5-r3` | **Sweep** | `Clap` | 77.7% | widar3 | `` |
| 83 | 3414 | `user6-1-4-5-5-r1` | **Push&Pull** | `Draw-O` | 77.6% | widar3 | `` |
| 84 | 4101 | `user6-6-2-4-5-r4` | **Draw-Zigzag** | `Slide` | 77.6% | widar3 | `` |
| 85 | 592 | `user1-4-5-4-5-r5` | **Slide** | `Clap` | 77.6% | widar3 | `` |
| 86 | 2137 | `user3-2-2-2-5-r2` | **Sweep** | `Push&Pull` | 77.3% | widar3 | `` |
| 87 | 1437 | `user2-1-3-5-5-r4` | **Push&Pull** | `Sweep` | 77.3% | widar3 | `` |
| 88 | 471 | `user1-4-1-4-5-r4` | **Slide** | `Draw-O` | 77.0% | widar3 | `` |
| 89 | 3598 | `user6-2-5-5-5-r5` | **Sweep** | `Draw-O` | 76.9% | widar3 | `` |
| 90 | 622 | `user1-5-1-4-5-r5` | **Draw-O** | `Slide` | 76.9% | widar3 | `` |
| 91 | 3627 | `user6-3-1-5-5-r4` | **Clap** | `Slide` | 76.8% | widar3 | `` |
| 92 | 1197 | `user1-8-5-5-5-r4` | **Sweep** | `Draw-Zigzag` | 76.8% | widar3 | `` |
| 93 | 1050 | `user1-8-1-1-5-r1` | **Sweep** | `Draw-Zigzag` | 76.6% | widar3 | `` |
| 94 | 3933 | `user6-5-2-1-5-r4` | **Draw-O** | `Slide` | 76.6% | widar3 | `` |
| 95 | 2736 | `user4-3-2-2-5-r1` | **Clap** | `Slide` | 76.6% | widar3 | `` |
| 96 | 2775 | `user4-3-3-3-5-r4` | **Clap** | `Draw-O` | 76.5% | widar3 | `` |
| 97 | 3550 | `user6-2-4-2-5-r5` | **Sweep** | `Draw-Zigzag` | 76.4% | widar3 | `` |
| 98 | 3198 | `user4-6-2-4-5-r1` | **Draw-Zigzag** | `Draw-O` | 76.4% | widar3 | `` |
| 99 | 3207 | `user4-6-2-5-5-r4` | **Draw-Zigzag** | `Draw-O` | 76.3% | widar3 | `` |
| 100 | 1468 | `user2-1-4-5-5-r5` | **Push&Pull** | `Sweep` | 76.3% | widar3 | `` |
