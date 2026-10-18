# CSIFormer Phase 15 — Physical Domain Gap Forensic Analysis

**Document Version:** 1.0.0  
**Date:** October 18, 2026  
**Auditor:** Principal Wireless Sensing Research Scientist & RF Signal Processing Auditor  
**Empirical Basis:** 23 Validated Real-World Sessions (3,212 frames) from [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/)  
**Visual Artifact:** [`reports/phase15_domain_gap_analysis.png`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_domain_gap_analysis.png)  
**Metrics Payload:** [`reports/phase15_domain_gap_metrics.json`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_domain_gap_metrics.json)

---

## 1. Executive Summary

A core objective of Phase 15 is to establish whether the features extracted from commercial ESP32-S3 hardware are physically compatible with the representations used to train CSIFormer on research-grade testbeds (Widar 3.0 and NTU-Fi HAR).

This investigation confirms that **dimensional compatibility ($[1, 50, 56]$) does not imply physical equivalence**. Four severe domain gaps exist between academic datasets and real commercial silicon:
1. **Doppler Scaling Compression ($2.385\times$):** Wavelength expansion from $5.15\text{ cm}$ (5.825 GHz) to $12.29\text{ cm}$ (2.442 GHz) compresses identical human velocities into $2.385\times$ lower frequency shifts.
2. **Kinematic Nyquist Aliasing ($v_{\text{max}} = 1.09\text{ m/s}$):** At the verified hardware sampling rate of $35.58\text{ Hz}$, the Nyquist cutoff is $17.79\text{ Hz}$. Fast limb gestures ($>1.1\text{ m/s}$) and sudden human falls ($>2.0\text{ m/s}$) undergo severe spectral aliasing.
3. **Hardware Tone Truncation & Spatial Hallucination:** The current ESP32-S3 firmware emits 5 subcarrier IQ pairs per packet, which are linearly interpolated to 56 subcarriers by the host software, smoothing out true frequency-selective multipath dips.
4. **Packet Timing Jitter ($41.4\%$):** Inter-packet intervals exhibit a mean of $28.11\text{ ms}$ with standard deviation $\sigma = 11.64\text{ ms}$, introducing phase jitter into Doppler Short-Time Fourier Transforms (STFT).

---

## 2. Empirical Hardware Telemetry vs Training Baselines

```
+---------------------------------------------------------------------------------------------------------+
|                                    PHYSICAL DOMAIN GAP SCORECARD                                        |
+------------------------------+---------------------------+-----------------------+----------------------+
| Physical Parameter           | Widar 3.0 (Research NIC)  | NTU-Fi (Atheros NIC)  | ESP32-S3 (Commercial)|
+------------------------------+---------------------------+-----------------------+----------------------+
| Carrier Frequency (f_c)      | 5.825 GHz                 | 5.320 GHz             | 2.442 GHz (Ch 7)     |
| Carrier Wavelength (\lambda) | 5.15 cm                   | 5.64 cm               | 12.29 cm             |
| Hardware Sampling Rate (f_s) | 1,000 Hz                  | 100 Hz                | 35.58 Hz (Measured)  |
| Nyquist Limit (f_Nyquist)    | 500.0 Hz                  | 50.0 Hz               | 17.79 Hz (Measured)  |
| Max Unaliased Velocity (v_max)| 12.88 m/s (46.4 km/h)    | 1.41 m/s (5.1 km/h)   | 1.09 m/s (3.9 km/h)  |
| Antenna Streams (RX)         | 3 Antennas (Intel 5300)   | 3 Antennas (AR9580)   | 1 On-board Monopole  |
| Native Subcarriers           | 30 active (cubic interp)  | 114 (HT40 decimate)   | 5 raw -> 56 interp   |
| Inter-Packet Jitter (\sigma) | < 0.1 ms (< 0.1%)         | < 0.5 ms (< 5%)       | 11.64 ms (41.4%)     |
| Mean RSSI Level              | -42.0 dBm                 | -48.0 dBm             | -58.4 dBm            |
+------------------------------+---------------------------+-----------------------+----------------------+
```

![Phase 15 Domain Gap Analysis](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase15_domain_gap_analysis.png)

---

## 3. Detailed Physical Gap Analysis

### 3.1 Kinematic Doppler Shift Scaling & Spectral Aliasing
Human activity recognition relies on detecting the Doppler Frequency Shift ($f_D$) produced by torso and limb velocities ($v$):
$$f_D = \frac{2v}{\lambda} \cos \theta = \frac{2v f_c}{c} \cos \theta$$

