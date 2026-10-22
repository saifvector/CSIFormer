# Phase 55 Report — Pilot Campaign Planning and Acquisition Strategy

**Document Version:** 1.0.0  
**Phase:** 55  
**Date:** 2026-10-20  
**Status:** `COMPLETED (PLANNING & AUDIT DELIVERABLES ACHIEVED; ACQUISITION-RATE ADEQUACY REMAINS UNRESOLVED BLOCKER)`  
**Safety Protocol:** Zero live serial access on COM5, zero active network traffic generation, zero firmware flashing or reconfiguration, zero real CSI data collection or modification, zero model retraining or evaluation, zero protected checkpoint or manifest alterations, zero git commits or pushes.

---

## 1. Executive Summary & Mandatory Phase 54 Closure Decision

### 1.1 Formal Phase 54 Closure Decision
Pursuant to Phase 55 directives, **the Phase 54 traffic experiment is formally concluded and closed**.
- The experiment will **not** be repeated, extended, optimized, or forced to completion.
- No ICMP or other active network traffic was generated during Phase 55.
- The latency-abort safety threshold was **not** increased to bypass medium contention.
- No further acquisition-rate experiments were attempted.
- The ESP32-S3 firmware was **not** flashed, erased, or reconfigured.
- No real data-collection session was initiated, resumed, or altered.
- The aborted active test in Phase 54 is **not** interpreted as evidence that network traffic increases or decreases CSI acquisition rate.

