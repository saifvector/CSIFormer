# CSIFormer Phase 17 — Comprehensive Audit of Current Collection Workflow

**Document Version:** 1.0.0  
**Audit Date:** October 18, 2026  
**Auditor:** Principal Wireless Sensing Research Scientist & Lead Agent  
**Status:** **AUDITED & EMPIRICALLY GROUNDED**

---

## 1. Executive Summary

Phase 17 conducted an audit of the live ESP32-S3 CSI collection pipeline, the physical dataset stored in `data/real_csi_dataset/`, the firmware source code in `firmware/esp32s3_csi_collector/main/main.c`, and the serial receiver logic in `backend/app/services/real_csi_collector.py`.

### Primary Audit Findings

1. **Physical Files vs. Manifest Discrepancy:**
   - Manifest `data/real_csi_dataset/dataset_manifest.json` indexes **23 sessions (3,212 frames)**.
   - Physical disk contains **24 session JSON files** (+ manifest = 25 JSON files total).
   - The unindexed file is `phase14_p15_real_walk_t1_1792303844_1792303844.json` (147 frames, recorded at 06:10:44Z), which was an initial walk trial superseded 23 seconds later by trial `phase14_p15_real_walk_t1_1792303867_1792303867.json`.
2. **Historical Raw CSI Preservation Gap:**
   - In the 23 historical Phase 15 recordings, **zero session files contain `raw_amplitudes` or `raw_phases`**.
   - These legacy sessions only saved the $[56]$ interpolated arrays under the `"amplitudes"` key.
   - In Phase 16, `backend/app/services/real_csi_collector.py` was enhanced to record `raw_amplitudes` $[5]$, `raw_phases` $[5]$, and `raw_num_subcarriers` alongside the aligned features, but this applies only to recordings moving forward.
3. **Firmware & Hardware Sampling Reality:**
   - Pre-flashed ESP32-S3 firmware outputs 5 interleaved IQ pairs (10 comma-separated integers) in Format A:
     `RSSI=-61 LEN=128 CSI:r0,im0,r1,im1,r2,im2,r3,im3,r4,im4`
   - The Python receiver linearly interpolates these 5 measurements to 56 subcarriers via `np.interp`. This erases genuine frequency-selective multipath fading profiles across the $20\text{ MHz}$ HT20 channel.
4. **Participant Distribution in Current Dataset:**
   - Exactly two participants (`Participant_01` and `Participant_02`) exist across the 23 sessions.
   - `Participant_01`: 12 sessions (1,570 frames, 25 windows)
   - `Participant_02`: 11 sessions (1,642 frames, 24 windows)
   - With only 2 participants, a 3-way split (Train / Val / Test) that is strictly participant-independent is mathematically impossible without at least 3 participants!

---

## 2. Inventory of Current Physical Recordings

```
Physical Files on Disk:    24 session JSON files, 24 session CSV files
Indexed in Manifest:       23 session JSON files, 23 session CSV files
Unindexed Files:           1 session JSON/CSV (p15_real_walk_t1_1792303844)
Total Packets (Indexed):   3,212 packets
Total Packets (All Files): 3,359 packets
Total Extracted Windows:   49 non-overlapping [50, 56] windows (indexed)
```

### Complete Class & Participant Breakdown of Indexed Data:

| Activity Label | Model Class ID | Total Sessions | Total Packets | Non-Overlapping Windows | `Participant_01` Windows | `Participant_02` Windows |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **push_pull** | 0 | 4 | 578 | 9 | 5 | 4 |
| **clap** | 2 | 4 | 579 | 8 | 4 | 4 |
| **static** | 6 | 3 | 309 | 5 | 3 | 2 |
| **sit** | 8 | 4 | 595 | 10 | 5 | 5 |
| **fall** | 9 | 4 | 561 | 8 | 4 | 4 |
| **walk** | 11 | 4 | 590 | 9 | 4 | 5 |
| **Total** | -- | **23** | **3,212** | **49** | **25** | **24** |

---

## 3. Signal Representation & Interpolation Audit

### 3.1 The 5-to-56 Subcarrier Linear Ramp:
- Hardware packet: 5 complex values $(I_0, Q_0), \dots, (I_4, Q_4)$.
- Measured amplitude: $A_k = \sqrt{I_k^2 + Q_k^2}$, Phase: $\Phi_k = \text{atan2}(Q_k, I_k)$.
- Software interpolation:
  $$A_{\text{aligned}}(j) = \text{interp}\left(j, \{0, 13.75, 27.5, 41.25, 55\}, \{A_0, A_1, A_2, A_3, A_4\}\right)$$
- **Impact on Neural Network:**
  - In real 802.11n Wi-Fi, 56 subcarriers carry independent multipath fading parameters reflecting room geometry.
  - Feeding a 5-point piecewise linear ramp into convolutional filters trained on 56 independent channels severely attenuates high-frequency spatial gradients, causing the model's spatial attention heads to degrade to a coarse power detector.

### 3.2 Measurement Storage Audit:
- **Phase 15 Sessions:** Stored only interpolated `amplitudes` ($[56]$). The original 5 values cannot be perfectly recovered.
- **Phase 16 Upgrade:** Enhanced `real_csi_collector.py` to record:
  ```json
  {
    "raw_amplitudes": [10.2, 12.5, 14.1, 13.8, 11.2],
    "raw_phases": [0.12, 0.45, -0.22, 0.81, -0.05],
    "raw_num_subcarriers": 5,
    "amplitudes": [... 56 values ...],
    "phases": [... 56 values ...],
    "num_subcarriers": 56
  }
  ```
  This satisfies the Stage 1 requirement that raw measurements are preserved alongside derived representations.

---

## 4. Participant-Independent Split Impossibility with N=2 Participants

A rigorous participant-independent evaluation requires:
1. **Train Split:** Contains only participants $\mathcal{P}_{\text{train}}$.
2. **Validation Split:** Contains only participants $\mathcal{P}_{\text{val}}$, where $\mathcal{P}_{\text{val}} \cap \mathcal{P}_{\text{train}} = \emptyset$.
3. **Held-Out Test Split:** Contains only participants $\mathcal{P}_{\text{test}}$, where $\mathcal{P}_{\text{test}} \cap (\mathcal{P}_{\text{train}} \cup \mathcal{P}_{\text{val}}) = \emptyset$.

**The Mathematical Barrier:**
$$|\mathcal{P}_{\text{total}}| = |\{\text{Participant\_01}, \text{Participant\_02}\}| = 2$$
To partition into 3 disjoint non-empty sets:
$$|\mathcal{P}_{\text{train}}| \ge 1, \quad |\mathcal{P}_{\text{val}}| \ge 1, \quad |\mathcal{P}_{\text{test}}| \ge 1 \implies |\mathcal{P}_{\text{total}}| \ge 3$$

Because the dataset currently has only 2 participants, **it is mathematically impossible to construct 3 participant-independent splits without either:**
- Eliminating the validation set (leaving only a 2-way Train/Test split: Train on P1, Test on P2, or vice versa).
- Expanding the dataset to include at least a 3rd participant (`Participant_03`) so that Train = {P1}, Val = {P2}, Test = {P3}, or Train = {P1, P2}, Val = {P3}, Test = {P4}.

This audit confirms that before any participant-independent validation can occur, a reproducible collection workflow and split generator must enforce this requirement and explicitly reject invalid 3-way split configurations.