1. **Carrier Frequency Discrepancy:**
   - In Widar 3.0 ($f_c = 5.825\text{ GHz}$), walking at $1.0\text{ m/s}$ generates $f_D \approx 38.8\text{ Hz}$.
   - In ESP32-S3 ($f_c = 2.442\text{ GHz}$), the exact same physical movement generates $f_D \approx 16.3\text{ Hz}$.
   - The scaling ratio is:
     $$\frac{f_{D, \text{Widar}}}{f_{D, \text{ESP32}}} = \frac{5.825}{2.442} = 2.385\times$$
   - A model trained on 5.8 GHz representations interprets a $16.3\text{ Hz}$ shift as a slow crawl ($0.42\text{ m/s}$) rather than a full walk ($1.0\text{ m/s}$).

2. **Nyquist Frequency Aliasing:**
   - With an effective sampling rate $f_s = 35.58\text{ Hz}$, the maximum frequency that can be represented without aliasing is:
     $$f_{\text{Nyquist}} = \frac{f_s}{2} = 17.79\text{ Hz}$$
   - Setting $f_D = 17.79\text{ Hz}$ gives the maximum observable human velocity:
     $$v_{\text{max}} = \frac{f_{\text{Nyquist}} \cdot \lambda}{2} = \frac{17.79 \times 0.1229}{2} = 1.09\text{ m/s}$$
   - **Critical Vulnerability for Fall Detection:** Human falls typically reach peak velocities of $2.0\text{ to }3.5\text{ m/s}$ as the torso descends toward the floor. At 2.442 GHz, a $2.5\text{ m/s}$ fall produces $f_D = 40.7\text{ Hz}$, which exceeds $17.79\text{ Hz}$ by $2.29\times$. This signal folds over (aliases) into the lower $5.1\text{ Hz}$ band, masquerading as a low-velocity gesture and causing fall misclassification.

### 3.2 Tone Truncation & Spatial Hallucination
In 802.11n HT20 mode, there are 56 active data subcarriers spanning a 20 MHz channel. In real multipath environments, different subcarriers experience constructive and destructive interference, creating a distinct "frequency-selective fading" signature across the 56 tones.
- The current ESP32-S3 firmware outputs only 5 physical subcarrier tones per packet.
- When `RealCSICollector` interpolates 5 points into 56 points, the resulting amplitude profile is a smooth piece-wise linear curve (visible in Panel B of `reports/phase15_domain_gap_analysis.png`).
- While this $[1, 50, 56]$ tensor passes shape validation in PyTorch, it lacks the fine-grained spatial multipath dips that CSIFormer's self-attention layers expect.

### 3.3 Timestamp Jitter & STFT Window Distortion
In research testbeds, NICs utilize hardware packet generators with microsecond-level timing accuracy ($\sigma < 0.1\text{ ms}$). 
On the ESP32-S3 under commercial Wi-Fi operation:
- Mean $\Delta t = 28.11\text{ ms}$
- Standard deviation $\sigma_{\Delta t} = 11.64\text{ ms}$ ($41.4\%$ relative jitter)
- Non-uniform sampling introduces spurious sidebands into the Short-Time Fourier Transform (STFT), corrupting the Doppler spectrogram with high-frequency phase noise.

---

## 4. Analytical Conclusions & Domain Adaptation Requirements

Direct feeding of raw ESP32-S3 CSI into the unchanged Phase 13 `CSIDualBranchFusionNet` checkpoint is mathematically bound to suffer severe domain degradation due to:
1. Velocity scaling compression ($2.385\times$).
2. Doppler spectral aliasing on rapid gestures and falls ($v > 1.09\text{ m/s}$).
3. Spatial frequency smoothing from 5-tone interpolation.

### Necessary Adaptation Remedies for Stage 5:
- **Remedy 1 (Doppler Frequency Normalization):** Rescale the Doppler DFS frequency axis by the inverse carrier ratio ($2.385\times$) prior to STFT feature extraction.
- **Remedy 2 (Temporal Equispaced Resampling):** Resample non-uniform timestamp intervals onto a strictly uniform temporal grid using cubic spline interpolation before computing Fourier transforms.
- **Remedy 3 (Fine-Tuning on Real Data):** Adapt the fusion projection and classification head on the newly captured real-world dataset.
