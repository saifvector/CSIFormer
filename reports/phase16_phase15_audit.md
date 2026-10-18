# CSIFormer Phase 16 — Comprehensive Audit of Phase 15 Results

**Document Version:** 1.0.0  
**Audit Date:** October 18, 2026  
**Auditor:** Principal Wireless Sensing Research Scientist & Lead Agent  
**Status:** **EMPIRICALLY VERIFIED & AUDITED**  
**Production Checkpoint Audited:** `models/csiformer_phase13_best.pth` (MD5: `383b4d98c08f8970b0443738f170ec01`)  
**Experimental Checkpoint Audited:** `models/csiformer_phase15_adapted.pth` (MD5: `ab3d97a04d78edf75d807178772bc828`)

---

## 1. Executive Summary & Audit Verdict

Phase 16 initiated an exhaustive, line-by-line verification of the data, scripts, and claims reported in Phase 15. The audit executed `scratch/audit_phase15_reproduce.py` directly against the raw dataset captures in `data/real_csi_dataset/`, reproducing all metrics and evaluating signal-processing and machine-learning assumptions.

### Key Audit Findings

| Audit Dimension | Phase 15 Claimed State | Verified Physical Reality | Audit Verdict |
| :--- | :--- | :--- | :---: |
| **Dataset Manifest Integrity** | 23 sessions, 3,212 packets | 23 JSON/CSV files, 3,212 packets verified bit-for-bit (0 mismatches) | **VERIFIED** |
| **Window Construction** | 49 non-overlapping $[50, 56]$ windows | `step=50`, `size=50`, 0 duplicate windows, 0 window overlap across sessions | **VERIFIED** |
| **Metric Reproduction** | Baseline: 14.29% & 27.27%; Adapted: 18.18% | Exactly reproduced to 2 decimal places on CUDA runtime | **VERIFIED** |
| **Baseline Acc Discrepancy** | Unexplained tension between 14.29% and 27.27% | **14.29% (7/49)** was on ALL windows; **27.27% (3/11)** was on TEST split only | **RESOLVED** |
| **Fall Recall Improvement** | 0.00% $\to$ 50.00% fall recall reported | **Only 2 fall windows in test split**; 50% represents **1 detected fall window** | **EXPOSED** |
| **Participant Independence** | Reported as held-out test split | `Participant_02` is in **both Train and Test**; test is seen-subject, not LOSO | **EXPOSED** |
| **Subcarrier Interpolation** | 56 active tones utilized | Hardware serial outputs **5 tones**; software linearly interpolates $5 \to 56$ | **EXPOSED** |
| **Nyquist Velocity Limit** | $v_{\max} = 1.09\text{ m/s}$ at 35.58 Hz | Monostatic formula accurate; Bistatic radar geometry & 41.4% jitter identified | **REFINED** |

---

## 2. Dataset Manifest & File Integrity Audit

The dataset manifest (`data/real_csi_dataset/dataset_manifest.json`) was checked against the physical files on disk:

```
Total Sessions Declared in Manifest:  23
Total JSON Files Located on Disk:     23
Total CSV Files Located on Disk:      23
Declared Packet Count:                3,212 packets
Actual Parsed Frames:                 3,212 packets
Packet Count Discrepancies:           0 (100% Match)
```

Every session JSON file contains complete frame records including `timestamp`, `sequence`, `rssi`, `noise`, `amplitudes` ($[56]$), and `phases` ($[56]$).

---

## 3. Split Isolation, Window Slicing, and Leakage Audit

### 3.1 Window Slicing Verification
In `backend/app/services/real_csi_collector.py` and `scratch/evaluate_phase15_baseline.py`, sliding windows are extracted with:
```python
window_size = 50
step = 50
for start_idx in range(0, n_frames - 50 + 1, step):
    win = mat[start_idx:start_idx + 50, :56]
```
- Because `step == window_size == 50`, within any individual session, contiguous windows are completely disjoint ($[0:50]$, $[50:100]$, $[100:150]$).
- Hashing each extracted window confirmed **0 duplicate windows** across the entire dataset.
- Because each session is assigned to exactly one split, there is **zero window overlap across splits**.

