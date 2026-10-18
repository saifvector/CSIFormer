# CSIFormer Phase 17 — Standardized Real-World CSI Collection Protocol

## Executive Summary

Phase 17 establishes an audited, standardized, and reproducible physical CSI data collection protocol for the CSIFormer project. Following the findings of the Phase 16 evaluation and Phase 17 collection audit—which identified severe participant leakage (only 2 participants in the legacy dataset) and zero raw subcarrier preservation in historical recordings—this protocol formalizes an end-to-end procedure designed to expand real-hardware dataset coverage while enforcing participant privacy, raw measurement preservation, and strict physical fall safety.

---

## 1. Hardware Architecture & Signal Path

### 1.1 Radio & Transceiver Specifications
- **Receiver (Rx):** ESP32-S3 (ESP32-S3-WROOM-1, 16 MB Flash, 8 MB Octal PSRAM).
- **Firmware:** ESP-IDF v5.x Wi-Fi CSI collector (`firmware/esp32s3_csi_collector/main/main.c`).
- **Antenna:** Integrated PCB 2.4 GHz inverted-F antenna.
- **Operating Channel:** Channel 7 (Center frequency: 2.442 GHz, 802.11n HT20).
- **Target AP:** SSID `Tp link`, BSSID `98:ba:5f:ef:28:26`.
- **Interface / Transport:** USB-to-UART bridge (WCH CH343 / Virtual COM Port), baud rate: 115,200 baud, 8N1.

### 1.2 Active Traffic Stimulation Engine
Because 802.11n Wi-Fi CSI callbacks on the ESP32-S3 are packet-triggered, passive listening on an idle router yields unpredictable, bursty packet rates (<5 Hz to 12 Hz). To achieve a sustained, statistically reliable sampling rate matching the CSIFormer input window (50 Hz nominal, $\ge 35$ Hz sustained), the collection pipeline incorporates an active UDP stimulator:
- **Target IP / Port:** `192.168.0.232:5555` (unicast to the receiver node on local LAN).
- **Probe Payload:** `CSI_PROBE_P17` (13 bytes UDP).
- **Pulse Rate:** 35.0 pulses per second (interval: 28.57 ms).
- **Subcarrier Resolution:** 52 physical data/pilot subcarriers (LLTF/HT-LTF) mapped to 56 CSIFormer model channels.

---

## 2. Participant Privacy & Pseudonymization

To prevent inadvertent leakage of Personally Identifiable Information (PII) and maintain compliance with observational sensing standards:
1. **Identifier Format:** All subjects are assigned a non-reversible, zero-indexed or padded identifier (e.g., `Participant_01`, `Participant_02`, `Participant_03`).
2. **Metadata Separation:** Demographic or physical notes (height, shoe type, clothing) must only record relative RF attenuation characteristics (e.g., "winter jacket vs light cotton shirt") without names, facial records, or personal contact information.
3. **Storage Boundary:** All recordings are stored locally under `data/real_csi_dataset/`. No biometric identifiers or physical participant photos are committed to version control.

---

## 3. Standard Activity Taxonomy & Label Mapping

The collection pipeline enforces the 6-activity taxonomy established in Phase 13/Phase 14, mapped to model class IDs:

| Activity Label | Class ID | Taxonomy Name | Description & Standard Movement Protocol |
| :--- | :---: | :--- | :--- |
| `push_pull` | 0 | Push and Pull | Participant stands in LOS baseline, pushing and pulling both arms horizontally at chest level (1.0 Hz cadence). |
| `clap` | 2 | Two-Hand Clapping | Participant stands facing Tx-Rx line, rhythmically clapping hands at torso height (~2.0 Hz cadence). |
| `static` | 6 | Static / Background | Room is empty or participant remains motionless in LOS for background RF baseline calibration. |
| `sit` | 8 | Sitting Transition | Participant begins standing, lowers deliberately into a standard office chair, and sits stationary. |
| `fall` | 9 | Controlled Padded Fall | Controlled, forward or lateral drop onto a certified 4-inch gymnastics crash mat under spotter supervision. |
| `walk` | 11 | Walking in LOS | Participant walks at natural pace (1.0–1.3 m/s) along a 3-meter path bisecting the Tx-Rx RF baseline. |
| `unknown` | -1 | Ambiguous / Unconfirmed | Any trial where the operator rejects ground truth or movement was interrupted/malformed. |

> [!IMPORTANT]
> Unconfirmed or ambiguous recordings must **always** remain labeled as `unknown` (Class ID `-1`). Under no circumstances should unconfirmed trials be converted into valid activity labels or synthetic data.

---

## 4. End-to-End Collection Procedure (Reproducible 8 Steps)

The collection workflow is implemented via [`backend/app/services/collection_workflow.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) and executable through [`scratch/run_collection_session.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py).

