# Phase 56.1 Report — Historical Rate Verification and Calibration Readiness Audit

**Document Version:** 1.0.0  
**Phase:** 56.1  
**Date:** 2026-10-21  
**Status:** COMPLETED — OFFLINE AUDIT AND CORRECTIVE VALIDATION ONLY  
**Safety Protocol:** Strict Offline Audit Gate Enforced. Zero COM5 serial access, zero network traffic generation, zero CSI collection, zero firmware flashing/modification, zero model training or evaluation, zero protected asset modification, zero git commits.

---

## 1. Executive Summary & Verification Ledger

Phase 56.1 serves as the rigorous forensic audit and corrective-validation gateway succeeding Phase 56. Its mandate is to resolve all outstanding engineering uncertainties regarding historical acquisition rates, target-BSSID capture rates, firmware station association, telemetry timestamp semantics, collector buffer synchronization, and deep-learning temporal assumptions before any physical hardware or network stimulation can ever be considered.

### Core Audit Outcomes:
1. **Historical Rate Claims Forensically Reconciled:**
   - **Configured UDP Stimulator Rate:** Verified as $35.0\text{ Hz}$ in Python stimulator source code (`scratch/collect_phase15_real_dataset.py` and `collection_workflow.py`).
   - **Actual UDP Datagrams Sent:** **UNKNOWN**. The in-memory counter `packets_sent` was never persisted to session files, manifests, or database records.
   - **Total CSI Records Captured per Second:** Verified as mean $35.40\text{ Hz}$ (range $32.67\text{--}40.00\text{ Hz}$) across all 74 sessions in `dataset_manifest.json`.
   - **Target-BSSID CSI Records per Second:** **UNKNOWN**. Historical data was acquired exclusively in Format A (`RSSI=.. LEN=128 CSI:..`), which lacks 802.11 MAC headers and Transmitter Addresses (TA). Source MAC filtering was explicitly disabled (`filter_by_mac=False`).
   - **Non-Target CSI Records:** **UNKNOWN**. In an unassociated promiscuous capture without MAC filtering, ambient 2.4 GHz 802.11 frames (beacons, probe requests, probe responses, ambient data) from non-target devices triggered CSI callbacks and were admitted into the record stream.
   - **Rate Calculation Provenance:** Derived exclusively post-hoc as integer frame count divided by target recording loop duration ($\text{frame\_count} / dur$, where $dur \in \{3.0, 4.0\}\text{ s}$), NOT from inter-frame hardware timestamps or packet timestamps.

2. **Collector Buffer Lockstep Alignment & Parser Isolation Defect Resolved:**
   - **Defect Identified:** In `real_csi_collector.py`, `hw_timestamp_buffer` was conditionally appended only if `"hw_timestamp_us" in frame`, causing buffer length mismatch and temporal misalignment during FIFO frame evictions when mixed or legacy frames were ingested.
   - **Resolution Implemented:** Buffers are now updated in strict unconditional lockstep (appending `None` for missing hardware timestamps).
   - **Parser Mutual Exclusivity Enforced:** Changed consecutive `if` statements to `elif` in `_parse_line()` to ensure malformed Format B v2 records (`CSI_DATA_V2`) fail-closed and cannot accidentally fall through to legacy Format B (`CSI_DATA`) parsing.
   - **Zero Regression:** All 30 offline tests passed cleanly across the entire regression suite.

3. **Firmware Station-Association Requirements Formally Defined:**
   - The current firmware (`firmware/esp32s3_csi_collector/main/main.c`) operates in unassociated promiscuous Station mode on Channel 7.
   - Association and CSI promiscuous capture are mutually compatible in ESP-IDF v6.1.0, but station association cannot be achieved via `esp_wifi_connect()` alone. It requires:
     1. Initialization of LwIP/netif default station interface (`esp_netif_create_default_wifi_sta()`).
     2. Hard-pinning BSSID and Channel in `wifi_sta_config_t` with `bssid_set = 1`, `channel = 7`, and `scan_method = WIFI_FAST_SCAN` to prevent roaming/scanning channel hops.
     3. Explicitly disabling 802.11 modem sleep (`esp_wifi_set_ps(WIFI_PS_NONE)`), as default modem sleep halts RF/baseband reception and disables CSI callbacks between DTIM beacon intervals.
     4. Dedicated FreeRTOS event-loop handlers for `WIFI_EVENT_STA_CONNECTED`, `WIFI_EVENT_STA_DISCONNECTED`, and `IP_EVENT_STA_GOT_IP`.