### 3.2 Participant Leakage Discovery (Critical Finding)
The audit inspected the participant metadata across splits:

| Split | Number of Sessions | Extracted Windows | `Participant_01` Windows | `Participant_02` Windows |
| :--- | :---: | :---: | :---: | :---: |
| **Train Split** | 12 | 26 | 13 (50%) | 13 (50%) |
| **Validation Split** | 6 | 12 | 12 (100%) | 0 (0%) |
| **Held-Out Test Split** | 5 | 11 | 0 (0%) | 11 (100%) |
| **Total** | **23** | **49** | **25** | **24** |

**Finding:**
While the splits are strictly session-independent, **`Participant_02` is present in both the Training split (13 windows) and the Test split (11 windows)**.
Therefore, the Phase 15 test evaluation was a **Seen-Subject evaluation**, NOT a Leave-One-Subject-Out (LOSO) cross-subject evaluation. True cross-subject generalization on completely unseen individuals was not tested in Phase 15.

---

## 4. Resolution of the Baseline Accuracy Discrepancy (14.29% vs. 27.27%)

Phase 15 documentation contained two different baseline accuracy numbers for the unmodified Phase 13 production model:
1. `reports/phase15_baseline_evaluation.md` reported **14.29%**.
2. `reports/phase15_adaptation_comparison.md` reported **27.27%**.

### Audit Resolution:
The audit confirmed the exact source and mathematics of both figures:
- **14.29%:** Evaluated on **ALL 49 windows** (Train + Val + Test combined) in `scratch/evaluate_phase15_baseline.py`.
  $$\text{Accuracy}_{\text{ALL}} = \frac{7\text{ correct predictions}}{49\text{ total windows}} = 14.2857\% \approx 14.29\%$$
- **27.27%:** Evaluated **ONLY on the 11 held-out test windows** in `scratch/execute_phase15_adaptation_benchmark.py`.
  $$\text{Accuracy}_{\text{TEST}} = \frac{3\text{ correct predictions}}{11\text{ test windows}} = 27.2727\% \approx 27.27\%$$

Both figures are mathematically accurate calculations on their respective evaluation domains. However, comparing 14.29% to 27.27% without stating the sample subset creates confusion.

---

## 5. Fall Recall Calculation & Sample Size Reality

Phase 15 reported that supervised domain adaptation increased Fall Recall from **0.00%** to **50.00%**.

### Audit Inspection of the Test Split:
The 11 test windows have the following class distribution:
- `Class 0 (Push&Pull)`: 2 windows
- `Class 2 (Clap)`: 2 windows
- `Class 8 (Sit/Clean)`: 3 windows
- `Class 9 (FALL)`: **2 windows**
- `Class 11 (Walk)`: 2 windows
- `Class 6 (Static)`: 0 windows

**Mathematical Breakdown:**
- Baseline Model (Method 0): Predicted 0 falls correctly out of 2 $\implies \text{Recall} = \frac{0}{2} = \mathbf{0.00\%}$.
- Adapted Model (Method 3): Predicted 1 fall correctly out of 2 $\implies \text{Recall} = \frac{1}{2} = \mathbf{50.00\%}$.

**Scientific Implication:**
The reported 50% fall recall represents **literally one correctly classified fall window** ($N=2$).
With a sample size of $N=2$, the $95\%$ Wilson score confidence interval for a single success is $[9.45\%, 90.55\%]$.
While detecting 1 real hardware fall is a positive step over missing all of them, claiming "reliable fall detection" or robust safety performance based on $N=2$ test samples is scientifically invalid.

---

## 6. Physical Meaning of the 5-to-56 Subcarrier Interpolation

### Physical Context:
In 802.11n HT20 (20 MHz bandwidth), an OFDM channel contains 64 FFT bins, with 56 active subcarriers spaced $312.5\text{ kHz}$ apart. Multipath propagation creates frequency-selective fading: different subcarriers experience constructive or destructive interference with distinct nulls across the $20\text{ MHz}$ band.