### Step 1: Pre-Flight Hardware & Stream Verification
Verify the ESP32-S3 serial stream before positioning the participant:
```powershell
py -3.11 scratch/run_collection_session.py --verify --port COM5
```
*Expected Output:* Status `OK`, packet rate $\ge 30.0$ Hz, Mean RSSI between $-50$ and $-65$ dBm.

### Step 2: Participant & Environmental Setup
1. Record room type (e.g., `Laboratory`, `Office_Room_B`).
2. Measure and record Tx-Rx baseline distance (standard: 2.5 meters).
3. Position participant at designated distance and orientation (e.g., `LOS_Facing_TxRx`, `NLOS_Behind_Drywall`).

### Step 3: Activity & Duration Selection
Select the target activity from `VALID_LABELS` and set standard capture duration (4.0 seconds nominal = 140–160 packets = $\approx 3$ non-overlapping 50-packet sliding windows).

### Step 4: Trial Initiation
Execute capture via the CLI:
```powershell
py -3.11 scratch/run_collection_session.py --activity walk --participant Participant_03 --duration 4.0 --notes "Shoes on, clear path"
```
The command automatically engages UDP stimulation, creates the unique session timestamp, and streams frames into the active buffer.

### Step 5: Raw Measurement & Packet-Loss Accounting
Each received CSI frame captures:
- `timestamp_us`: Microsecond hardware counter from ESP32-S3 system clock.
- `sequence_number`: Monotonically increasing packet sequence ID to detect dropped frames.
- `rssi`: Received signal strength indication (dBm).
- `raw_amplitudes`: List of 52 raw subcarrier amplitudes without interpolation or filtering.
- `amplitudes`: Normalized 56-subcarrier array for CSIFormer ingestion.
- `phase`: Raw subcarrier phase angles ($\text{atan2}(Q, I)$).

### Step 6: Post-Capture Confirmation / Rejection
Immediately upon completion, the operator verifies trial validity:
- If movement was clean and matched timing: confirm ground truth (`y`).
- If participant stumbled, hesitated, or external interference occurred: reject (`n`). The recording will be stored with `ground_truth_confirmed=False` and activity `unknown`.

### Step 7: Manifest Update & Cryptographic Integrity Check
Confirmed sessions are automatically appended to `data/real_csi_dataset/dataset_manifest.json` with frame counts, sampling rate, RSSI, and session paths.

### Step 8: Multi-Trial Repetition
Repeat steps 3–7 for a minimum of 5 trials per activity per participant to capture human biometric and kinematic variation.

---

## 5. Strict Fall Safety Protocol

Data collection must never jeopardize participant safety. Fall detection research carries inherent physical risks if conducted without medical precautions.

> [!CAUTION]
> **MANDATORY SAFETY RULES FOR FALL DATA COLLECTION**
> 1. **Protective Padding Required:** Falls must ONLY be performed onto a high-density, shock-absorbing gymnastics or martial arts crash mat of **at least 4 inches (10 cm) thickness**.
> 2. **Spotter Presence:** A minimum of two individuals (the participant and a dedicated spotter/operator) must be physically present during all fall trials.
> 3. **Controlled Deceleration:** Participants must be instructed to execute controlled, low-impact descent techniques (breakfalls). Hard, uncontrolled falls onto the head, neck, spine, or extended wrists are strictly prohibited.
> 4. **No Hard Floors:** Absolutely zero fall trials may be executed onto hard concrete, hardwood, or tile floors.
> 5. **Participant Discretion:** Participants have the absolute right to decline or halt fall trials at any point without explanation. The software or operator must never pressure a participant to continue.
> 6. **Postponement Protocol:** If certified crash mats or trained spotters are unavailable, fall collection MUST be postponed. The system supports proxy sitting/stooping trials or designated test dummy models in lieu of live human impacts.

---

## 6. Pilot Target & Statistical Limitations

### 6.1 Phase 16 Milestone Target
The pilot milestone established in Phase 16 is **$\ge 35$ independently labeled, participant-held-out fall test windows**.

### 6.2 Statistical Justification
Assuming a binomial distribution for fall detection sensitivity:
$$n = \frac{Z^2 \cdot p(1-p)}{d^2}$$
For an anticipated sensitivity $p = 0.90$, margin of error $d = 0.10$, and 95% confidence level ($Z = 1.96$):
$$n = \frac{(1.96)^2 \cdot 0.90 \cdot 0.10}{(0.10)^2} \approx 34.6 \implies 35\text{ windows}$$

### 6.3 Explicit Limitations
1. **Window Autocorrelation:** Overlapping sliding windows from the same fall event are temporally correlated. 35 windows derived from only 10 fall events do not provide 35 independent statistical degrees of freedom.
2. **Participant Diversity:** 35 windows collected from a single individual measure device sensitivity on that individual's biomechanics, not population-wide fall detection reliability.
3. **No Clinical Generalization:** Padded, voluntary falls performed by healthy young adults do not reflect real-world geriatric falls, which typically involve slower pre-fall gait, syncope, or bed roll-offs. Achieving this pilot milestone demonstrates pipeline feasibility, not clinical readiness.