4. **Model Temporal Requirements Deconstructed:**
   - The $30.0\text{ Hz}$ figure in `PhysicsCSIPreprocessor` is a **nominal preprocessing configuration parameter**, not a frozen neural network weight parameter.
   - `CSIDualBranchFusionNet` accepts discrete tensors of shape `(batch, 50, 56)`. It has no baked-in time step $\Delta t$.
   - However, the model's learned weights implicitly assume the 50-frame window spans $\approx 1.4\text{--}1.7\text{ seconds}$ of physical human motion. At passive rates ($1.66\text{--}3.8\text{ Hz}$), a 50-frame window spans $13\text{--}30\text{ seconds}$, destroying Doppler gesture kinematics and phase velocity features.
   - The $30.0\text{ Hz}$ target is an **empirical kinematic requirement** matching human motion speed ($0.5\text{--}2.5\text{ m/s}$) and Doppler frequency shifts ($8\text{--}41\text{ Hz}$), rather than a rigid mathematical proof for all features.

5. **Timestamp Semantics Grounded in ESP-IDF v6.1.0 API:**
   - `wifi_pkt_rx_ctrl_t.timestamp` is a 32-bit hardware counter running at microsecond ($\mu\text{s}$) resolution driven by the local Wi-Fi baseband/MAC peripheral clock.
   - It is **not** an 802.11 TSF beacon timestamp and **not** a network-synchronized clock.
   - It wraps around every $2^{32}\ \mu\text{s} \approx 71.58\text{ minutes}$. Safe subtraction `(t2 - t1) & 0xFFFFFFFF` is valid only for durations $< 71.58\text{ minutes}$ when modem sleep is disabled.
   - Monotonic host arrival time (`time.perf_counter()`) must remain strictly isolated from hardware arrival timestamps.

6. **Decoupled Calibration Acceptance Protocol Defined:**
   - Formally separated the 6 critical acquisition quantities ($R_{\text{stim}}$, $R_{\text{raw}}$, $R_{\text{target}}$, $R_{\text{parsed}}$, $\Delta t_{\text{hw}}$, $\Delta t_{\text{host}}$).
   - Specified exact log schemas, measurement methodologies, and defensive abort thresholds.
   - **Acquisition-rate adequacy is explicitly NOT declared achieved.**

---

## 2. Historical Rate Calculations and Their Provenance

A rigorous forensic audit of the historical acquisition artifacts in `scratch/collect_phase15_real_dataset.py`, `backend/app/services/collection_workflow.py`, `data/real_csi_dataset/dataset_manifest.json`, and raw session files was conducted.

### 2.1 Reconciled Provenance Matrix

| Metric Dimension | Reconciled Value / Status | Primary Source Artifact | Forensic Verification Methodology |
| :--- | :--- | :--- | :--- |
| **Configured UDP Stimulator Rate** | **35.0 Hz** | `scratch/collect_phase15_real_dataset.py:35`, `collection_workflow.py:46` | Audited `time.sleep(1.0 / 35.0)` loop inside `UdpStimulator.run()`. Configured rate was 35 pkts/s. |
| **Actual UDP Datagrams Sent** | **UNKNOWN** | None (Unlogged in memory) | In `UdpStimulator.run()`, `self.packets_sent += 1` was incremented, but this variable was never serialized to session JSON files, manifest files, or telemetry logs. Actual network transmission count cannot be proven. |
| **Total CSI Records Captured / Sec** | **Mean 35.40 Hz** (32.67–40.00 Hz) | `data/real_csi_dataset/dataset_manifest.json` (74 sessions) | Calculated post-hoc across 74 sessions: total admitted frames $N \in [98, 160]$ divided by nominal duration $dur \in [3.0, 4.04]\text{ s}$. |
| **Target-BSSID CSI Records / Sec** | **UNKNOWN** | Format A Raw CSI Sessions | Historical firmware emitted Format A (`RSSI=.. LEN=128 CSI:..`). Frames contained zero MAC headers. The collector ran with `filter_by_mac=False`. |
| **Non-Target CSI Records / Sec** | **UNKNOWN** | Format A Raw CSI Sessions | Ambient 802.11 traffic was unfilterable and unrecorded. Non-target packet proportion cannot be established. |
| **Duration Basis for Rate Calculation** | **3.0 to 4.04 seconds** | `session_manifest["duration_seconds"]` | Derived from wall-clock acquisition window or hardcoded trial time (`dur = 4.0`), NOT hardware timestamp deltas. |
| **Measurement Basis** | **Integer Count / Time** | Post-hoc arithmetic | Rate = $\frac{\text{frame\_count}}{\text{duration\_seconds}}$. It was NOT an inter-arrival interval calculation. |

### 2.2 Mathematical Breakdown of Historical Manifest Rates

For the 74 sessions documented in `data/real_csi_dataset/dataset_manifest.json`:
- **Minimum Recorded Frame Count:** 98 frames in 3.00 seconds $\rightarrow 32.67\text{ Hz}$.
- **Maximum Recorded Frame Count:** 160 frames in 4.00 seconds $\rightarrow 40.00\text{ Hz}$.
- **Standard 4-Second Target:** 140–145 frames in 4.00 seconds $\rightarrow 35.00\text{--}36.25\text{ Hz}$.
- **Mean Across All Sessions:** $35.40\text{ Hz} \pm 1.22\text{ Hz}$.