### 1.2 Critical Unresolved Blocker: Acquisition-Rate Adequacy
The acquisition-rate requirement has **NOT** been demonstrated to be satisfied.
- **Phase 54 Direct Measurements:**
  - Passive baseline duration: $10.23\text{ seconds}$.
  - Total CSI records: $26$.
  - Target-BSSID records admitted (`98:BA:5F:EF:28:26`): $17$.
  - Non-target records filtered (`18:CC:88:7E:74:71`): $9$.
  - Passive target-record rate: $\approx 1.66\text{ records/s}$ ($1.66\text{ Hz}$).
  - Active test (5 pkts/s ICMP): Safely aborted at probe 15 ($3.51\text{ s}$) when observed latency spiked to $63.0\text{ ms}$ (exceeding the $50.0\text{ ms}$ abort threshold).
  - Probe responses: 15/15 ($0.0\%$ loss, mean RTT $10.6\text{ ms}$, max RTT $63.0\text{ ms}$).
  - CSI records during the aborted active interval: $6$ total ($3$ target, $3$ non-target, including physical capture of the host laptop's MediaTek client MAC `60:E9:AA:2C:9A:83`).
  - Target-record rate during the aborted interval: $\approx 0.85\text{ records/s}$.
- **Analytical Assessment:**
  - The short 3.51-second active interval is insufficient to establish any reliable acquisition-rate change or causal relationship between network traffic and CSI capture performance.
  - The historical rate of $\approx 36.8\text{ Hz}$ recorded in `data/real_csi_dataset/dataset_manifest.json` cannot be assumed achievable under passive operating conditions. Forensic code audit in Phase 55 reveals that historical sessions were collected under active UDP traffic stimulation (`UdpStimulator` targeting `192.168.0.232:5555` at $35.0\text{ Hz}$ in `backend/app/services/collection_workflow.py`).
  - **Phase 55 Finding:** Acquisition-rate adequacy is formally recorded as an **unresolved acquisition-readiness blocker**. A future passive-only method for assessing acquisition rate is defined herein, but the requirement is **not** declared satisfied, no arbitrary minimum rate is fabricated, and no live measurements were conducted during this phase.

---

## 2. Continuity, Evidence Distinction, and Safety Rules

### 2.1 Epistemological Evidence Classification
To maintain strict scientific and engineering rigor, all project findings are classified into five distinct categories:

1. **Verified Repository and Log Evidence:**
   - ESP32-S3 hardware identity: QFN56 revision v0.2, 16 MB flash, 8 MB embedded PSRAM, MAC `d4:05:92:7b:2e:d0`.
   - Firmware sequence counter assignment: Global `static uint32_t packet_sequence` in `firmware/esp32s3_csi_collector/main/main.c:34`, incrementing on every non-null CSI callback regardless of transmitter MAC.
   - UART serial transport loss in Phase 51, 52, 53, and 54 was strictly **0.00%** (zero transport packet loss over USB-UART bridge at 115,200 baud).
   - In `RealCSICollector`, timestamps originate on the host computer (`time.time()`) upon serial reception, and are **discarded** when forming sliding windows (`deque(maxlen=50)`).
   - Historical dataset in `data/real_csi_dataset/dataset_manifest.json` contains 74 sessions with sampling rates between 35.0 and 39.0 Hz, generated via active background UDP stimulation.
2. **Previously Reported but Unverified Results:**
   - Absolute radio-frequency multipath stability in multi-room environments across extended (hours-long) collection campaigns.
   - Long-term clock drift and host timestamp jitter under high CPU load.
3. **Engineering Hypotheses:**
   - The 63.0 ms latency spike observed during Phase 54 on 2.4 GHz was hypothesized to be caused by CSMA/CA 802.11 backoff or co-channel interference. (Unproven without an external RF spectrum analyzer; treated strictly as an unverified hypothesis).
   - The hypothesis that passive beacon snooping alone could satisfy human activity recognition temporal resolution without active network stimulation. (Falsified by mathematical temporal window audit).
4. **Proposed Acceptance Criteria:**
   - Formal session quality gates defining acceptable SNR, missing carrier bounds, timestamp monotonicity, and sequence continuity.
5. **Unresolved Research Questions:**
   - Can passive operating conditions ever achieve temporal sampling rates adequate for human motion kinematics without active traffic generation?
   - What is the maximum acceptable temporal window dilation before CSIFormer transformer self-attention collapses?

### 2.2 Prohibited Operations Audit
During Phase 55, all ten prohibited operations were strictly observed:
1. ESP32-S3 was not flashed, erased, reset, or reconfigured.
2. COM5 was not opened for live acquisition or hardware diagnostics.
3. Zero network traffic (no ping, iperf, UDP, or ICMP) was generated.
4. No real CSI data was collected, recorded, resumed, or altered.
5. No machine learning models were trained, fine-tuned, benchmarked, or evaluated.
6. Production preprocessing, firmware code, and acquisition logic were not altered.
7. Zero dataset or session files were deleted, overwritten, renamed, or relocated.
8. Protected checkpoints and the dataset manifest were not modified.
9. No git commits or pushes were executed.
10. Phase 56 was not started automatically.

---

## 3. Repository Inspection and Evidence Inventory

### 3.1 Inspected Files and Components
The following files across the workspace were inspected and audited:

| Component | File Path | Actual Status & Key Role |
| :--- | :--- | :--- |
| **Firmware Source** | [`firmware/esp32s3_csi_collector/main/main.c`](file:///C:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c) | Audited lines 1–205: Global sequence counter, Format B serialization, Channel 7 HT20 configuration. |
| **Collector Engine** | [`backend/app/services/real_csi_collector.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/real_csi_collector.py) | Audited lines 1–874: Source filtering, timestamp generation (`time.time()`), sliding window buffer `[50, 56]`, and serialization. |
| **Hardware Adapter** | [`backend/app/services/esp32_csi_adapter.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_csi_adapter.py) | Audited lines 1–289: HT20 64-bin carrier masks (52 active data tones, 12 DC/guard nulls). |
| **Session Validator** | [`backend/app/services/session_validator.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/session_validator.py) | Audited lines 1–392: `compute_session_sampling_rate()`, session validation rules, and quarantine workflow. |
| **Collection Workflow** | [`backend/app/services/collection_workflow.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/collection_workflow.py) | Audited lines 1–508: Discovered active `UdpStimulator` (35 Hz background traffic to `192.168.0.232:5555`). |
| **Collection CLI** | [`scratch/run_collection_session.py`](file:///C:/Users/saifu/Desktop/4-1%20project/scratch/run_collection_session.py) | Audited lines 1–268: Operator-guided session recording, safety fall warnings, and manifest validation. |
| **Split Generator** | [`backend/app/services/split_generator.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/split_generator.py) | Audited lines 1–419: Participant-independent (LOSO) partition constraints and event grouping. |
| **Live Pipeline Service**| [`backend/app/services/live_pipeline_service.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/live_pipeline_service.py) | Audited lines 1–237: Real-time inference coordinator, sliding window consumption, and label mapping. |
| **Physics Preprocessor**| [`backend/app/services/physics_csi_preprocessor.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py) | Audited lines 1–338: Phase sanitization, STFT Doppler spectrum, and `source_rate_hz=30.0` assumption. |
| **Dataset Manifest** | [`data/real_csi_dataset/dataset_manifest.json`](file:///C:/Users/saifu/Desktop/4-1%20project/data/real_csi_dataset/dataset_manifest.json) | Audited 74 physical sessions, 10,407 frames, confirmed 35.0–39.0 Hz historical rate baseline. |
| **Phase 50 Report** | [`reports/phase50_recovery_firmware_deployment.md`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase50_recovery_firmware_deployment.md) | Verified recovery deployment, bootloader logs, and 8.25 s smoke test. |
| **Phase 51 Report** | [`reports/phase51_csi_stream_integrity_and_pilot_readiness.md`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase51_csi_stream_integrity_and_pilot_readiness.md) | Verified 15.04 s stream integrity audit, 64-bin FFT spectrum structure, 0.00% UART loss. |
| **Phase 52 Report** | [`reports/phase52_source_filtering_and_subcarrier_readiness.md`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase52_source_filtering_and_subcarrier_readiness.md) | Verified source filtering implementation, fail-closed policy, and HT20 carrier masks. |
| **Phase 53 Report** | [`reports/phase53_sequence_semantics_and_rate_feasibility.md`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase53_sequence_semantics_and_rate_feasibility.md) | Verified global sequence counter lifecycle, gap reconciliation, and 18x temporal dilation audit. |
| **Phase 54 Report** | [`reports/phase54_controlled_acquisition_rate_experiment.md`](file:///C:/Users/saifu/Desktop/4-1%20project/reports/phase54_controlled_acquisition_rate_experiment.md) | Verified in-band vs cross-band ICMP test, safety abort at probe 15, and 1.66 Hz passive rate. |

---

## 4. Technical Audit of Phase 50–54 Findings

### 4.1 Phase 50 — Recovery Firmware Deployment
- **Verified Facts:** The Phase 48 CSI driver initialization crash (`ESP_FAIL` in `esp_wifi_set_csi_config`) was resolved in Phase 49/50 by initializing network interfaces (`esp_netif_init()`), creating default event loops, and setting `cfg.csi_enable = 1`. Boot logs confirmed `app_main()` initialization of STA promiscuous mode on Channel 7.
- **Audited Metrics:** 8.25 s bounded smoke test parsed 27 Format B packets, 0 errors, RSSI $-59\text{ dBm}$ to $-62\text{ dBm}$.

### 4.2 Phase 51 — CSI Stream Integrity & Subcarrier Geometry
- **Verified Facts:** 15.04 s bounded stream ingested 57 Format B frames with zero malformed lines and zero UART packet loss ($0.00\%$).
- **Subcarrier Ground Truth:** In IEEE 802.11n HT20 mode, the ESP32-S3 MAC hardware supplies 64 complex subcarrier bins ($128\text{ bytes}$). The active spectrum consists of **52 active data/pilot subcarriers** (bins 1–26 and 38–63) and **12 null bins** (DC center carrier at bin 0, and 11 guard carriers at bins 27–37).

### 4.3 Phase 52 — Source Filtering and Carrier Masking
- **Verified Facts:** The parsed `mac` field in Format B represents Address 2 (Transmitter Address / TA) of the 802.11 MAC header.
  - Downlink transmissions from the router have `TA == BSSID` (`98:BA:5F:EF:28:26`).
  - Uplink transmissions from mobile/laptop clients have `TA == Client MAC` (e.g. `80:5E:4F:21:03:FA`, `18:CC:88:7E:74:71`, `60:E9:AA:2C:9A:83`).
- **Filter Efficacy:** `RealCSICollector` implements `target_mac="98:BA:5F:EF:28:26"` and `filter_by_mac=True`. If `mac` is missing or invalid, the filter fails closed, increments `self.parse_errors`, and discards the frame.

### 4.4 Phase 53 — Sequence Counter Lifecycle and Interleaving Reconciliation
- **Verified Facts:** In `firmware/esp32s3_csi_collector/main/main.c`, `static uint32_t packet_sequence = 0` is defined at file scope. It increments unconditionally inside `wifi_csi_cb()` for *every* frame received on Channel 7.
- **Reconciliation of "Lost" Packets:** When ambient non-target frames are received, `packet_sequence` increments. Because the host source filter discards non-target frames, the sequence numbers in the admitted target stream exhibit gaps. In Phase 53, a 10.0 s diagnostic verified that all 13 reported target sequence jumps corresponded 1:1 with interleaved non-target frames. **Actual physical transport loss over UART was 0.00%**.

### 4.5 Phase 54 — Controlled Acquisition-Rate Experiment Closure
- **Verified Facts:** Passive baseline over 10.23 s yielded 17 target records ($1.66\text{ Hz}$). During authorized ICMP stimulation on Channel 7, probe 15 triggered an immediate safety abort at 3.51 s due to an isolated latency spike of $63.0\text{ ms} > 50.0\text{ ms}$.
- **Closure:** Phase 54 is closed. The aborted test confirms the responsiveness of the real-time safety monitor, but cannot establish steady-state rate scalability.

---

## 5. The Pilot Campaign's Core Research Questions

A future authorized pilot campaign must be designed to answer eight specific research questions:

| ID | Research Question | Current Evidence Baseline | Unresolved Information | Proposed Passive Measurement Method | Decision Supported by Evidence |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **Q1** | Can ESP32-S3 consistently capture and parse CSI records associated with target AP under passive conditions? | Phases 50–54 captured target AP records (`98:BA:5F:EF:28:26`) with 0 parser errors across all tests. | Long-term parser stability over multi-hour passive listening sessions. | Repeated passive observation trials with automated Format B syntax verification. | Validates whether passive capture is sufficiently robust for long-duration operation. |
| **Q2** | What target-record rate and rate variability occur across repeated passive observation periods? | Single trials showed 1.66 Hz (Phase 54), 3.20 Hz (Phase 52), 3.79 Hz (Phase 51). | Statistical distribution, variance, and minimum rate across diverse times of day. Short 15 s trials cannot establish long-term rate stability. | Compute mean, standard deviation, and IQR of target inter-arrival times across 10 repeated passive trials. | Quantifies empirical passive rate bounds; informs feasibility of passive-only probes. |
| **Q3** | How do source filtering and physical-carrier extraction behave when target and non-target transmitters are present? | Phase 52 & 54 proved 100% rejection of foreign MACs (`18:CC..`, `80:5E..`, `60:E9..`). | Filter CPU overhead and buffer pressure under dense ambient Wi-Fi traffic. | Log admitted vs filtered counts under varying ambient RF loads; verify subcarrier masks. | Confirms single-channel multipath isolation without antenna contamination. |
| **Q4** | Are timestamps, sequence numbers, raw measurements, and metadata preserved accurately throughout pipeline? | Collector records `timestamp` (host), `sequence` (global firmware counter), `raw_amplitudes` (64), `physical_active_amplitudes` (52). | Host timestamp jitter under Windows timer resolution (~15 ms default) and OS process scheduling. | Verify strict monotonicity, timestamp span matching wall-clock duration, and sequence reconciliation. | Ensures full data provenance and auditability for research datasets. |
| **Q5** | Can the pipeline detect malformed, truncated, incomplete, or low-quality sessions? | `session_validator.py` checks file presence, NaN/Inf, frame counts, and monotonicity. | Real-time session rejection before writing corrupt JSON files to disk. | Run synthetic corrupted sessions through `DatasetIntegrityValidator` and test quarantine routing. | Prevents silent dataset contamination. |
| **Q6** | What evidence is required before a session can be accepted into the research dataset? | Manifest schema requires validated frame count, pseudonymized participant ID, and confirmed label. | Comprehensive quality gate thresholds calibrated against physical pilot trials. | Apply the 15-point Session Quality Gate specification defined in Section 9. | Sets explicit gate for admitting vs quarantining recorded sessions. |
| **Q7** | Is the observed acquisition rate adequate for the actual model's temporal assumptions? | CSIFormer window `[50, 56]` was trained on 35–39 Hz data ($T \approx 1.4\text{ s}$). Passive rate is 1.66–3.8 Hz ($T \approx 13\text{--}30\text{ s}$). | Exact quantitative performance drop across activity classes under temporal dilation. | Compare temporal window duration (50 intervals: $50 / f$; first-to-last sample span: $49 / f$) against human gesture duration ($1.0\text{--}2.0\text{ s}$). | **Unresolved Blocker:** Confirms that passive acquisition creates severe temporal dilation ($11\times\text{--}21\times$). |
| **Q8** | Can acquisition-rate adequacy be established from historical evidence, or does it require a future pilot? | Historical manifest shows 35+ Hz, but code audit shows it required active UDP stimulation. | Whether passive beacon tuning (e.g. router beacon interval) can achieve $\ge 30\text{ Hz}$. | Design passive-only pilot protocol to measure maximum passive beacon density. | Establishes whether active traffic is mandatory or if passive pilot can be calibrated. |

---

## 6. Future Passive-Only Pilot Protocol Design

*(Design specification for future separately authorized campaign. Zero hardware access or active tests were executed in Phase 55).*

### 6.1 Preflight Checklist Specification
Before any future authorized session, an automated preflight script must verify:
1. **ESP32-S3 Identity:** Chip is responsive on COM5, MAC matches `d4:05:92:7b:2e:d0`, chip revision v0.2.
2. **Firmware Verification:** Running Phase 49/50 recovery firmware build (`b5262e456...`), baud rate 115,200 console / 921,600 transport.
3. **Serial Port Availability:** COM5 is free, uncontended, and cleanly claimable.
4. **Target AP Verification:** Lab AP BSSID is verified as `98:BA:5F:EF:28:26` via active OS scan.
5. **Channel Alignment:** Wi-Fi channel is confirmed as Channel 7 (2.442 GHz HT20).
6. **Parser Compatibility:** Ingest parser validates Format B CSV grammar (`CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,...`).
7. **System Clock & Timestamps:** Host high-resolution timer (`time.perf_counter()` / `time.time()`) is verified monotonic.
8. **Storage & Path Isolation:** Designated pilot staging directory (`data/pilot_recordings/`) exists with $\ge 5\text{ GB}$ free disk space.
9. **Protected Asset Hashes:** Hashes of Phase 13, Phase 15 checkpoints and `dataset_manifest.json` match expected MD5s.
10. **Passive-Only Enforcement:** Explicit configuration lock confirming zero active traffic generators (UDP, ICMP, TCP) are active.

### 6.2 Observation Protocol
- **Trial Duration:** Proposed **15.0 seconds** per trial.
  - *Critical Protocol Clarification:* Under passive conditions yielding $\sim 1.66\text{--}3.8\text{ Hz}$, a 15.0 s trial captures approximately 25–55 target records. This trial duration is designed **strictly as an exploratory characterization probe** to evaluate passive beacon inter-arrival time (IAT) statistics, ambient traffic density, and receiver stability. It is **not** an activity recording protocol for model inference, because at 1.66 Hz, 15 seconds yields only ~25 frames, which cannot even populate a single 50-frame model window.
- **Trial Replication:** Proposed **10 repeated trials** per session, spaced by 30-second quiet intervals.
- **Environmental Controls:** Fixed device placement (ESP32-S3 antenna orientation vertical, Tx-Rx distance $2.5\text{ m}$ LOS), clear room occupancy logging, and documentation of all co-channel interferers.
- **Data Traceability:** Raw serial output must be captured bit-for-bit to `.raw.log` alongside parsed `.json` and `.csv` files.

### 6.3 Automated Stop Conditions
The acquisition engine must abort immediately if any of the following occur:
1. Receipt of unexpected firmware crash banners, panic logs, or watchdog resets.
2. Cumulative parser errors exceed 2% of detected lines.
3. Serial port disconnection, buffer overrun, or USB-UART driver stall.
4. Channel hopping or unexpected AP BSSID change detected in frame headers.
5. Truncated or corrupted CSI payload buffers (subcarrier count $\ne 64$ for HT20).
6. Host disk write error or disk space dropping below 1 GB.
7. Any condition that risks contaminating the existing production dataset in `data/real_csi_dataset/`.

---

## 7. Source Filtering and Physical Carrier Representation Audit

### 7.1 Transmitter Address (TA) vs BSSID Semantics
In `firmware/esp32s3_csi_collector/main/main.c:47-49`, the firmware copies `info->mac` directly into the Format B header:
```c
snprintf((char*)mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
         info->mac[0], info->mac[1], info->mac[2],
         info->mac[3], info->mac[4], info->mac[5]);
```
- **802.11 MAC Frame Structure:** `info->mac` is Address 2 of the IEEE 802.11 MAC header, which designates the physical **Transmitter Address (TA)**.
- **Frame Type Analysis:**
  - **Downlink Beacon / Probe Response / Data:** `TA == BSSID` (`98:BA:5F:EF:28:26`). In this specific downlink scenario, the Transmitter Address matches the router's BSSID.
  - **Uplink Client Probe Request / Data / ACK:** `TA == Client Station MAC` (e.g. laptop `60:E9:AA:2C:9A:83`). The parsed MAC is the client station, *not* the BSSID (the BSSID resides in Address 1 RA or Address 3).
- **Filtering Contract:** Setting `target_mac="98:BA:5F:EF:28:26"` and `filter_by_mac=True` in `RealCSICollector` isolates downlink multipath reflections from the router, discarding all client transmissions. The field represents TA, not an invariant BSSID.

### 7.2 IEEE 802.11n HT20 64-Bin Subcarrier Partitioning
In `backend/app/services/esp32_csi_adapter.py:40-85`:
```python
HT20_64_TOTAL_BINS = 64
HT20_64_ACTIVE_DATA_INDICES = np.concatenate([np.arange(1, 27), np.arange(38, 64)])  # 52 active tones
HT20_64_NULL_INDICES = np.concatenate([[0], np.arange(27, 38)])  # 12 null/guard tones
```
- **Physical Provenance:** The 52 active tones represent true electromagnetic channel measurements across OFDM subcarrier frequencies.
- **Null Carriers:** Bin 0 is the direct current (DC) null carrier (zeroed by baseband receiver). Bins 27–37 are band-edge guard carriers (zeroed by digital spectral shaping).
- **Model Invariance:** In `RealCSICollector._process_parsed_frame()`, raw 64-bin subcarrier arrays are resampled to 56 subcarriers via `np.interp` to maintain strict input tensor compatibility `[50, 56]` for CSIFormer. The un-interpolated 52 active tones and 12 null tones are preserved separately in `rec_frame["physical_active_amplitudes"]` and `rec_frame["physical_null_amplitudes"]`.
- **Critical Distinction:** Spatial/channel interpolation (from 52 active tones or 64 raw bins to 56 model channels) is strictly an interpolation across the **spatial / frequency domain**. It does **not** and **cannot** alter the temporal dimension or create missing temporal observations.

---

## 8. Timestamps, Sampling Semantics, and Temporal Window Audit

### 8.1 Timestamp Provenance and Clock Domain
- **Origin:** All packet timestamps in `RealCSICollector` originate on the **host computer** via `time.time()` at lines 372 and 414.
- **Firmware Timestamp:** The ESP32-S3 firmware does **not** attach a microsecond hardware timer (TSF) to Format B serial strings.
- **Clock Meaning:** The host timestamp represents serial packet arrival/parsing time on the PC, subject to USB-UART buffer latency and OS process scheduling.
- **Clock Resolution & Duplicate Risk:** On Windows, standard `time.time()` resolution is typically 15.6 ms. When serial bytes are ingested in multi-line chunks, adjacent lines parsed in the same buffer burst can receive identical or near-identical timestamps. A strict zero-duplicate timestamp check must account for host clock discretization.

### 8.2 Sliding Window Buffering, Rate Assumption, and Timestamp Discard
In `RealCSICollector.get_latest_window()`:
```python
raw_win = np.stack(list(self.raw_frame_buffer), axis=0)    # Shape: [50, 56]
phase_win = np.stack(list(self.phase_frame_buffer), axis=0)  # Shape: [50, 56]
return raw_win, phase_win
```
- **Critical Finding:** Timestamps are **completely discarded** upon temporal window formation.
- **30 Hz Assumption Entry Point:** In `backend/app/services/live_pipeline_service.py` line 58, `PhysicsCSIPreprocessor` is initialized with `source_rate_hz=30.0`. In `compute_doppler_spectrogram()`, this rate is passed directly to `scipy.signal.stft(..., fs=self.source_rate_hz)`.
- **Nature of the 30 Hz Value:** 30 Hz is a preprocessing configuration default chosen to approximate the nominal ~35 Hz rate of historical UDP-stimulated collection. It is not an experimentally validated passive listening rate.
- **Model Assumption:** The Transformer encoder uses learned positional encodings that treat index $t$ and $t+1$ as uniform time steps corresponding to $f_s \approx 30\text{--}35\text{ Hz}$ ($\Delta t \approx 28\text{--}33\text{ ms}$).

### 8.3 The Temporal Dilation Problem
- **Consistent Window Duration Definitions:**
  - **Duration by Rate Intervals ($N / f$):** The total time represented by 50 rate intervals.
    - At 35.0 Hz: $50 / 35.0 = \mathbf{1.429\text{ s}}$.
    - At 30.0 Hz: $50 / 30.0 = \mathbf{1.667\text{ s}}$.
    - At 1.66 Hz: $50 / 1.66 = \mathbf{30.12\text{ s}}$.
  - **First-to-Last Sample Elapsed Span ($(N - 1) / f$):** The exact interval between the first and 50th uniformly spaced sample.
    - At 35.0 Hz: $49 / 35.0 = \mathbf{1.400\text{ s}}$.
    - At 30.0 Hz: $49 / 30.0 = \mathbf{1.633\text{ s}}$.
    - At 1.66 Hz: $49 / 1.66 = \mathbf{29.518\text{ s}}$.
- **Dilation Factor:** $\frac{30.12\text{ s}}{1.43\text{ s}} \approx \mathbf{21.1\times\text{ temporal dilation}}$ (or $\frac{29.52\text{ s}}{1.40\text{ s}} \approx \mathbf{21.1\times}$).
- **Physical Consequence:** An activity occurring over 1.5 seconds occupies only 2–3 frames in a passive stream. The remaining 47 frames capture unrelated background noise, completely distorting attention weights and rendering velocity profiles uninterpretable.
- **Critical Caution:** A higher packet rate alone does **not** guarantee reliable human activity recognition. Multipath signal quality, line-of-sight geometry, signal-to-noise ratio, and phase detrending are equally critical physical prerequisites.

---

## 9. Session Quality Gates Specification

The session quality gates govern evaluation of physical CSI recordings. Each threshold is strictly classified by its evidentiary basis:

### 9.1 Evidentiary Classification Taxonomy
- **Verified from implementation or documented requirements:** Grounded in active codebase logic, specifications, or architectural invariants.
- **Supported by existing measurements:** Derived from empirical telemetry gathered during executed, verified project phases.
- **Provisional engineering threshold:** Reasonable engineering convention requiring future empirical validation.
- **Requires future pilot calibration:** Uncalibrated placeholder needing structured physical data before setting a definitive value.
- **Unresolved:** Fundamental architectural blocker where current hardware or operating mode cannot satisfy requirements.

### 9.2 The 15 Quality Gates

| Gate ID & Name | Proposed Threshold / Rule | Evidentiary Classification | Technical Rationale & Supporting Evidence | Consequence of Failure |
| :--- | :--- | :--- | :--- | :--- |
| **1. Firmware / Protocol** | Format B CSV (`CSI_DATA`), 0 unhandled exceptions. | **Verified from implementation** | Code path: `real_csi_collector.py:385-425`. Phase 50–54 telemetry confirmed 100% parse success on Format B. | Session rejected immediately; halt collection. |
| **2. Target Transmitter Identity** | Source MAC matches approved router TA / BSSID `98:BA:5F:EF:28:26`. | **Verified from implementation** | Code path: `real_csi_collector.py:438-446`. Isolates router downlink multipath from client uplink interference. | Non-target frames filtered; session rejected if admitted count = 0. |
| **3. Channel / Band** | Channel 7, 2.442 GHz, HT20. | **Verified from implementation** | Firmware `WIFI_CHANNEL 7` (`main.c:27`). Matches RF calibration and wavelength $\lambda = 0.123\text{ m}$. | Session quarantined; configuration re-audit required. |
| **4. Record Integrity** | 0 NaN/Inf values, complete subcarrier arrays ($L=64$ raw, $56$ aligned). | **Verified from implementation** | Code path: `session_validator.py:226-235`. Ensures numerical stability for deep neural network execution. | Session quarantined to `quarantine/`. |
| **5. Source Filtering** | Fail-closed on missing/malformed MAC; non-target count logged. | **Verified from implementation** | Phase 52 test `test_phase52_target_source_filtering_and_fail_closed`. Discards non-target and corrupt frames. | Corrupted frames dropped; session rejected if error count $> 2\%$. |
| **6. Record Count (Volume)** | Minimum $\ge 50$ admitted target records per session. | **Provisional engineering threshold** | Model architecture input requires tensor `[Batch, 50, 56]`. (Measures volume sufficiency, separate from rate). | Session marked `INCOMPLETE`; excluded from dataset. |
| **7. Acquisition Rate (Temporal)** | Empirical target rate $f_{\text{empirical}} = \frac{N-1}{t_{N-1}-t_0} \ge 30.0\text{ Hz}$. | **Supported by existing measurements & model design (UNRESOLVED BLOCKER for passive)** | Model trained at 35–39 Hz ($T \approx 1.4\text{ s}$). Passive listening yields only 1.66–3.8 Hz ($T \approx 13\text{--}30\text{ s}$). | Session rejected for production inference; quarantined. |
| **8. Rate Variability (Jitter)** | Inter-arrival jitter $\sigma_{\Delta t} \le 15.0\text{ ms}$ (provisional). | **Requires future pilot calibration** | Phase 54 measured passive IAT standard deviation of $1,026.7\text{ ms}$. The 15 ms threshold is an uncalibrated target. | Flagged with warning in metadata; quarantined if $\sigma > 50\text{ ms}$. |
| **9. Sequence Behavior** | True UART transport loss $\le 1.0\%$ (reconciled across transmitters). | **Supported by existing measurements** | Phase 53 verified that target sequence jumps correspond to interleaved non-target frames. UART loss was 0.00%. | Quarantined if unreconciled true loss $> 1.0\%$. |
| **10. Timestamp Integrity** | Strictly monotonic ($\Delta t > 0$), span matches wall clock ($\pm 5\%$). | **Provisional engineering threshold** | Host `time.time()` resolution (~15 ms on Windows) can cause burst clustering. Microsecond timer needed in firmware. | Session marked invalid; quarantined. |
| **11. Carrier Validity** | Subcarrier array $L=64$ raw, all finite, non-negative amplitudes, active power $> 0$. | **Provisional engineering threshold** | Deep multipath fading notches can cause legitimate near-zero active amplitudes. Mandating all 52 active tones $>0$ is physically invalid. | Session rejected if carrier mask mismatch or non-finite values found. |
| **12. Metadata Completeness** | All required fields populated: session_id, participant_id, room, tx/rx pos. | **Verified from implementation** | Code path: `session_validator.py:178-186`. Essential for participant-independent (LOSO) splits. | Session rejected until metadata completed. |
| **13. Termination Status** | `COMPLETED_NORMAL` (clean operator stop; duration within $\pm 5\%$). | **Verified from implementation** | Prevents truncated or aborted trials from entering training splits. | Aborted sessions logged as diagnostic, excluded from dataset. |
| **14. Data Preservation** | Unmodified raw serial log (`.raw.log`) archived alongside JSON/CSV. | **Verified from implementation** | Code path: `real_csi_collector.py:724-812`. Provides permanent bit-level audit trail for raw measurements. | Session quarantined if raw serial log missing. |
| **15. Dataset Eligibility** | Explicit validation verdict `PASS` across all gates 1–14. | **Verified from implementation** | Code path: `DatasetIntegrityValidator.validate_session_file()`. Prevents silent dataset contamination. | Session remains in staging/quarantine; never added to manifest. |

### 9.3 Formal Session Disposition States
Every recorded session must be assigned exactly one of four explicit disposition verdicts:
- **ACCEPTED:** Session satisfies all quality gates (1–15). Admitted to the verified pilot dataset.
- **QUARANTINED:** Session is syntactically intact but violates operational gates (e.g. rate deficit $< 30\text{ Hz}$ or high jitter). Moved to `quarantine/` with diagnostic record in `quarantine_manifest.json`. Never added to training or evaluation splits.
- **REJECTED:** Session exhibits fatal corruption, invalid AP/channel configuration, or non-finite values. Dropped and logged.
- **INCOMPLETE:** Session was aborted early by operator or automated safety trigger before reaching scheduled duration. Preserved as diagnostic trace, excluded from dataset.

---

## 10. Dataset Governance and Participant Safety

### 10.1 Proposed Session Metadata Schema
The pilot metadata schema builds upon existing `RealCSICollector` and `session_validator` definitions without breaking backward compatibility:

```json
{
  "metadata_version": "2.0.0",
  "session_id": "pilot_p55_walk_Participant_01_1792350000",
  "event_id": "evt_walk_Participant_01_1792350000",
  "timestamp_utc": "2026-10-20T14:30:00Z",
  "participant_id": "Participant_01",
  "activity_label": "walk",
  "ground_truth_confirmed": true,
  "room": {
    "room_name": "Laboratory_Room1",
    "room_type": "Laboratory",
    "room_dimensions_xyz_meters": [4.5, 3.5, 2.8]
  },
  "geometry": {
    "tx_rx_distance_meters": 2.5,
    "tx_position": "Tx_Origin_Corner",
    "rx_position": "Rx_Node_Desk",
    "orientation": "LOS_Facing_TxRx",
    "nlos_obstruction": false
  },
  "hardware": {
    "board": "ESP32-S3 (Xtensa LX7)",
    "chip_revision": "v0.2",
    "mac_address": "d4:05:92:7b:2e:d0",
    "serial_port": "COM5",
    "baud_rate": 115200,
    "firmware_version": "Phase50_Recovery_16cb232"
  },
  "rf_configuration": {
    "access_point_ssid": "Tp link",
    "target_bssid": "98:BA:5F:EF:28:26",
    "channel": 7,
    "frequency_ghz": 2.442,
    "bandwidth_mode": "HT20",
    "raw_subcarrier_count": 64,
    "active_subcarrier_count": 52,
    "aligned_subcarrier_count": 56
  },
  "telemetry_metrics": {
    "wall_clock_duration_seconds": 15.02,
    "timestamp_span_seconds": 15.018,
    "raw_records_detected": 42,
    "target_records_admitted": 28,
    "non_target_records_filtered": 14,
    "unfiltered_sequence_gaps": 0,
    "reconciled_transport_loss_rate": 0.000,
    "empirical_target_rate_hz": 1.86,
    "mean_rssi_dbm": -60.8,
    "mean_noise_dbm": -92.5,
    "mean_snr_db": 31.7
  },
  "quality_gate_results": {
    "overall_status": "QUARANTINED_RATE_DEFICIT",
    "gate_evaluations": {
      "firmware_protocol": "PASS",
      "bssid_match": "PASS",
      "channel_match": "PASS",
      "record_integrity": "PASS",
      "source_filtering": "PASS",
      "target_count": "PASS",
      "acquisition_rate_adequacy": "FAIL_BLOCKED",
      "timestamp_monotonicity": "PASS",
      "carrier_integrity": "PASS"
    }
  },
  "operator_notes": "Passive trial; clean reception; rate insufficient for inference."
}
```

### 10.2 Dataset Isolation and Partition Protection
- **Staging Directory:** All future pilot recordings must be stored in `data/pilot_recordings/` and **never** written directly to `data/real_csi_dataset/`.
- **Manifest Protection:** `data/real_csi_dataset/dataset_manifest.json` is protected by cryptographic checksum and will not be altered.
- **Quarantine Workflow:** Any session failing one or more quality gates is automatically moved to `data/pilot_recordings/quarantine/` along with an entry in `quarantine_manifest.json`.

### 10.3 Participant Safety and Ethical Protocol
- **Informed Consent & Privacy:** Written informed consent required. All participant data is strictly pseudonymized (`Participant_01`, `Participant_02`). No personally identifiable information (PII) is stored.
- **Strict Limitation to Ordinary Safe Activities:**
  - Proposed pilot activities are strictly limited to safe, ordinary activities: walking, standing, sitting, and arm movements, subject to consent and an approved protocol.
  - **Zero Fall Authorization:** Mention of safety mats and spotters in prior drafts must NOT be interpreted as authorization to perform fall experiments. Participants will **never** be instructed or permitted to intentionally fall during this or subsequent pilot sessions.
  - Any future fall-related collection is indefinitely deferred and requires a separately reviewed, approved, and dedicated safe methodology.
- **Zero Fabrication Policy:** No fake participant sessions or synthetic CSI samples will ever be created to artificially pad dataset counts.

---

## 11. Implementation, Testing, and Verification Scope

### 11.1 Test Suite Implementation (`backend/tests/test_phase55.py`)
To validate Phase 55 deliverables without accessing hardware or generating network traffic, a dedicated offline unit test suite was implemented in [`backend/tests/test_phase55.py`](file:///C:/Users/saifu/Desktop/4-1%20project/backend/tests/test_phase55.py), verifying:
1. `test_phase55_gate0_protected_file_invariance`: Bit-level cryptographic verification of protected files.
2. `test_phase55_acquisition_rate_gate_fails_closed_under_passive_conditions`: Validates fail-closed rate evaluation ($1.66\text{ Hz} \rightarrow \text{FAIL\_BLOCKED}$, $36.8\text{ Hz} \rightarrow \text{PASS}$).
3. `test_phase55_passive_pilot_source_filtering_fail_closed`: Validates target MAC admission and foreign MAC rejection without active network stimulation.
4. `test_phase55_global_sequence_reconciliation_logic`: Verifies that sequence jumps in the target stream are reconciled against filtered non-target packets without false loss attribution.
5. `test_phase55_temporal_dilation_and_window_semantics`: Verifies mathematical temporal window dilation ($21.1\times$ at 1.66 Hz).

### 11.2 Regression Test Execution Results
The complete regression test suite spanning Phases 42 through 55 was executed:
```bash
py -3.11 -m pytest backend/tests/test_phase42.py backend/tests/test_phase43.py \
    backend/tests/test_phase44.py backend/tests/test_phase45.py backend/tests/test_phase46.py \
    backend/tests/test_phase49.py backend/tests/test_phase50.py backend/tests/test_phase51.py \
    backend/tests/test_phase52.py backend/tests/test_phase55.py -v
```
**Results:** **58 passed, 0 failed, 0 skipped in 4.34s**.

---

## 12. Protected Asset Cryptographic Hash Verification

Bit-level MD5 cryptographic checksums were verified before and after all Phase 55 work:

| Protected Resource | File Path | Expected MD5 Hash | Measured MD5 Hash | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 13 Checkpoint** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (Pristine)** |
| **Phase 15 Checkpoint** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (Pristine)** |
| **Dataset Manifest** | `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (Pristine)** |

---

## 13. Open Risks and Evidence Required for Resolution

| Blocker / Open Risk | Technical Nature | Evidence Required to Resolve | Status |
| :--- | :--- | :--- | :--- |
| **1. Acquisition-Rate Deficit** | Passive beacon sniffing yields $1.66\text{--}3.8\text{ Hz}$, causing $11\times\text{--}21\times$ temporal dilation for 50-frame windows. | Empirical proof of $\ge 30\text{ Hz}$ acquisition rate under passive conditions, or separate safety-reviewed authorization for metered traffic generation. | **OPEN BLOCKER** |
| **2. Timestamp Origin Disconnect** | Timestamps originate on the PC host via `time.time()`, not hardware TSF on ESP32-S3. | Firmware modification adding microsecond hardware timestamps to Format B (requires separate authorized phase). | Documented Architecture Limitation |
| **3. Guard-Null Resampling** | `RealCSICollector` resamples 64 bins (including 12 nulls) to 56 subcarriers via `np.interp`. | Unit test validation of direct 52-active subcarrier mapping into model input layer. | Resolved in Adapter; Integration Deferred |
| **4. Medium Contention on 2.4 GHz** | 2.4 GHz Channel 7 exhibited an isolated $63\text{ ms}$ latency spike during active probe. | Statistical latency distribution audit over 2.4 GHz link during low-density hours. | Understood RF Characteristic |

---

## 14. Authorization Boundary and Scope Confirmation

- **No live serial operations:** COM5 was not opened.
- **No network traffic:** No ICMP, UDP, TCP, or broadcast packets were transmitted.
- **No firmware modifications:** ESP32-S3 flash was not touched.
- **No dataset modifications:** Zero records admitted to `data/real_csi_dataset/`.
- **No model training or evaluation:** Zero weights updated, zero inference runs.
- **No automatic progression:** Phase 56 will **not** be started automatically.

---

## 15. Final Disposition

**Phase 55 Status:** `COMPLETED (PLANNING & AUDIT DELIVERABLES ACHIEVED; ACQUISITION-RATE ADEQUACY REMAINS UNRESOLVED BLOCKER)`

Phase 55 has completed all assigned planning, static audit, protocol design, quality gate specification, and regression testing deliverables. Acquisition-rate adequacy remains an explicit, open, unresolved blocker that precludes declaring the hardware acquisition pipeline ready for research data collection. Any future hardware pilot, traffic experiment, or firmware modification requires separate explicit user authorization.
