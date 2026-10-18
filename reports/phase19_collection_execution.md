# CSIFormer Phase 19 — Physical Collection Campaign Execution & Operator Protocol

## Executive Summary

**CSIFormer Phase 19** implements and audits an evidence-based physical data acquisition workflow for expanding real-world ESP32-S3 Channel State Information (CSI) collections. In strict accordance with the project directives, **no model training or fine-tuning was performed, and no physical recordings or hardware results were fabricated**.

This document provides:
1. **Physical Acquisition Infrastructure Audit:** Technical specifications of the serial stream, active UDP stimulation, and raw subcarrier extraction.
2. **Data Preservation & Anti-Corruption Controls:** Non-destructive overwrite protection, separate raw vs. interpolated storage, and quarantine isolation.
3. **Operator Execution Protocol:** Step-by-step checklist, exact terminal commands, and trial confirmation/rejection criteria.
4. **Protective Fall Safety Directives:** Mandatory equipment, breakfall standards, spotter supervision, and immediate postponement rules.
5. **Physical Data Accounting Table:** Baseline vs. Newly Added vs. Current Verified vs. Deficits against Phase 19 pilot targets.

---

## 1. Physical Acquisition Architecture & Signal Path

### 1.1 Hardware Node & Radio Baseline
- **Hardware Receiver:** ESP32-S3 (ESP32-S3-WROOM-1, 16 MB Flash, 8 MB Octal PSRAM).
- **Transport Bridge:** USB-to-UART bridge (WCH CH343) on serial port `COM5` at 115,200 baud, 8N1.
- **RF Radio Mode:** 802.11n HT20, 2.442 GHz (Channel 7).
- **Associated Access Point:** SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`.
- **Active UDP Stimulator:** Background socket engine transmitting 13-byte probes (`CSI_PROBE_P17`) to `192.168.0.232:5555` at 35.0 Hz to sustain high packet arrival rates.

### 1.2 Raw Measurements vs. Model Features
- **Raw Measurements (`raw_amplitudes` & `raw_phases`):** Parsed directly from hardware packets. Length $N_{\text{raw}}$ reflects actual firmware output (e.g. 64 subcarriers for 128-byte raw IQ Format A, or $N_{\text{sc}}$ from Format B header). The system never artificially relabels interpolated features as raw physical data.
- **Model Features (`amplitudes` & `phases`):** 1D linearly interpolated representation mapped to exactly 56 channels to match the input layer of the production CSIFormer model.
- **Metadata Documentation:** Explicitly logged as `subcarrier_alignment_method: "linear_interpolation_to_56"`.

---

## 2. Fortified Collection Controls

### 2.1 Accidental Overwrite Protection
In [`backend/app/services/real_csi_collector.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py), the storage handler inspects whether `json_path` already exists prior to writing. If an existing session with the same identifier is detected on disk, the system automatically appends an incremented revision suffix (`_v1`, `_v2`, etc.) rather than overwriting historical files:
```python
base_id = session_id
counter = 1
json_path = self.data_dir / f"{session_id}.json"
while json_path.exists():
    session_id = f"{base_id}_v{counter}"
    json_path = self.data_dir / f"{session_id}.json"
    counter += 1
```