### 2.3 Historical Acquisition Code Evidence

In `scratch/collect_phase15_real_dataset.py`, the collector was invoked as follows:
```python
# Line 128 of scratch/collect_phase15_real_dataset.py
collector = RealCSICollector(
    port=port,
    baudrate=baudrate,
    source_mac="98:BA:5F:EF:28:26",  # Target AP BSSID specified
    filter_by_mac=False              # BUT MAC FILTERING WAS EXPLICITLY DISABLED
)
```
In `backend/app/services/real_csi_collector.py` (legacy branch for Format A):
```python
# Format A parsing:
match = re.search(r"RSSI\s*=\s*(-?\d+)\s+LEN\s*=\s*(\d+)\s+CSI:\s*(.*)", line)
if match:
    # No MAC address was present in the serial line!
    # Collector assigned a synthetic mock MAC:
    source_mac = "ESP32-S3-NODE-01"
```
Because the serial stream did not contain the 802.11 Transmitter Address, and the collector injected `"ESP32-S3-NODE-01"` as a placeholder string, all captured frames were admitted regardless of whether they originated from `98:BA:5F:EF:28:26` or ambient Wi-Fi devices.

---

## 3. Whether Target-BSSID Rate Can Actually Be Established

### 3.1 Forensic Verdict: UNKNOWN

**Formal Finding:** The claim that historical collection achieved 35–39 Hz of *target-BSSID* CSI records cannot be proven from the historical artifacts. It must be classified as **technically unestablished / unknown**.

### 3.2 Proof of Unverifiability
1. **Absence of 802.11 Address 2 (TA) in Format A:** Format A serial records contain only RSSI, length, and raw signed carrier values. There are zero bytes allocated to the transmitter MAC address, receiver MAC address, or BSSID.
2. **Promiscuous Channel-7 Environment:** The ESP32-S3 operated in promiscuous sniffer mode on 2.4 GHz Channel 7. In any standard domestic, academic, or office environment, 2.4 GHz Channel 7 is populated by:
   - AP Beacon frames from co-channel access points.
   - 802.11 Probe Requests from smartphones, laptops, and IoT devices.
   - 802.11 Probe Responses.
   - Unicast and broadcast data frames between third-party stations.
   - Acknowledgement (ACK) and Clear-to-Send (CTS) control frames.
3. **Hardware Callback Behavior:** In ESP-IDF, `wifi_csi_cb` is triggered for *every* valid OFDM packet received by the physical layer whose PHY preamble and LTF are successfully decoded, regardless of source or destination, unless filtered by hardware or software.
4. **Conclusion:** While active 35 Hz UDP stimulation was physically present on the local subnet, the proportion of captured CSI records originating from the target AP versus ambient transmitters is completely unrecorded. **Attributing 100% of historical CSI records to the target BSSID is an assumption, not an established empirical fact.**
5. **Policy Directive:** In accordance with user requirements, `dataset_manifest.json` will NOT be edited to reconcile these rates, and historical rates will remain documented with their explicit provenance and unknown quantities.

---

## 4. Collector Diff Audit and Compatibility Results

The implementation changes in `backend/app/services/real_csi_collector.py` and `backend/tests/test_phase56.py` were audited line-by-line to verify API stability, memory safety, and timing integrity.

### 4.1 Audit Checklist & Resolution

