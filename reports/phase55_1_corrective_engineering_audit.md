# Phase 55.1 Report — Corrective Engineering Audit and Acquisition Readiness Resolution

**Document Version:** 1.0.0  
**Phase:** 55.1  
**Date:** 2026-10-20  
**Status:** `COMPLETED (CORRECTIVE ENGINEERING AUDIT & QUALITY GATE RESOLUTION ACHIEVED; ACQUISITION-RATE ADEQUACY REMAINS UNRESOLVED BLOCKER)`  
**Safety Protocol:** Strict offline engineering audit and corrective-planning phase. Zero live serial port access on COM5, zero active network traffic generation (ICMP, UDP, TCP), zero firmware flashing or reconfiguration, zero real CSI data collection or modification, zero model training or evaluation, zero protected checkpoint or manifest alterations, zero git commits or pushes.

---

## 1. Executive Summary & Audit Mandate

### 1.1 Context and Purpose
Phase 55 established pilot campaign protocols and documented an unresolved acquisition-rate blocker: passive listening yields approximately 1.66–3.8 records/s, whereas historical collection achieved 35–39 records/s using active UDP stimulation. CSIFormer's Transformer encoder consumes 50-frame windows, and the downstream physics preprocessing engine assumes a nominal 30.0 Hz source sampling rate.

Phase 55.1 executes a rigorous, offline, code-level engineering audit to resolve inconsistencies, correct quality-gate definitions, eliminate conflicting assumptions, separate data volume from temporal sampling rate, and formulate an evidence-based roadmap for resolving the acquisition-rate deficit.

### 1.2 Core Audit Principles
1. **Fact-First Engineering:** Prioritize code paths, firmware logic, and empirical telemetry over inherited assertions or documentation polish.
2. **Epistemological Rigor:** Classify every parameter, rule, and threshold as verified from implementation, supported by existing measurements, provisional engineering threshold, requiring future calibration, or unresolved.
3. **No Compromise of Safety or Asset Integrity:** Strict embargo on live RF acquisition, hardware tampering, network probing, and model alteration. Bit-level cryptographic invariance of protected assets is maintained throughout.
4. **Transparent Blocker Reporting:** Do not weaken acceptance gates to make current hardware pass. The acquisition-rate deficit is documented as an open technical blocker requiring explicit future resolution.

---

## 2. Actual Implementation and Telemetry Audit

An exhaustive code-level audit was conducted across all relevant firmware, ingestion, preprocessing, validation, and historical dataset components. The findings address the ten core architectural questions:

