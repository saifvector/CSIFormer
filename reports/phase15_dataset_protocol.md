# CSIFormer Phase 15 — Real-World CSI Dataset Protocol & Acquisition Specification

**Document Version:** 1.0.0  
**Date:** October 18, 2026  
**Dataset Identifier:** `CSIFormer_Phase15_Real_ESP32S3_CSI_Dataset`  
**Storage Directory:** [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/)  
**Dataset Manifest:** [`data/real_csi_dataset/dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json)  
**Total Validated Sessions:** 23 sessions (3,212 real physical frames)

---

## 1. Executive Summary

Phase 15 establishes an empirical, immutable, and leak-resistant real-world dataset collected directly from the physical ESP32-S3 hardware. 

To overcome the low ambient beacon rate (~2–5 Hz) discovered during the Phase 14 reproducibility audit, Phase 15 introduces an **Active UDP Probe Stimulation Workflow**:
- The host laptop transmits lightweight probe packets (`b'CSI_PROBE_P15'`) at a calibrated 35.0 Hz frequency to the ESP32-S3's IP address (`192.168.0.232:5555`).
- Each incoming probe stimulates an immediate hardware CSI interrupt and callback in the ESP32-S3 MAC layer.
- The resulting physical CSI OFDM frames are streamed over USB Serial (`COM5` @ 115200 baud) to the host in real time, achieving a sustained capture rate of **35.0 to 40.0 Hz**.

---

## 2. Experimental Environment & RF Setup

```
+--------------------------------------------------------------------------------------------------+
|                                    RF & HARDWARE SPECIFICATIONS                                  |
+--------------------------+-----------------------------------------------------------------------+
| Hardware Node            | ESP32-S3 (Xtensa LX7 dual-core 240 MHz, 512 KiB SRAM, 16 MB Flash)    |
| USB-UART Bridge          | WCH CH343 High-Speed Serial Interface (Windows Port: COM5)            |
| Baud Rate                | 115,200 bps                                                           |
| Access Point SSID        | Tp link                                                               |
| Access Point BSSID       | 98:ba:5f:ef:28:26                                                     |
| Operating Band           | 2.4 GHz ISM Band (802.11b/g/n, HT20)                                  |
| Operating Channel        | Channel 7 (Center Frequency f_c = 2.442 GHz)                          |
| RSSI Level               | -56.0 dBm to -60.0 dBm (Stable high-SNR line of sight)                |
| Room Environment         | Laboratory_Room1 (4.5 m x 3.5 m x 2.8 m)                              |
| Tx-Rx Distance           | 2.5 meters line-of-sight                                              |
| Antenna Orientation      | Fixed omnidirectional monopole on board                               |
+--------------------------+-----------------------------------------------------------------------+
```

---

## 3. Data Representation & Storage Formats

Raw physical recordings are kept strictly immutable in [`data/real_csi_dataset/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/):

### 3.1 Raw JSON Frame Schema (`.json`)
Each session is stored as a self-describing JSON payload containing complete session metadata alongside raw per-packet arrays:
```json
{
  "metadata": {
    "session_id": "phase14_p15_real_walk_t1_1792303867_1792303867",
    "timestamp_utc": "2026-10-18T06:11:07Z",
    "room_type": "Laboratory",
    "room_dimensions_xyz_meters": [4.5, 3.5, 2.8],
    "tx_rx_distance_meters": 2.5,
    "participant_id": "Participant_01",
    "ground_truth_activity": "walk",
    "hardware": {
      "board": "ESP32-S3 (Xtensa LX7)",
      "uart_bridge": "CH343",
      "port": "COM5",
      "baud_rate": 115200,
      "protocol": "raw_iq_stream"
    },
    "rf_config": {
      "channel": 7,
      "frequency_ghz": 2.442,
      "bandwidth_mode": "HT20",
      "subcarriers": 56
    }
  },
  "frame_count": 146,
  "frames": [
    {
      "timestamp": 1792303867.42,
      "sequence": 1,
      "rssi": -58.0,
      "noise": -95.0,
      "amplitudes": [17.46, 16.23, ...],
      "phases": [0.865, 0.742, ...]
    }
  ]
}
```

### 3.2 Tabular CSV Format (`.csv`)
For rapid matrix loading and numerical inspection, each session produces a matching CSV file:
- Columns: `timestamp`, `sequence`, `rssi`, `noise`, `amp_0`, `amp_1`, ..., `amp_55`.

---

## 4. Activity Classes & Experimental Protocol

The acquisition protocol covers 6 core activities mapped directly to the CSIFormer 12-class ontology:

```
+---------------------------------------------------------------------------------------------------------+
|                                    DATASET ACTIVITY COMPOSITION                                         |
+-------------+----------+-----------------------------+----------+---------------+-----------------------+
| Label       | Class ID | Kinematic Description       | Trials   | Dur / Trial   | Life-Safety Critical  |
+-------------+----------+-----------------------------+----------+---------------+-----------------------+
| walk        | 11       | Normal human gait along LOS | 4 trials | 4.0 seconds   | No (HAR Standard)     |
| fall        | 9        | Rapid downward torso fall   | 4 trials | 4.0 seconds   | YES (Zero FN Target)  |
| sit         | 8        | Stand-to-chair transition   | 4 trials | 4.0 seconds   | No (HAR Standard)     |
| clap        | 2        | Repetitive two-hand clap    | 4 trials | 4.0 seconds   | No (Gesture Standard) |
| push_pull   | 0        | Arm extension and push/pull | 4 trials | 4.0 seconds   | No (Gesture Standard) |
| static      | 6        | Empty room / stationary     | 3 trials | 3.0 seconds   | No (Baseline Floor)   |
+-------------+----------+-----------------------------+----------+---------------+-----------------------+
| Total       | -        | 6 Balanced Physical Classes | 23 trials| ~89.0 seconds | 3,212 Real Frames     |
+-------------+----------+-----------------------------+----------+---------------+-----------------------+
```

---

## 5. Leakage-Resistant Dataset Partitioning

To guarantee absolute scientific integrity and prevent temporal data leakage:
- **No Overlapping Window Leakage:** Train, validation, and test splits are partitioned **by independent recording session/trial**, NEVER by randomly slicing sliding windows from the same continuous recording.
- **Participant Rotation:** Trials alternate between privacy-preserving identifiers `Participant_01` and `Participant_02`.
- **Split Breakdown:**
  - **Training Split (52.2%):** Trials 1 & 2 of all activities (12 sessions, 1,675 frames).
  - **Validation Split (26.1%):** Trial 3 of all activities (6 sessions, 846 frames).
  - **Held-Out Test Split (21.7%):** Trial 4 of all dynamic activities (5 sessions, 691 frames).

```
+--------------------------------------------------------------------------------------------------+
|                                    DATASET SPLIT SUMMARY                                         |
+-------------------+--------------------+--------------------+------------------------------------+
| Split Name        | Sessions Count     | Total Frames       | Activity Classes Included          |
+-------------------+--------------------+--------------------+------------------------------------+
| train             | 12 sessions        | 1,675 frames       | walk, fall, sit, clap, push, static|
| val               | 6 sessions         | 846 frames         | walk, fall, sit, clap, push, static|
| test (held-out)   | 5 sessions         | 691 frames         | walk, fall, sit, clap, push        |
+-------------------+--------------------+--------------------+------------------------------------+
| Combined Total    | 23 sessions        | 3,212 frames       | 100% Real Physical Hardware Frames |
+-------------------+--------------------+--------------------+------------------------------------+
```

All 23 sessions are fully indexed in [`data/real_csi_dataset/dataset_manifest.json`](file:///c:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json).