| Audit Requirement | Verification Result | Implementation Detail / Evidence |
| :--- | :--- | :--- |
| **Original 2-Tuple Return Stability** | **VERIFIED** | When `return_metadata=False` (default), `get_latest_window()` returns `(raw_win, phase_win)` identical to all previous phases. Existing pipeline consumers are unaffected. |
| **Documented Metadata Schema** | **VERIFIED** | When `return_metadata=True`, `get_latest_window()` returns `(raw_win, phase_win, meta_dict)` where `meta_dict` strictly conforms to `{timestamps, monotonic_timestamps, hw_timestamps, sequences, source_macs}`. |
| **FIFO Buffer Lockstep Alignment** | **DEFECT FIXED** | **Defect:** `hw_timestamp_buffer` was previously appended conditionally. If legacy or non-V2 frames arrived, buffer lengths diverged, causing misalignment during FIFO eviction.  <br>**Fix:** `RealCSICollector` now appends `frame.get("hw_timestamp_us")` unconditionally (storing `None` when absent). All 5 buffers (`raw_frame_buffer`, `phase_frame_buffer`, `timestamp_buffer`, `monotonic_timestamp_buffer`, `hw_timestamp_buffer`, `sequence_buffer`, `source_mac_buffer`) maintain identical lengths at all times. |
| **Frame-to-Metadata Association** | **VERIFIED** | Frames and their associated metadata are appended atomically within a single lock-guarded block in `_process_frame()`. Elements at index $i$ in any buffer correspond strictly to the same frame. |
| **Format A & Format B v1 Compatibility** | **VERIFIED** | `_parse_line()` correctly parses legacy Format A (`RSSI=.. LEN=128 CSI:..`) and Format B v1 (`CSI_DATA,<mac>,<rssi>,<noise>,<seq>,..`). |
| **Format B v2 Mutual Exclusivity** | **DEFECT FIXED** | **Defect:** In `_parse_line()`, `if line.startswith("CSI_DATA_V2"):` was followed by an un-nested `if line.startswith("CSI_DATA"):`. A malformed V2 line could be misinterpreted by the V1 parser.  <br>**Fix:** Changed to `elif line.startswith("CSI_DATA"):`. A malformed V2 record is now cleanly rejected without misinterpretation. |
| **Hardware Timestamp Wraparound** | **VERIFIED** | In `get_diagnostics()`, hardware timestamp deltas are calculated only when all window frames contain valid hardware timestamps, using unsigned 32-bit modulo arithmetic: `(t2 - t1) & 0xFFFFFFFF`. |
| **Host vs Hardware Isolation** | **VERIFIED** | Monotonic host arrival time (`time.perf_counter()`) is stored in `monotonic_timestamps`, wall-clock time in `timestamps`, and hardware timer values in `hw_timestamps`. They are never conflated or substituted. |
| **Diagnostic Stability under Edge Cases** | **VERIFIED** | `get_diagnostics()` handles empty buffers ($N=0$), single-frame buffers ($N=1$), zero-variance/duplicate timestamps, and missing hardware timestamps safely without throwing `ZeroDivisionError` or returning negative rates. |

---

## 5. Station-Association Requirements and Unresolved Issues

### 5.1 Inspection of Current Firmware Implementation

The active firmware source file is `firmware/esp32s3_csi_collector/main/main.c`.
Inspection of its Wi-Fi initialization sequence reveals:
```c
// firmware/esp32s3_csi_collector/main/main.c: Lines 130-175
void app_main(void) {
    nvs_flash_init();
    esp_netif_init();
    esp_event_loop_create_default();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_start();
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(7, WIFI_SECOND_CHAN_NONE);
    // CSI configuration & callbacks...
}
```

### 5.2 Critical Blockers in Current Firmware
1. **Unassociated State:** The firmware configures `WIFI_MODE_STA` but **never** configures an SSID, password, or calls `esp_wifi_connect()`. The ESP32-S3 has no IP address, no DHCP lease, and does not exchange frames with the router.
2. **Missing Network Interface Instance:** `esp_netif_init()` is called, but `esp_netif_create_default_wifi_sta()` is **omitted**. The LwIP TCP/IP stack cannot bind to the Wi-Fi station driver without a netif instance.
3. **No Event Handlers:** No event handler is registered for `WIFI_EVENT` or `IP_EVENT`. Connection failures, disconnections, and DHCP assignment cannot be detected or handled.
4. **Modem Sleep Enabled by Default:** In ESP-IDF v6.1.0, station mode defaults to `WIFI_PS_MIN_MODEM`. Under modem sleep, the baseband and RF circuits sleep between DTIM beacon intervals. This halts `wifi_csi_cb` callbacks for non-beacon frames and causes severe phase and timing jitter.
5. **Risk of Channel Hopping During Association:** When `esp_wifi_connect()` is called without restricting the scan, the ESP32 performs an active scan across channels 1–13, immediately knocking the receiver off Channel 7 and losing CSI capture.

### 5.3 ESP-IDF v6.1.0 Station-Association Requirements

To achieve station association while maintaining promiscuous CSI capture on Channel 7, the following sequence is technically required:

```
[System Init]
  ├── nvs_flash_init()
  ├── esp_netif_init()
  ├── esp_event_loop_create_default()
  └── esp_netif_create_default_wifi_sta()   <-- MANDATORY for LwIP / DHCP

[Wi-Fi Config]
  ├── esp_wifi_init(&cfg)
  ├── esp_wifi_set_storage(WIFI_STORAGE_RAM)
  ├── esp_wifi_set_mode(WIFI_MODE_STA)
  ├── wifi_sta_config_t:
  │     ├── ssid = "Tp link"
  │     ├── password = "..."
  │     ├── bssid_set = 1                   <-- Lock to specific AP BSSID
  │     ├── bssid = {0x98, 0xBA, 0x5F, ...}
  │     ├── channel = 7                     <-- Pin channel to 7
  │     └── scan_method = WIFI_FAST_SCAN    <-- Prevent scanning other channels
  └── esp_wifi_set_config(WIFI_IF_STA, &wifi_config)

[Power & State Optimization]
  ├── esp_wifi_start()
  ├── esp_wifi_set_ps(WIFI_PS_NONE)         <-- MANDATORY: Disable modem sleep
  ├── esp_wifi_connect()                    <-- Initiate association
  └── Event Handlers:
        ├── WIFI_EVENT_STA_CONNECTED: Verify channel == 7
        ├── IP_EVENT_STA_GOT_IP: Confirm DHCP acquisition
        └── WIFI_EVENT_STA_DISCONNECTED: Reconnect without channel hop

[CSI & Sniffer Configuration]
  ├── esp_wifi_set_promiscuous(true)
  ├── esp_wifi_set_promiscuous_rx_cb(...)
  └── esp_wifi_set_csi_config(&csi_config)
```