### 2.2 Automated Quarantine Workflow
In [`backend/app/services/session_validator.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py), any recording that contains non-finite values (NaN, Inf), truncated frame arrays, corrupted JSON syntax, or unconfirmed labels masquerading as valid classes is automatically moved to `data/real_csi_dataset/quarantine/` alongside an audited `quarantine_manifest.json` documenting the exact reason for rejection. Corrupted files are never silently repaired.

### 2.3 Explicit Label Confirmation
Every trial requires post-capture operator verification:
- Confirmed trials retain the designated activity label and class ID.
- Unconfirmed, interrupted, or ambiguous trials are strictly labeled as `"unknown"` (Class ID `-1`).

---

## 3. Operator Execution Protocol & Checklist

Operators collecting physical data on the ESP32-S3 testbed must follow this sequence:

### Step 1: Pre-Flight Hardware Verification
Execute the automated link check before positioning participants:
```powershell
py -3.11 scratch/run_collection_session.py --verify --port COM5
```
*Pass Criteria:* Status `OK`, packet arrival rate $\ge 30.0$ Hz, mean RSSI between $-50$ and $-65$ dBm.

### Step 2: Environmental & Geometric Setup
Record the physical room layout, Tx/Rx coordinates, and distance:
- Short-range baseline: 1.5 meters
- Nominal baseline: 2.5 meters
- Extended baseline: 3.5 / 4.5 meters
Position Tx and Rx antennas 1.0 meter above the floor facing the movement zone.

### Step 3: Standard Movement Trial Execution
Execute trial collection using the standardized CLI:
```powershell
py -3.11 scratch/run_collection_session.py `
  --activity walk `
  --participant Participant_03 `
  --duration 4.0 `
  --room Laboratory `
  --distance 2.5 `
  --tx-pos "Tx_Corner_A" `
  --rx-pos "Rx_Desk_B" `
  --confirm
```

### Step 4: Supervised Padded-Mat Fall Trial Execution
For fall trials, execute the trial strictly on certified crash padding:
```powershell
py -3.11 scratch/run_collection_session.py `
  --activity fall `
  --participant Participant_03 `
  --duration 4.0 `
  --room Laboratory `
  --distance 2.5 `
  --tx-pos "Tx_Corner_A" `
  --rx-pos "Rx_Desk_B" `
  --notes "Certified 4-inch crash mat forward breakfall" `
  --confirm
```

---

## 4. Mandatory Fall Safety Directives

> [!CAUTION]
> **LIFE-SAFETY MANDATE FOR EXPERIMENTAL FALL SENSING**
> 
> Collecting physical human fall data carries risk of injury if safety rules are violated. The following protocols are strictly mandatory:
> 1. **High-Density Protective Mat:** Every fall trial must take place onto a certified gymnastics or martial arts crash mat of **at least 4 inches (10 cm) thickness**.
> 2. **Never Drop on Unpadded Floors:** Falls onto concrete, hardwood, tile, or thin carpet are **strictly prohibited**.
> 3. **Competent Spotter Required:** At least two adults (participant + designated spotter) must be present. The spotter must remain within arm's reach of the mat.
> 4. **Controlled Breakfalls Only:** Participants must be instructed in controlled breakfall mechanics (tucking chin to prevent whiplash, slapping mat with open forearms to disperse impact energy). Falls landing on the head, neck, spine, or locked wrists are strictly forbidden.
> 5. **Uncoerced Consent & Stop Authority:** Participants must provide informed consent and have the absolute authority to halt or refuse fall trials at any moment.
> 6. **Mandatory Postponement Rule:** If certified crash mats, competent spotters, or consenting participants are unavailable, fall collection **must be postponed**. The campaign must prioritize non-fall activities (walking, sitting, standing, pushing/pulling).

---

## 5. Physical Data Accounting Table: Baseline vs. Targets

Every metric in the table below is derived from audited physical files on disk in `data/real_csi_dataset/`:

| Milestone Metric | Phase 18 Baseline | Newly Added (Phase 19) | Current Verified Total | Phase 19 Pilot Target | Remaining Deficit | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Physical Sessions** | 23 | 0 | **23 sessions** | $\ge 50$ | **-27** | Pending Physical Collection |
| **Physical Packets** | 3,212 | 0 | **3,212 packets** | $\ge 10,000$ | **-6,788** | Pending Physical Collection |
| **Valid Windows (50 frames)** | 49 | 0 | **49 windows** | $\ge 150$ | **-101** | Pending Physical Collection |
| **Distinct Participants** | 2 | 0 | **2 subjects** | $\ge 5$ | **-3** | Barrier ($N=2$) |
| **Physical Rooms** | 1 | 0 | **1 room** | $\ge 3$ | **-2** | Domain Gap |
| **Tx-Rx Distances** | 1 | 0 | **1 distance (2.5m)** | $\ge 3$ | **-2** | Domain Gap |
| **Held-Out Test Fall Windows** | 4 | 0 | **4 windows** | $\ge 35$ | **-31** | **Critical Deficit (-77.5%)** |
| **Held-Out Test Fall Events** | 2 | 0 | **2 events** | $\ge 12$ | **-10** | **Critical Deficit (-83.3%)** |
| **Packet Sampling Rate** | 35.6 Hz | — | **35.6 Hz** | $\ge 30$ Hz | 0 | **Target Met** |
| **Packet Loss Rate** | 1.2% | — | **1.2%** | $< 5.0\%$ | 0 | **Target Met** |

### Evidence Reference:
- Verified Primary Manifest: [`data/real_csi_dataset/dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json)
- Verified LOSO Partition: [`data/real_csi_dataset/dataset_manifest_p17_loso.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest_p17_loso.json)
- Total Verified Session Files: 23 indexed files + 1 unindexed aborted run (`phase14_p15_real_walk_t1_1792303844_1792303844.json`).

### Transparent Declaration:
No new physical recordings were fabricated or simulated to artificially satisfy milestones. The software acquisition infrastructure and validation engine are complete; physical hardware collection across new participants and environments remains the sole prerequisite for Phase 20 model evaluation.