### Audit of Implementation:
In `backend/app/services/real_csi_collector.py` (lines 335–340):
```python
if len(raw_amps) != self.TARGET_SUBCARRIERS:
    x_old = np.linspace(0, 1, len(raw_amps))
    x_new = np.linspace(0, 1, self.TARGET_SUBCARRIERS)
    aligned_amp = np.interp(x_new, x_old, raw_amps).astype(np.float32)
```
1. **Loss of High-Frequency Spatial Multipath:** The hardware firmware emits only 5 subcarrier values. Linearly interpolating from 5 to 56 points produces piecewise linear ramps, erasing genuine multipath nulls and frequency-selective features.
2. **Convolutional Filter Mismatch:** The model's 1D/2D CNN filters (`m.raw_cnn`) were trained on Intel 5300 CSI containing 56 independent RF measurements. When fed linearly interpolated ramps, the spatial gradients $\frac{\partial \text{CSI}}{\partial f}$ are flat segments rather than physical multipath profiles.
3. **Data Storage Flaw in Phase 15:** In Phase 15 captures, the JSON files stored the interpolated $[56]$ vector, but discarded the raw $[5]$ measurements.

---

## 7. Sampling Behavior & Doppler Velocity Physics Audit

### 7.1 Measured Timing Telemetry:
Evaluating all consecutive frame timestamp deltas ($\Delta t$) across the 23 sessions yielded:
- **Mean $\Delta t$:** $28.11\text{ ms}$
- **Median $\Delta t$:** $29.06\text{ ms}$
- **Standard Deviation (Jitter):** $11.64\text{ ms}$ ($41.4\%$ relative jitter)
- **Effective Sample Rate:** $f_s = \frac{1}{\bar{\Delta t}} = 35.58\text{ Hz}$
- **Nyquist Frequency Limit:** $f_{\text{nyq}} = \frac{f_s}{2} = 17.79\text{ Hz}$

### 7.2 Velocity Limit Refinement:
- **Carrier Frequency:** $f_c = 2.442\text{ GHz} \implies \lambda = \frac{c}{f_c} = 0.1228\text{ m}$.
- **Monostatic Approximation:**
  $$v_{\max} = \frac{f_{\text{nyq}} \lambda}{2} = \frac{17.79 \times 0.1228}{2} = 1.092\text{ m/s} \approx 3.93\text{ km/h}$$
- **Bistatic Radar Reality:** In a room where Tx and Rx are separated by a baseline, the Doppler shift for a human moving with velocity $\vec{v}$ is:
  $$f_d = \frac{v}{\lambda} \left(\cos \theta_{\text{Tx}} + \cos \theta_{\text{Rx}}\right) = \frac{2 v}{\lambda} \cos\left(\frac{\beta}{2}\right) \cos \delta$$
  where $\beta$ is the bistatic angle and $\delta$ is the angle of motion relative to the bistatic bisector.
  - When a human falls or moves perpendicular to the Tx-Rx line, $\cos(\beta/2) \le 1$, meaning the observed Doppler shift is *lower* than the monostatic equivalent for the same physical velocity.
  - However, human falls reach instantaneous torso/head velocities of $2.0\text{–}3.5\text{ m/s}$. At $35.58\text{ Hz}$, these velocities exceed $1.09\text{ m/s}$ and fold back into lower frequencies (aliasing).
- **Packet Jitter Impact:** Non-uniform packet intervals ($\sigma = 11.64\text{ ms}$) introduce phase jitter in the standard discrete STFT, smearing the spectrogram floor and creating false low-frequency Doppler artifacts.

---

## 8. Summary of Identified Flaws & Required Remediation for Phase 16

1. **Address Low Test Sample Size:** Expand the physical dataset so that each class in the held-out test split has at least 10–15 windows (especially falls), giving statistical significance.
2. **Implement LOSO Evaluation:** Ensure the evaluation protocol partitions participants so that the held-out test set contains **only unseen participants** who never appeared in training.
3. **Preserve Raw Uninterpolated CSI:** Upgrade the collection recorder to save the exact raw measurements alongside any aligned or interpolated features, keeping the raw capture immutable.
4. **Resampling / Jitter Mitigation:** Resample incoming packet streams onto a uniform temporal grid (e.g., cubic spline or linear time interpolation) prior to computing STFT Doppler spectrograms, mitigating spectral leakage from $41.4\%$ timing jitter.