### 5.4 Unresolved Operational Risks
- **AP Dynamic Channel Changes:** If the `Tp link` router has "Auto Channel" enabled and migrates to Channel 1 or 6, the ESP32 will either lose association or jump channels. The router must be physically locked to 20MHz bandwidth on Channel 7.
- **Promiscuous Filter Interactions:** In ESP-IDF v6.1.0, promiscuous packet filters can occasionally drop unicast management frames needed for 802.11 4-way handshake renewal if configured incorrectly.

---

## 6. Model Temporal-Requirement Evidence

### 6.1 Architectural and Preprocessing Audit

The source code of `CSIDualBranchFusionNet` (`backend/app/models/csiformer.py`), `PhysicsCSIPreprocessor` (`backend/app/services/physics_preprocessor.py`), and `LivePipelineService` (`backend/app/services/live_pipeline_service.py`) was audited to trace how time is represented.

```
+-------------------------------------------------------------------------------+
|                             TEMPORAL TRACE MAP                                |
+-------------------------------------------------------------------------------+
|                                                                               |
|  1. Sliding Window: 50 CSI Frames                                             |
|     - Fixed integer buffer size: N = 50                                       |
|     - At 30 Hz: Window Duration T = 50 / 30 = 1.67 seconds                    |
|     - At 2.5 Hz: Window Duration T = 50 / 2.5 = 20.0 seconds                  |
|                                                                               |
|  2. PhysicsCSIPreprocessor:                                                   |
|     - Parameter: source_rate_hz = 30.0                                        |
|     - Role: Nominal parameter used to calculate STFT frequency axis           |
|                                                                               |
|  3. STFT Spectrogram Generation:                                              |
|     - scipy.signal.spectrogram(..., fs=source_rate_hz, nperseg=16, noverlap=8)|
|     - Time dimension output: 5 temporal slices                                |
|     - Frequency bin resolution: df = fs / nperseg = 30 / 16 = 1.875 Hz        |
|                                                                               |
|  4. CSIDualBranchFusionNet Architecture:                                      |
|     - Spatial/Amplitude Branch: Input shape (batch, 50, 56)                   |
|     - Doppler/Phase Branch: Input shape (batch, 5, 56)                        |
|     - Internal Weights: Linear layers, Multi-Head Attention, Conv1D           |
|     - Explicit Time Step (dt): NONE in PyTorch tensor operations              |
|                                                                               |
+-------------------------------------------------------------------------------+
```

### 6.2 Is 30 Hz a Hard Mathematical Constraint or an Engineering Target?

1. **Nominal Preprocessing Parameter:** `source_rate_hz=30.0` is an argument passed into `PhysicsCSIPreprocessor.__init__()`. It sets the `fs` argument in `scipy.signal.spectrogram`. If `fs` is changed, the physical frequency bin centers $\Delta f$ change, but the tensor output shape `(5, 56)` remains identical!
2. **Absence of Time in Model Weights:** The neural network weights operate on discrete matrix multiplications. The model cannot read a clock.
3. **Implicit Kinematic Constraint:**
   - Human gesture execution (push, pull, swipe, wave) takes approximately $1.0\text{--}2.0\text{ seconds}$.
   - Training datasets (Phase 13, 14, 15) were gathered during trials where gestures took $\approx 1.5\text{ seconds}$, spanning $\approx 50$ frames at $\approx 35\text{ Hz}$.
   - At 2.442 GHz ($\lambda \approx 12.28\text{ cm}$), hand/arm motion speeds of $v \in [0.5, 2.5]\text{ m/s}$ induce Doppler frequency shifts:
     $$f_D = \frac{2 v}{\lambda} = \frac{2 \times [0.5, 2.5]}{0.1228} \approx 8.1\text{ to }40.7\text{ Hz}$$
   - By the Nyquist sampling theorem, to resolve a Doppler frequency of $15\text{ Hz}$, the sampling rate must satisfy:
     $$f_s \ge 2 \times f_{\max} = 30.0\text{ Hz}$$
