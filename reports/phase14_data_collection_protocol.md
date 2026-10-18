# CSIFormer Phase 14.1 — Real-World CSI Data Collection Protocol

**Document Version:** 1.0.0  
**Status:** APPROVED & OPERATIONAL  
**Target Microcontroller:** Espressif ESP32-S3 (Xtensa LX7 Dual-Core, 2.4 GHz 802.11b/g/n)  
**Host Ingestion System:** Windows Laptop via High-Speed USB Serial (`COM5`, CH343 Bridge) / UDP Broadcast  

---

## 1. Physical Hardware & RF Transceiver Setup

### 1.1 Node Geometry & Antenna Configuration
- **Transmitter (TX):** Commercial Wi-Fi Access Point (TP-Link Dual-Band 802.11ac/n router).
  - Operating Frequency: **2.442 GHz (Channel 7)**.
  - Bandwidth: **HT20 (20 MHz)**.
  - Antenna Polarization: Vertical dipole ($\lambda \approx 12.28\text{ cm}$).
  - TX Power: Standard +20 dBm EIRP.
- **Receiver (RX):** ESP32-S3 development board (`d4:05:92:7b:2e:d0`).
  - RF Frontend: On-board 2.4 GHz PCB antenna with matching network.
  - Receiver Sensitivity: -98 dBm (1 Mbps 802.11b), -75 dBm (MCS7 HT20).
  - Height Above Ground: **1.0 m to 1.2 m** (standard torso/waist height to maximize kinematic limb scattering).
  - TX-RX Separation: **2.0 m to 5.0 m** Line-of-Sight (LOS) with documented Non-Line-of-Sight (NLOS) tests.

```
       [ Wi-Fi Router (TX) ]
       Channel 7 (2.442 GHz)
              │
              │   Direct Path (LOS)
              ▼~~~~~~~~~~~~~~~~~~~~~~~► [ ESP32-S3 (RX) ]
             / \                          Connected to Laptop
            /   \ Multipath Reflected     via USB Serial (COM5)
           /     \ from Human Body
          ▼       ▼
     [ Human Participant ]
     (Walking, Falling, Gestures)
```

---

## 2. Multi-Room Environmental Classification Taxonomy

Every data collection session must be tagged with one of the five standardized environmental categories:

| Room Type | Dimensions ($L \times W \times H$) | Multipath Clutter Level | Surface Materials | Dominant Reflection Characteristics |
| :--- | :---: | :---: | :--- | :--- |
| **Bedroom** | $4.0\text{ m} \times 3.5\text{ m} \times 2.8\text{ m}$ | High (Damped) | Drywall, wooden bed frame, mattress/fabric | High absorption of high-frequency components; strong static bed reflections. |
| **Office** | $6.0\text{ m} \times 4.5\text{ m} \times 3.0\text{ m}$ | High (Metallic) | Concrete walls, steel desks, swivel chairs | Strong specular reflections from metal surfaces; dynamic clutter from moving chairs. |
| **Laboratory** | $8.0\text{ m} \times 7.0\text{ m} \times 3.5\text{ m}$ | Moderate (Open) | Tile floor, electronic test benches, glass | Long multipath delay spreads ($> 80\text{ ns}$); wide Fresnel zone coverage. |
| **Apartment** | $5.0\text{ m} \times 4.0\text{ m} \times 2.7\text{ m}$ | Dense (Living Area) | Reinforced concrete walls, sofa, TV unit | Cavity resonance in enclosed space; through-wall signal attenuation. |
| **Benchmark** | $5.0\text{ m} \times 5.0\text{ m} \times 3.0\text{ m}$ | Controlled | Anechoic/semi-controlled laboratory | Direct baseline comparison against Widar 3.0 university hall settings. |

---

## 3. Participant Metadata & Biometric Annotation

To resolve whether performance drops arise from biometric morphology (height, weight, body shape) versus room multipath, every trial records:

```json
{
  "participant_id": "User-05",
  "height_cm": 174.5,
  "weight_kg": 68.0,
  "gender": "Male",
  "age_group": "20-25",
  "torso_depth_cm": 22.0,
  "clothing_type": "Standard cotton shirt & denim"
}
```

---

## 4. Telemetry Format & Timestamp Synchronization

### 4.1 Packet Ingestion Streams
The acquisition engine (`RealCSICollector`) supports two validated packet structures:
1. **Raw IQ Callback Stream (Format A):**
   ```
   === CSI CALLBACK FIRED ===
   RSSI=<int> LEN=128 CSI:<I_0>,<Q_0>,<I_1>,<Q_1>,...
   ```
2. **Structured CSI Telemetry Stream (Format B):**
   ```
   CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,<amp_0>:<phase_0>,<amp_1>:<phase_1>,...
   ```

### 4.2 Synchronization & Timing Precision
- **Hardware Timestamping:** Microsecond timestamp attached on frame arrival.
- **Target Sampling Rate:** **30.0 Hz** continuous ($\Delta t \approx 33.3\text{ ms}$).
- **Sequence Continuity:** Monotonically increasing sequence ID ($S_k$).
- **Packet Loss Detection:**
  $$\text{Loss Rate (\%)} = \frac{\sum \max(0, S_{k} - S_{k-1} - 1)}{\text{Total Packets}} \times 100$$
- **Jitter Formulation:**
  $$\text{Jitter}_k = 0.9 \cdot \text{Jitter}_{k-1} + 0.1 \cdot |\Delta t_k - 33.3\text{ ms}|$$

---

## 5. Storage Schema & Data Serialization

All sessions are persisted under [`data/recordings/`](file:///c:/Users/saifu/Desktop/4-1%20project/data/recordings) with twin files:

1. **Structured Session Archive (`.json`):**
   Contains complete room metadata, hardware identifiers, participant biometrics, and the chronological array of 56-subcarrier frames.
2. **Tabular Telemetry Log (`.csv`):**
   Header: `timestamp,sequence,rssi,noise,amp_0..amp_55` for high-throughput vectorized Pandas/NumPy analysis.