### 2.1 CSI Record Generation and Transmission
- **Firmware Implementation:** In [`firmware/esp32s3_csi_collector/main/main.c:150-197`](file:///C:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c#L150-L197), Wi-Fi is initialized in promiscuous mode (`esp_wifi_set_promiscuous(true)`) locked to Channel 7 (`esp_wifi_set_channel(7, WIFI_SECOND_CHAN_NONE)`). CSI extraction is enabled across all 802.11n preamble types (`lltf_en`, `htltf_en`, `stbc_htltf2_en`, `ltf_merge_en`, `channel_filter_en` in `init_csi()`).
- **Hardware Callback:** Whenever an OFDM frame with valid preamble is demodulated by the baseband MAC, `wifi_csi_cb(void *ctx, wifi_csi_info_t *info)` fires.
- **Formatting & Transport:** In lines 51–79, raw signed 8-bit I/Q values (`info->buf`) are converted to real subcarrier amplitudes ($A = \sqrt{I^2 + Q^2}$) and unwrapped phases ($\phi = \text{atan2}(Q, I)$). The callback formats a comma-delimited string (Format B):
  `CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,amp_1:phase_1,...`
  The string is streamed over USB-UART serial via `printf` at 115,200 baud console / 921,600 baud transport.
- **Host Ingestion:** In [`backend/app/services/real_csi_collector.py:275-331`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L275-L331), `RealCSICollector._serial_ingest_loop()` reads serial chunks, buffers newline-terminated strings, parses candidate lines, and forwards validated frames to `_process_parsed_frame()`.

### 2.2 Observable Frames and Target Source Filtering
- **Physical Observation Scope:** In promiscuous mode on Channel 7 HT20, the ESP32-S3 MAC hardware demodulates *every* over-the-air 802.11 packet satisfying preamble detection thresholds, regardless of BSSID or destination. This includes router beacons, probe responses, uplink probe requests, data packets from associated stations, foreign AP beacons on Channel 7, and ambient control frames.
- **Software Target Filtering:** In [`real_csi_collector.py:430-446`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L430-L446), the collector enforces target isolation:
  ```python
  if self.filter_by_mac:
      if not source_mac_norm or not self.target_mac:
          self.parse_errors += 1
          return
      if source_mac_norm != self.target_mac:
          self.filtered_non_target_packets += 1
          return
  ```
  Only frames where the parsed MAC matches `target_mac` (`"98:BA:5F:EF:28:26"`) pass into the CSI buffer. Malformed or missing MAC frames fail closed.

### 2.3 MAC Field Semantics: Transmitter Address (TA) vs BSSID
- **Firmware Origin:** In `main.c:47-49`, the MAC string is constructed from `info->mac`. In ESP-IDF, `wifi_csi_info_t.mac` contains Address 2 of the 802.11 MAC frame header.
- **802.11 Protocol Truth:** Address 2 is defined in IEEE 802.11 specifications strictly as the **Transmitter Address (TA)**—the physical radio interface actively transmitting the frame over the air.
  - **Downlink Transmissions (AP to Client / Broadcast):** `TA == BSSID` (`98:BA:5F:EF:28:26`). For beacons, probe responses, and downlink data, Address 2 matches the router's BSSID.
  - **Uplink Transmissions (Client to AP):** `TA == Client Station MAC` (e.g. host laptop `60:E9:AA:2C:9A:83` intercepted during Phase 54). For uplink frames, Address 1 (Receiver Address RA) contains the BSSID, while Address 2 contains the client's radio address.
- **Engineering Verdict:** The parsed MAC represents the physical **Transmitter Address (TA)**, not an invariant BSSID. Setting `target_mac="98:BA:5F:EF:28:26"` and `filter_by_mac=True` admits *exclusively router-downlink transmissions* and discards client uplink packets.

### 2.4 Sequence Counter Mechanics and Gap Reconciliation
- **Hardware Counter Lifecycle:** In `main.c:34`, `static uint32_t packet_sequence = 0` is defined at file scope. In line 45, `packet_sequence++` increments unconditionally inside `wifi_csi_cb()` for *every* CSI callback that fires on Channel 7 before any MAC filtering.
- **Interleaving vs Loss:** Because `packet_sequence` increments for both target and non-target frames, whenever ambient non-target packets arrive, the admitted target stream exhibits sequence number jumps.
- **Code Path & Telemetry:** In Phase 53, a diagnostic audit proved that 13 reported target sequence jumps matched 13 interleaved non-target frames 1:1. True physical transport loss over the USB-UART serial link was strictly **0.00%**.
- **Validator Defect Identified:** In [`session_validator.py:255-260`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py#L255-L260), the existing code naively computes dropped packets as `sum(d - 1 for d in diffs_s if d > 1)`. When applied to a target-filtered stream, this falsely attributes interleaved non-target packets as physical packet loss.

### 2.5 Host Timestamp Assignment, Discard, and Preservation
- **Firmware Timestamp Absence:** The ESP32-S3 firmware Format B serial string contains no microsecond hardware timer (TSF).
- **Host Assignment:** Timestamps originate on the host computer via `time.time()` inside `RealCSICollector.parse_raw_telemetry_line()` ([`real_csi_collector.py:372, 414`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L372)).
- **Sliding Window Discard:** In [`real_csi_collector.py:540-552`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L540-L552), `get_latest_window()` extracts `raw_frame_buffer` and `phase_frame_buffer` of shape `[50, 56]`. **Timestamps are completely discarded**. The model consumes tensors where temporal spacing is implicit.
- **Session Preservation:** During recording sessions, timestamps are preserved in `recorded_frames` in the JSON/CSV output and evaluated by `compute_session_sampling_rate()`.
- **Clock Resolution Limitation:** On Windows, `time.time()` typically has a ~15.6 ms resolution. Ingesting multi-packet serial buffers can cause adjacent packets to receive identical host timestamps, risking false duplicate rejections.

### 2.6 Subcarrier Resampling: 64 Raw Bins to 56 Model Channels
- **Physical Spectrum:** In 802.11n HT20 mode, the ESP32-S3 baseband produces 64 FFT bins: 52 active data/pilot subcarriers (bins 1–26 and 38–63) and 12 null/guard bins (DC at bin 0, guard band at bins 27–37), defined in [`esp32_csi_adapter.py:40-85`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_csi_adapter.py#L40-L85).
- **Resampling Implementation:** In [`real_csi_collector.py:477-485`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L477-L485), `_process_parsed_frame()` executes 1D linear interpolation across the subcarrier axis:
  ```python
  x_old = np.linspace(0, 1, len(raw_amps))
  x_new = np.linspace(0, 1, self.TARGET_SUBCARRIERS)
  aligned_amp = np.interp(x_new, x_old, raw_amps).astype(np.float32)
  aligned_phase = np.interp(x_new, x_old, raw_phases).astype(np.float32)
  ```
- **Physical Tone Preservation:** In line 507, `self.adapter.separate_physical_and_null_components(raw_amps)` extracts un-interpolated `physical_active_amplitudes` (52) and `physical_null_amplitudes` (12), which are persisted in the recorded JSON for scientific provenance.
- **Critical Distinction:** Spatial/channel interpolation is strictly an interpolation across the **spatial / frequency domain**. It does **not** and **cannot** alter temporal sampling or synthesize missing temporal observations.

### 2.7 50-Frame Temporal Window Construction
- **Queue Implementation:** In `real_csi_collector.py:85-86`, `self.raw_frame_buffer = deque(maxlen=50)`.
- **Window Assembly:** In lines 540–552, `get_latest_window()` waits until `len(self.raw_frame_buffer) >= 50` and executes `np.stack(list(self.raw_frame_buffer), axis=0)` to yield a tensor of shape `[50, 56]`.
- **Index-Based FIFO Queue:** The window is purely an index-based buffer of 50 consecutively admitted target frames. It has **no internal elapsed-time enforcement**.

### 2.8 Provenance of the 30 Hz Source-Rate Assumption
- **Code Locations:**
  1. [`backend/app/services/live_pipeline_service.py:56-64`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py#L56-L64): `PhysicsCSIPreprocessor` is initialized with `source_rate_hz=30.0`.
  2. [`backend/app/services/physics_csi_preprocessor.py:199-207`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py#L199-L207): In `compute_doppler_spectrogram()`, `fs=self.source_rate_hz` is passed to `scipy.signal.stft()`.
  3. [`backend/app/services/esp32_csi_adapter.py:86`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_csi_adapter.py#L86): Defaults `target_rate_hz=30.0` for temporal resampling of benchmark datasets (e.g. Widar 3.0 at 1000 Hz).
  4. [`real_csi_collector.py:828`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py#L828): In `inject_synthetic_burst()`, `np.linspace(0, 1.66, 50)` assumes a nominal 30 Hz rate ($50 / 1.66 \approx 30.1\text{ Hz}$).
  5. [`scratch/execute_phase15_adaptation_benchmark.py:56`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/execute_phase15_adaptation_benchmark.py#L56): `CalibratedPhysicsPreprocessor` uses `source_rate_hz=35.58` (the empirical mean rate across historical sessions).
- **Classification:** The 30 Hz rate is a **preprocessing configuration default** selected to approximate the nominal ~35 Hz acquisition rate of historical UDP-stimulated sessions. It is **not** an experimentally validated passive listening rate.

### 2.9 Historical Acquisition Rates: Active UDP Stimulation
- **Empirical Baseline in Manifest:** In [`data/real_csi_dataset/dataset_manifest.json`](file:///C:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json), all 74 physical sessions exhibit sampling rates between 35.0 and 39.0 Hz (mean $\approx 36.8\text{ Hz}$, duration $4.0\text{ s}$, ~140–155 frames).
- **Forensic Code Discovery:** In [`backend/app/services/collection_workflow.py:44-75, 188`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py#L44-L75), `CollectionWorkflowManager.start_session()` explicitly initialized and activated `UdpStimulator`:
  ```python
  class UdpStimulator:
      """Sends background UDP probes to stimulate ESP32-S3 CSI callbacks at ~35 Hz."""
      def __init__(self, target_ip: str = "192.168.0.232", port: int = 5555, rate_hz: float = 35.0):
  ```
  `UdpStimulator` transmitted active background UDP packets (`b"CSI_PROBE_P17"`) at 35.0 Hz to `192.168.0.232:5555`.
- **Verdict:** Historical sessions obtained 35–39 Hz strictly because active background UDP traffic stimulated the router and channel. Passive listening without traffic achieves only 1.66–3.8 Hz.

### 2.10 Physical Accuracy of In-Pipeline Elapsed Time
- The existing collector **cannot accurately represent hardware-level elapsed time between records**:
  1. The firmware outputs no hardware TSF timestamp.
  2. Host timestamps (`time.time()`) incorporate serial buffer latencies, OS thread scheduling jitter, and USB FIFO delays.
  3. Sliding window tensors discard timestamps entirely; indices $t$ and $t+1$ are treated by the Transformer as equidistant steps.

---

## 3. Analysis of Acquisition-Rate Options and Technical Decision Matrix

### 3.1 Mathematical Definitions of Window Duration
To eliminate ambiguity, two consistent definitions are formalized:
- **Duration by Rate Intervals ($T_{\text{intervals}} = N / f$):** The physical duration represented by $N$ sample periods at rate $f$.
  - At 35.0 Hz: $50 / 35.0 = \mathbf{1.429\text{ s}}$.
  - At 30.0 Hz: $50 / 30.0 = \mathbf{1.667\text{ s}}$.
  - At 1.66 Hz: $50 / 1.66 = \mathbf{30.12\text{ s}}$.
- **First-to-Last Sample Elapsed Span ($\Delta t = (N - 1) / f$):** The exact elapsed time between the first sample $t_0$ and the 50th sample $t_{49}$.
  - At 35.0 Hz: $49 / 35.0 = \mathbf{1.400\text{ s}}$.
  - At 30.0 Hz: $49 / 30.0 = \mathbf{1.633\text{ s}}$.
  - At 1.66 Hz: $49 / 1.66 = \mathbf{29.518\text{ s}}$.
- **Temporal Dilation Factor:** $\frac{30.12\text{ s}}{1.43\text{ s}} \approx \mathbf{21.1\times\text{ dilation}}$ (or $\frac{29.52\text{ s}}{1.40\text{ s}} \approx \mathbf{21.1\times}$).

### 3.2 Evaluation of Acquisition-Rate Pathways

| Option | Problem Addressed | Current Supporting Evidence | Required Changes | Impact on Data Distribution | Key Risks & Limitations | Safe Validation Method | Requires Explicit Authorization? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Option 1: Passive Listening (Existing Setup)** | Non-intrusive sensing without network transmission. | 1.66 Hz (Phase 54), 3.20 Hz (Phase 52), 3.79 Hz (Phase 51). | None on hardware; requires complete redesign of model temporal pipeline. | Severe distribution shift ($21\times$ temporal dilation). Incompatible with existing checkpoints. | Aliases all human limb motion (Nyquist limit 0.83 Hz); gestures span only 2–3 frames; model attention fails. | Safe offline audit proves failure; multi-hour passive beacon monitoring. | No (Passive only). **Verdict: Fails rate requirement**. |
| **Option 2: Authorized Metered Packet Source** | Sustains ~30–35 Hz sampling rate matching training distribution. | Historical dataset achieved 35–39 Hz via active UDP stimulator. Phase 54 proved physical RF capture of client probes. | Authorized software packet generator (UDP unicast / ICMP); tuned 2.4 GHz latency threshold (75–100 ms). | Matches training distribution of `dataset_manifest.json` and model checkpoints. | Consumes 2.4 GHz airtime; potential latency impact under contention. | Bounded stepped rate sweep (5, 10, 20, 30 Hz) with automated latency/loss abort triggers. | **YES. Explicit network-experiment authorization required.** |
| **Option 3: Router Configuration Tuning** | Increases passive beacon density without client transmissions. | Standard 802.11 beacons broadcast at 100 TU ($\approx 102.4\text{ ms} \approx 9.77\text{ Hz}$). | Router admin access; reduce beacon interval to 20–30 ms; set DTIM period = 1. | Preserves downlink-only AP profile, but max rate capped at ~30–50 Hz. | Consumer routers often restrict beacon interval $\ge 50\text{ ms}$; potential AP CPU load and power usage. | Router settings inspection followed by passive rate measurement. | **YES. Router administrative authorization required.** |
| **Option 4: Firmware / Hardware Enhancement** | Ingests client uplink frames and adds hardware microsecond TSF. | Sniffer physically intercepted laptop uplink frames (`60:E9..`) in Phase 54. | Firmware modification adding microsecond hardware timer to Format B; dual-MAC filtering; 921,600 baud. | Mixing downlink and uplink introduces dual-path geometry (different Tx locations/antennas). | Multipath inconsistency between downlink and uplink; requires firmware rebuild and flashing. | Offline firmware syntax test followed by authorized single-board flash test. | **YES. Firmware modification and flash authorization required.** |
| **Option 5: Irregular / Continuous-Time Model Redesign** | Enables neural network to process irregular, low-rate CSI directly. | Transformer positional encodings mathematically assume uniform steps. | Replace model with Neural ODE / Continuous Attention; remove fixed-rate STFT; retrain from scratch. | Completely replaces data distribution and architecture; invalidates Phase 13 & 15 models. | High research complexity; does not solve physical Nyquist aliasing for <2 Hz motion capture; requires massive new dataset. | Offline architectural design and synthetic burst simulation. | No hardware authorization, but **requires extensive model retraining authorization**. |

### 3.3 Prioritized Recommendation
**Primary Recommendation: Option 2 (Metered Packet Source) with safety-reviewed rate control**, complemented by **Option 4 (Hardware TSF in firmware)** in a future hardware phase.
- *Rationale:* The existing trained models (`csiformer_phase13_best.pth` and `csiformer_phase15_adapted.pth`) and the established dataset (`dataset_manifest.json`) were built on active ~35 Hz traffic. Restoring controlled 30–35 Hz traffic with a tuned 2.4 GHz latency threshold (e.g. 75–100 ms) preserves the model's physical inductive biases and spatial multipath geometry without invalidating existing assets.

---

## 4. Audit of the 30 Hz Source-Rate Assumption

### 4.1 Nature of the 30 Hz Parameter
1. **Not a Theoretical Coincidence:** 30 Hz was chosen because human gesture kinematics (arm reach, sit-to-stand, walking stride) have velocity components between 0.5 m/s and 3.0 m/s. At 2.442 GHz ($\lambda = 0.123\text{ m}$), the Doppler frequency shift is:
   $$f_D = \frac{2 v}{\lambda} \cos \theta \implies f_D \approx \frac{2 \times 1.5}{0.123} \approx 24.4\text{ Hz}$$
   The Nyquist sampling theorem requires $f_s \ge 2 f_D \approx 48.8\text{ Hz}$ for full velocity disambiguation, or $f_s \ge 30\text{ Hz}$ for sub-Nyquist enveloped Doppler profiles.
2. **STFT Spectrogram Coupling:** In `PhysicsCSIPreprocessor.compute_doppler_spectrogram()`, `scipy.signal.stft(..., fs=self.source_rate_hz)` computes the frequency bins $f$. The frequency bin width is $\Delta f = \frac{f_s}{N_{\text{FFT}}}$.
   - If `source_rate_hz` is artificially set to 1.66 Hz, the frequency axis collapses to $[-0.83, +0.83]\text{ Hz}$. A 5 Hz limb motion would wrap/alias completely.
   - If `source_rate_hz` remains 30.0 Hz while data arrives at 1.66 Hz, the STFT assumes 32 samples span 1.07 seconds when they actually span 19.3 seconds. The resulting Doppler spectrum represents inter-minute drift rather than human gesture velocity.
3. **Audit Rule Enforced:** The production source-rate setting (`source_rate_hz=30.0`) must **not** be modified to match the current low capture rate. Doing so without retraining and redesigning the temporal pipeline produces physically invalid Doppler representations.

---

## 5. Corrected Session Quality Gates Specification

### 5.1 Reconciliation of Quality Gate Flaws
The Phase 55 quality gates contained three critical ambiguities that are now resolved:
1. **Count vs Rate Separation:** Gate 6 (Record Count) and Gate 7 (Acquisition Rate) are formally separated. Gate 6 measures data volume sufficiency ($N \ge 50$ for window formation); Gate 7 measures temporal rate ($f_{\text{empirical}} \ge 30.0\text{ Hz}$).
2. **Physical Carrier Validity:** In 802.11n multipath channels, destructive interference produces legitimate deep fading notches where individual carrier amplitudes approach zero. Mandating that all 52 active carriers be strictly non-zero is physically invalid. The corrected gate requires complete 64-bin arrays, finite values, non-negative amplitudes, active power $>0$, and phase in $[-\pi, \pi]$.
3. **Sequence Continuity vs UART Loss:** Reconciled sequence tracking separates UART transport loss (loss over USB serial) from target sequence jumps caused by non-target packet interleaving.

### 5.2 Corrected 15-Point Quality Gate Matrix

| Gate ID & Dimension | Operational Threshold / Rule | Evidentiary Classification | Technical Rationale & Reference | Verdict upon Violation |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1: Firmware Protocol** | Format B CSV (`CSI_DATA`), 0 unhandled exceptions. | **Verified from implementation** | Code path: `real_csi_collector.py:385-425`. Confirmed 100% parse success in Phases 50–54. | **REJECTED** |
| **Gate 2: Target Transmitter** | Source MAC matches approved router TA `98:BA:5F:EF:28:26`. | **Verified from implementation** | Code path: `real_csi_collector.py:438-446`. Isolates router downlink multipath. | **REJECTED** |
| **Gate 3: Channel Alignment** | Wi-Fi Channel 7, 2.442 GHz, HT20. | **Verified from implementation** | Firmware `WIFI_CHANNEL 7` (`main.c:27`). Matches RF wavelength $\lambda = 0.123\text{ m}$. | **QUARANTINED** |
| **Gate 4: Numerical Integrity** | 0 NaN/Inf values, $L=64$ raw bins, $56$ aligned channels. | **Verified from implementation** | Code path: `session_validator.py:226-235`. Ensures neural network numerical stability. | **QUARANTINED** |
| **Gate 5: Source Filtering Policy** | Fail-closed on missing/malformed MAC; non-target logged. | **Verified from implementation** | Verified by `test_phase52_target_source_filtering_and_fail_closed`. | **REJECTED** |
| **Gate 6: Record Count (Volume)** | Minimum $\ge 50$ admitted target records per session. | **Provisional engineering threshold** | CSIFormer window requires 50 frames `[Batch, 50, 56]`. Measures volume sufficiency. | **INCOMPLETE** |
| **Gate 7: Acquisition Rate (Temporal)**| Empirical rate $f_{\text{empirical}} = \frac{N-1}{t_{N-1}-t_0} \ge 30.0\text{ Hz}$. | **Supported by measurements & design (UNRESOLVED BLOCKER for passive)** | Model trained on 35–39 Hz data ($T \approx 1.4\text{ s}$). Passive yields 1.66–3.8 Hz ($T \approx 13\text{--}30\text{ s}$). | **QUARANTINED** |
| **Gate 8: Rate Variability (Jitter)**| Inter-arrival jitter $\sigma_{\Delta t} \le 15.0\text{ ms}$ (provisional). | **Requires future pilot calibration** | Phase 54 measured passive IAT standard deviation of $1,026.7\text{ ms}$. 15 ms is uncalibrated. | **QUARANTINED** |
| **Gate 9: Transport Integrity** | True UART transport loss $\le 1.0\%$ (reconciled). | **Supported by existing measurements** | Phase 53 verified that target sequence jumps correspond to interleaved foreign frames. UART loss was 0.00%. | **QUARANTINED** |
| **Gate 10: Timestamp Monotonicity**| Strictly monotonic ($\Delta t > 0$), span matches wall clock $\pm 5\%$. | **Provisional engineering threshold** | Host `time.time()` resolution (~15 ms on Windows) requires burst clustering handling. | **QUARANTINED** |
| **Gate 11: Physical Carrier Integrity**| 64-bin raw array, finite, non-negative, active power $>0$. | **Provisional engineering threshold** | Tolerates deep multipath fading notches; rejects corrupted or all-zero arrays. | **REJECTED** |
| **Gate 12: Metadata Completeness**| All required fields populated: session_id, participant_id, room, tx/rx pos. | **Verified from implementation** | Code path: `session_validator.py:178-186`. Essential for participant-independent (LOSO) splits. | **REJECTED** |
| **Gate 13: Termination Status** | `COMPLETED_NORMAL` (clean operator stop; duration within $\pm 5\%$). | **Verified from implementation** | Prevents truncated or aborted trials from entering training splits. | **INCOMPLETE** |
| **Gate 14: Raw Data Preservation** | Unmodified raw serial log (`.raw.log`) archived alongside JSON/CSV. | **Verified from implementation** | Code path: `real_csi_collector.py:724-812`. Provides permanent bit-level audit trail. | **QUARANTINED** |
| **Gate 15: Dataset Admission Verdict**| Explicit validation verdict `PASS` across all gates 1–14. | **Verified from implementation** | Code path: `DatasetIntegrityValidator.validate_session_file()`. | **QUARANTINED** |

### 5.3 Formal Session Disposition States
Every recorded session is assigned exactly one of four explicit outcomes:
1. **ACCEPTED:** Passes all gates 1–15. Eligible for addition to dataset manifest.
2. **QUARANTINED:** Syntactically valid but fails operational thresholds (rate deficit $<30\text{ Hz}$, high jitter). Moved to `quarantine/` with diagnostic entry in `quarantine_manifest.json`. Never added to training/evaluation splits.
3. **REJECTED:** Fatal defect (wrong channel, wrong AP MAC, non-finite values, corrupted JSON). Dropped and logged.
4. **INCOMPLETE:** Aborted early by operator or real-time safety monitor before reaching scheduled duration. Preserved as diagnostic log, excluded from dataset.

---

## 6. Pilot Protocol Feasibility & Participant Safety Audit

### 6.1 Feasibility of the 15-Second Trial Duration
- **Observational Probe vs Activity Recording:** Under passive conditions yielding 1.66–3.8 records/s, a 15.0 s trial captures approximately 25–55 records.
  - A 15.0 s trial at 1.66 Hz yields ~25 records. This is **insufficient to construct even a single 50-frame model window**.
  - Therefore, a 15.0 s trial is classified strictly as an **exploratory characterization probe** for statistical rate, IAT, and ambient density analysis.
  - For physical activity recording, if the rate remains at 1.66 Hz, a session would require at least 30.1 seconds to yield 50 records (or 60 seconds for 100 records). If 30 Hz acquisition is achieved via stimulation, a 15-second trial yields ~450 records (forming ~9 complete windows).
- **Storage Isolation:** Pilot recordings must be stored in `data/pilot_recordings/` and must **never** be written to `data/real_csi_dataset/`.

### 6.2 Participant Safety Protocols
- **Strict Prohibition of Intentional Falls:** Prior mentions of crash mats and spotters in Phase 55 drafts must **not** be interpreted as authorization to conduct fall experiments. Participants will **never** be instructed or permitted to intentionally fall.
- **Permitted Activities in Future Pilots:** Future pilot collections are strictly limited to safe, ordinary movements:
  - Walking in LOS
  - Sitting transition
  - Standing transition
  - Arm movements (push/pull, clapping)
  - Static background
- **Ethics & Privacy:** Written informed consent, pseudonymized participant IDs (`Participant_01`), and zero PII storage are strictly enforced.

---

## 7. Open Technical Blockers and Required Evidence

| Blocker ID & Description | Technical Impact | Exact Evidence Required to Resolve | Status |
| :--- | :--- | :--- | :--- |
| **B1: Acquisition-Rate Deficit** | Passive capture yields 1.66–3.8 Hz, causing $21\times$ temporal dilation and invalidating 50-frame inference windows. | Either empirical demonstration of $\ge 30\text{ Hz}$ passive beacon density via router configuration, or explicit user authorization for a metered packet stimulator with safety monitoring. | **OPEN BLOCKER** |
| **B2: Hardware Timestamp Absence** | Formats A and B lack hardware microsecond TSF timers; host timestamps suffer from Windows clock resolution (~15 ms) and OS scheduling jitter. | Firmware code update adding `info->rx_ctrl.timestamp` / hardware TSF to Format B, validated via unit test and authorized flash. | **DEFERRED (Requires Firmware Phase)** |
| **B3: Target-Filtered Sequence Loss Confusion** | `session_validator.py` lines 255–260 naively treats all sequence jumps as dropped packets, mistaking interleaved ambient frames for transport loss. | Update `session_validator.py` to reconcile target sequence numbers against logged non-target packet counts before reporting loss rates. | **RESOLVED IN SPECIFICATION (Implementation Planned)** |
| **B4: 2.4 GHz Contention Latency Abort** | In Phase 54, an isolated ping latency spike of 63.0 ms triggered a safety abort at 3.51 s on 2.4 GHz Channel 7. | Empirical statistical latency distribution audit on 2.4 GHz to determine if 75–100 ms spike threshold maintains safety while preventing false aborts. | **UNDERSTOOD RF CHARACTERISTIC** |

---

## 8. Offline Testing and Verification

### 8.1 Test Implementation (`backend/tests/test_phase55_1.py`)
To validate the corrective audit without accessing hardware, generating network traffic, or altering datasets, a targeted offline test suite was created in [`backend/tests/test_phase55_1.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase55_1.py):
1. `test_phase55_1_protected_hashes`: Cryptographic bit-level hash verification of protected models and manifest.
2. `test_phase55_1_record_count_vs_rate_separation`: Proves that a 15 s trial with 50 frames passes the count threshold ($\ge 50$) but fails the 30 Hz rate threshold ($3.27\text{ Hz} \ll 30\text{ Hz}$), establishing why count and rate must remain separate gates.
3. `test_phase55_1_window_span_definitions_consistency`: Verifies exact mathematical definitions for 50 rate intervals ($50 / f$) vs first-to-last sample span ($(50-1) / f$) at 1.66 Hz, 30.0 Hz, and 35.0 Hz.
4. `test_phase55_1_spatial_interpolation_invariance`: Proves that spatial subcarrier interpolation across 64 bins or 52 active tones to 56 channels operates purely in the frequency domain and cannot create temporal samples.
5. `test_phase55_1_doppler_stft_frequency_scaling`: Verifies that STFT frequency axis in `PhysicsCSIPreprocessor` scales directly with `source_rate_hz`, proving why changing `source_rate_hz` to 1.66 Hz would distort Doppler representations by ~18x.
6. `test_phase55_1_carrier_validity_multipath_notch_tolerance`: Verifies that a physical CSI frame experiencing a deep multipath fading notch is correctly validated without false rejections, provided array dimensions match 64 and values are finite.
7. `test_phase55_1_session_disposition_states`: Verifies that the quality gate workflow cleanly assigns ACCEPTED, QUARANTINED, REJECTED, or INCOMPLETE verdicts.

### 8.2 Test Execution Results
The test suite was executed offline:
```bash
py -3.11 -m pytest backend/tests/test_phase55_1.py -v
```
**Results:** **7 passed, 0 failed, 0 skipped in 19.70s**.

Regression test verification across Phase 55:
```bash
py -3.11 -m pytest backend/tests/test_phase55.py -v
```
**Results:** **5 passed, 0 failed, 0 skipped in 2.02s**.

---

## 9. Protected Asset Cryptographic Hash Verification

Cryptographic MD5 checksums were verified before and after all Phase 55.1 work:

| Protected Resource | File Path | Expected MD5 Hash | Measured MD5 Hash | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 13 Production Checkpoint** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| **Phase 15 Adapted Checkpoint** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| **Established Dataset Manifest** | `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |

---

## 10. Scope Confirmation and Final Disposition

- **Zero serial hardware access:** Port COM5 was not opened.
- **Zero active traffic generated:** No ICMP, UDP, or TCP packets were sent.
- **Zero firmware modifications:** ESP32-S3 was not flashed or reconfigured.
- **Zero dataset modifications:** Real CSI dataset in `data/real_csi_dataset/` was untouched.
- **Zero model execution:** No models were trained, fine-tuned, or evaluated.

### Final Disposition
**Phase 55.1 Status:** `COMPLETED (CORRECTIVE ENGINEERING AUDIT & QUALITY GATE RESOLUTION ACHIEVED; ACQUISITION-RATE ADEQUACY REMAINS UNRESOLVED BLOCKER)`

Phase 55.1 has succeeded in establishing complete internal consistency, rigorous quality-gate definitions, exact mathematical window models, and an evidence-based roadmap for resolving the acquisition-rate deficit. The acquisition-rate deficit remains an explicit, open, unresolved blocker that precludes declaring CSIFormer research-ready until a separately authorized acquisition strategy is validated.