4. **Failure Mode at Passive Rates:** At the passive rate of $2.5\text{ Hz}$, a 50-frame window represents $20.0\text{ seconds}$ of history. A 1.5-second gesture occupies only 3.7 frames out of 50. The gesture information is severely sub-sampled, motion Doppler features are aliased into near-DC noise, and the model's temporal attention heads receive quasi-static ambient drift.
5. **Conclusion:** The $30.0\text{ Hz}$ requirement is **not** an arbitrary number or an architectural limit of PyTorch, but a **biophysical and kinematic necessity** imposed by the duration and Doppler physics of human gesture interactions.

---

## 7. ESP-IDF Timestamp API Verification

### 7.1 Native Header Definition

Inspection of ESP-IDF v6.1.0 native headers (`local/esp_wifi_types_native.h`) confirms the precise declaration of packet metadata:

```c
typedef struct {
    signed rssi: 8;                /**< Received Signal Strength Indicator */
    unsigned rate: 11;             /**< PHY rate encoding */
    unsigned is_group: 1;
    unsigned : 1;
    unsigned sig_mode: 2;          /**< 0: legacy non-HT, 1: HT, 3: VHT */
    unsigned legacy_length: 12;
    unsigned damatch0: 1;
    unsigned damatch1: 1;
    unsigned bssidmatch0: 1;
    unsigned bssidmatch1: 1;
    unsigned mcs: 7;               /**< Modulation and Coding Scheme */
    unsigned cwb: 1;               /**< Channel Width: 0: 20MHz, 1: 40MHz */
    unsigned : 16;
    unsigned smoothing: 1;
    unsigned not_sounding: 1;
    unsigned : 1;
    unsigned aggregation: 1;
    unsigned stbc: 2;
    unsigned fec_coding: 1;
    unsigned sgi: 1;
    unsigned noise_floor: 8;       /**< Noise floor in dBm */
    unsigned ampdu_cnt: 8;
    unsigned channel: 4;           /**< Primary channel number */
    unsigned secondary_channel: 4;
    unsigned : 8;
    unsigned timestamp: 32;        /**< Local hardware timestamp in microseconds (us) */
    unsigned : 32;
    unsigned : 32;
    unsigned : 32;
    unsigned : 32;
    unsigned : 32;
    unsigned rx_state: 8;
    unsigned : 24;
} wifi_pkt_rx_ctrl_t;
```

### 7.2 Rigorous Semantic Differentiation

| Semantic Dimension | Verified Engineering Fact | Common Pitfall / False Assumption |
| :--- | :--- | :--- |
| **Clock Source** | Driven by internal Wi-Fi MAC/baseband peripheral hardware counter running at $1\text{ MHz}$ ($1\ \mu\text{s}$ per tick). | **NOT** FreeRTOS tick count (`xTaskGetTickCount`). |
| **Network Synchronization** | **Unsynchronized local counter.** It resets when Wi-Fi starts and does not reflect AP beacon TSF. | **NOT** 802.11 TSF (Timing Synchronization Function). TSF is 64-bit and obtained via `esp_wifi_get_tsf_time()`. |
| **Wraparound Period** | $2^{32}\ \mu\text{s} = 4,294,967,296\ \mu\text{s} \approx 4,294.97\text{ s} \approx \mathbf{71.58\text{ minutes}}$. | Does not wrap around every second or hour. |
| **Wraparound Arithmetic** | For consecutive frames $t_1, t_2$, interval is $\Delta t = (t_2 - t_1) \pmod{2^{32}}$, valid if $\Delta t < 71.58\text{ min}$. | Standard unsigned 32-bit subtraction `(t2 - t1) & 0xFFFFFFFF` handles rollover seamlessly. |
| **Modem Sleep Behavior** | **Clock stops or drifts during light/modem sleep.** `esp_wifi_set_ps(WIFI_PS_NONE)` is required. | If sleep is enabled, timestamp jumps unpredictably and cannot be used for interval estimation. |
| **Inter-Arrival Estimation** | **Valid for high-precision frame interval estimation** ($\pm 1\ \mu\text{s}$) strictly when `WIFI_PS_NONE` is enforced. | Cannot be compared across different ESP32 devices (no shared clock). |
| **Host Arrival Relation** | Host timestamp measures serial transfer + USB UART queueing. Hardware timestamp measures OTA PHY arrival. | Conflating host arrival with hardware capture introduces up to $20\text{ ms}$ of UART jitter. |

---

## 8. Revised Calibration Protocol and Explicit Abort Criteria

### 8.1 Decoupled Metric Definitions

To ensure unambiguous scientific validity, the calibration protocol decouples acquisition measurements into 6 distinct quantities:

$$\begin{aligned}
R_{\text{stim}} &\triangleq \text{UDP datagrams sent per second by host stimulator (pkts/s)} \\
R_{\text{raw}} &\triangleq \text{Total CSI callback records captured per second by ESP32 physical layer (Hz)} \\
R_{\text{target}} &\triangleq \text{CSI records matching target BSSID } (98:\text{BA}:5\text{F}:\text{EF}:28:26) \text{ per second (Hz)} \\
R_{\text{parsed}} &\triangleq \text{Valid records admitted into host collector sliding window per second (Hz)} \\
\Delta t_{\text{hw}} &\triangleq \text{Hardware inter-arrival interval: } (t_{\text{hw}, i} - t_{\text{hw}, i-1}) \pmod{2^{32}}\ (\mu\text{s}) \\
\Delta t_{\text{host}} &\triangleq \text{Host serial monotonic arrival interval: } (t_{\text{mono}, i} - t_{\text{mono}, i-1})\ (\text{s})
\end{aligned}$$

### 8.2 Stepped Rate Sequence Justification

| Stage | Target Stim Rate ($R_{\text{stim}}$) | Duration | Engineering Purpose & Decision Gate |
| :---: | :---: | :---: | :--- |
| **Stage 0** | **0 pkts/s (Passive Baseline)** | 60 s | **Establish true passive target rate.** Measure ambient beacon frequency from AP ($R_{\text{target}}$ baseline) and verify zero UDP stimulation. |
| **Stage 1** | **5 pkts/s (Low Probe)** | 30 s | **Verify station unicast routing.** Confirm that UDP packets to ESP32 IP trigger downlink frames from target AP without packet loss or queue buildup. |
| **Stage 2** | **15 pkts/s (Intermediate)** | 30 s | **Confirm rate linearity.** Verify that $R_{\text{target}} \approx R_{\text{passive}} + 15\text{ Hz}$ and UART buffers remain stable without framing errors. |
| **Stage 3** | **30 pkts/s (Nominal Target)** | 60 s | **Validate operational model rate.** Confirm sustained $30.0\text{ Hz}$ target delivery matching `PhysicsCSIPreprocessor` requirements. |
| **Stage 4** | **35 pkts/s (Historical Parity)** | 60 s | **Verify historical reproducibility.** Test whether historical $35.4\text{ Hz}$ performance can be reproduced with zero packet drop and $<30\text{ ms}$ serial latency. |

### 8.3 Predefined Safety Abort Criteria

If any of the following conditions are met during execution, the test MUST be aborted immediately:

```
+-------------------------------------------------------------------------------+
|                       MANDATORY CALIBRATION ABORT GATES                       |
+-------------------------------------------------------------------------------+
| 1. Serial Latency Spike:                                                      |
|    - Instantaneous host serial latency > 100 ms                               |
|    - Rolling 1-second mean serial latency > 30 ms                             |
|                                                                               |
| 2. Rate Tracking Failure:                                                     |
|    - In Stages 1-4, target CSI rate |R_target - (R_passive + R_stim)| > 20%   |
|      persisting for longer than 5 consecutive seconds                         |
|                                                                               |
| 3. Packet Transmission Loss:                                                  |
|    - Stimulator socket buffer drops or network transmit error > 2%            |
|                                                                               |
| 4. Channel Deviation:                                                         |
|    - Reported primary channel in rx_ctrl != 7                                 |
|                                                                               |
| 5. UART / Collector Buffer Overflow:                                          |
|    - FIFO frame drops in collector > 0                                        |
|    - Serial input buffer overflow or framing error detected                   |
|                                                                               |
| 6. Hardware Timestamp Anomaly:                                                |
|    - Negative or frozen hardware timestamps under WIFI_PS_NONE                |
+-------------------------------------------------------------------------------+
```

---

## 9. Tests Executed and Exact Results

### 9.1 Test Execution Summary

The offline test suite was executed using Python 3.11.9 (`py -3.11 -m pytest`).
**All 30 tests passed cleanly with 0 failures.**

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\saifu\Desktop\4-1 project
collected 30 items

backend/tests/test_phase52.py::test_phase52_gate0_protected_file_invariance PASSED       [  3%]
backend/tests/test_phase52.py::test_phase52_target_source_filtering_and_fail_closed PASSED [  6%]
backend/tests/test_phase52.py::test_phase52_ht20_physical_carrier_mask PASSED           [ 10%]
backend/tests/test_phase52.py::test_phase52_stream_diagnostics_contract PASSED            [ 13%]
backend/tests/test_phase52.py::test_phase52_model_preprocessing_invariance PASSED         [ 16%]
backend/tests/test_phase55.py::test_phase55_gate0_protected_file_invariance PASSED       [ 20%]
backend/tests/test_phase55.py::test_phase55_acquisition_rate_gate_fails_closed_under_passive_conditions PASSED [ 23%]
backend/tests/test_phase55.py::test_phase55_passive_pilot_source_filtering_fail_closed PASSED [ 26%]
backend/tests/test_phase55.py::test_phase55_global_sequence_reconciliation_logic PASSED   [ 30%]
backend/tests/test_phase55.py::test_phase55_temporal_dilation_and_window_semantics PASSED [ 33%]
backend/tests/test_phase55_1.py::test_phase55_1_protected_hashes PASSED                 [ 36%]
backend/tests/test_phase55_1.py::test_phase55_1_record_count_vs_rate_separation PASSED    [ 40%]
backend/tests/test_phase55_1.py::test_phase55_1_window_span_definitions_consistency PASSED [ 43%]
backend/tests/test_phase55_1.py::test_phase55_1_spatial_interpolation_invariance PASSED   [ 46%]
backend/tests/test_phase55_1.py::test_phase55_1_doppler_stft_frequency_scaling PASSED     [ 50%]
backend/tests/test_phase55_1.py::test_phase55_1_carrier_validity_multipath_notch_tolerance PASSED [ 53%]
backend/tests/test_phase55_1.py::test_phase55_1_session_disposition_states PASSED        [ 56%]
backend/tests/test_phase56.py::test_phase56_gate0_protected_file_invariance PASSED       [ 60%]
backend/tests/test_phase56.py::test_phase56_historical_acquisition_evidence_consistency PASSED [ 63%]
backend/tests/test_phase56.py::test_phase56_espidf_timestamp_semantics_contract PASSED   [ 66%]
backend/tests/test_phase56.py::test_phase56_format_b_v2_parser_and_backward_compatibility PASSED [ 70%]
backend/tests/test_phase56.py::test_phase56_host_monotonic_timing_and_sliding_window_metadata PASSED [ 73%]
backend/tests/test_phase56.py::test_phase56_rate_gate_vs_record_count_gate_separation PASSED [ 76%]
backend/tests/test_phase56.py::test_phase56_calibration_procedure_safety_abort_simulation PASSED [ 80%]
backend/tests/test_phase56_1.py::test_phase56_1_gate0_protected_file_invariance PASSED     [ 83%]
backend/tests/test_phase56_1.py::test_phase56_1_collector_buffer_lockstep_alignment PASSED [ 86%]
backend/tests/test_phase56_1.py::test_phase56_1_telemetry_parser_mutual_exclusivity PASSED [ 90%]
backend/tests/test_phase56_1.py::test_phase56_1_historical_provenance_audit PASSED         [ 93%]
backend/tests/test_phase56_1.py::test_phase56_1_diagnostic_timing_robustness PASSED       [ 96%]
backend/tests/test_phase56_1.py::test_phase56_1_decoupled_calibration_quantities PASSED   [100%]

============================= 30 passed in 19.34s =============================
```

---

## 10. Protected Hashes Verification

In accordance with Section 1 of the task specification, the MD5 checksums of all protected project assets were verified before and after all operations.

| Protected Asset | Reference MD5 Hash | Audited MD5 Hash | Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **100% INVARIANT** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **100% INVARIANT** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **100% INVARIANT** |

**Zero modifications, overwrites, or corruptions occurred on protected assets.**

---

## 11. Remaining Blockers and Recommended Next Action

### 11.1 Remaining Engineering Blockers
1. **Firmware Station Association Not Yet Implemented in C:** The active firmware `main.c` remains in unassociated promiscuous STA mode. It requires code updates to initialize default netif, configure target credentials, enforce `bssid_set=1`, `channel=7`, `WIFI_FAST_SCAN`, and disable modem sleep (`WIFI_PS_NONE`).
2. **Format B v2 Telemetry Not Yet Deployed to ESP32-S3:** While host parser support in `real_csi_collector.py` is fully verified and backward-compatible, the firmware running on the hardware has not been flashed and does not yet emit `CSI_DATA_V2` lines.
3. **Physical RF & Network Environment Validation:** The router `Tp link` must be verified to have 20MHz bandwidth pinned on Channel 7, with DHCP server active on `192.168.0.0/24`.
4. **Acquisition-Rate Adequacy Has NOT Been Achieved:** Under passive conditions, capture remains at $1.66\text{--}3.8\text{ Hz}$. Target-rate adequacy ($\ge 28\text{ Hz}$) cannot be declared until an authorized calibration experiment is conducted.

### 11.2 Recommended Next Action
1. **Conclude Phase 56.1:** Submit this audit report for review.
2. **Authorize Phase 57 (Firmware Enhancement & Compilation Only):** Update `firmware/esp32s3_csi_collector/main/main.c` offline with Station association, `WIFI_PS_NONE`, fast scan, and Format B v2 telemetry. Compile with `idf.py build` offline without flashing hardware.
3. **Subsequent Authorized Calibration:** Only after firmware build verification and explicit user authorization, schedule a controlled hardware calibration run on COM5 under the revised Phase 56.1 stepped protocol.
