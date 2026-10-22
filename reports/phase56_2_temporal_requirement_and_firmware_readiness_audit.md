# Phase 56.2 Report — Temporal Requirement and Firmware Readiness Audit

**Document Version:** 1.0.0  
**Phase:** 56.2  
**Date:** 2026-10-21  
**Status:** COMPLETED — STRICT OFFLINE SOURCE-CODE AND ARTIFACT AUDIT  
**Safety Protocol:** Strict Offline Audit Enforced. Zero hardware access on COM5, zero network packet transmission, zero UDP stimulation, zero firmware modification/flashing, zero model training or evaluation, zero protected asset modification, zero git commits.

---

## 1. Executive Summary & Verification Ledger

Phase 56.2 resolves the critical evidence gaps identified in Phase 56 and Phase 56.1 through an exhaustive offline audit of training pipelines, inference services, signal preprocessing routines, firmware implementations, and mathematical timing models.

### Key Audit Findings:
1. **Mathematical Invariance of Input Tensors to `source_rate_hz`:**
   - In `PhysicsCSIPreprocessor.compute_doppler_spectrogram`, the `source_rate_hz` parameter (whether 30.0 Hz, 35.58 Hz, or 1000.0 Hz) is used exclusively by `scipy.signal.stft` to calculate frequency and time vectors (`f`, `t`).
   - Both returned vectors (`f`, `t`) are **completely discarded** by the preprocessor. The resulting STFT magnitude-squared power matrix is interpolated onto normalized coordinates $[0, 1] \times [0, 1]$ using `RectBivariateSpline`.
   - Offline testing confirms that the output tensor is **100% numerically identical (`diff == 0.0`)** across any positive value of `source_rate_hz`. The nominal 30 Hz value in `PhysicsCSIPreprocessor` does NOT modify the numerical values fed to the neural network.

2. **Severe Preprocessing Discrepancy Between Training and Live Inference:**
   - **Training Pipeline (Phase 15):** Used `CalibratedPhysicsPreprocessor` with default STFT parameters (`stft_window=64`, `stft_noverlap=48`, `stft_nfft=128`) and applied an explicit **2.385x Doppler scale expansion** (`self.doppler_scale = 5.825 / 2.442`) to stretch 2.442 GHz Doppler bins to match 5.8 GHz pretraining.
   - **Live Inference Pipeline (`LivePipelineService`):** Instantiates standard `PhysicsCSIPreprocessor` with `stft_window=32`, `stft_noverlap=24`, `stft_nfft=64`, and applies **zero Doppler scale expansion**.
   - Offline empirical comparison on identical CSI inputs reveals a maximum tensor divergence of **3.2667**, demonstrating that live inference and adaptation training do not use equivalent temporal preprocessing.

3. **Deconstruction of the Doppler/Nyquist 30 Hz Argument:**
   - The theoretical Doppler shift for human motion ($v \in [0.5, 2.5]\text{ m/s}$) at 2.442 GHz ranges from $8.1\text{ Hz}$ to $40.7\text{ Hz}$.
   - Under the Nyquist criterion, resolving a $40.7\text{ Hz}$ Doppler frequency without aliasing requires $f_s \ge 81.5\text{ Hz}$, NOT 30 Hz. A 30 Hz sampling rate aliases all velocity components above $0.92\text{ m/s}$ into lower frequency bins.
   - Furthermore, Wi-Fi CSI sensing is bistatic, where Doppler shift depends on the bistatic angle $\beta$ ($f_D \le \frac{2v}{\lambda} \cos(\beta/2)$).
   - Most critically, the repository contains **zero empirical ablation studies** evaluating CSIFormer gesture classification accuracy as a function of physical frame rate.
   - **Formal Verdict:** The 30 Hz requirement is an **UNRESOLVED engineering heuristic**, not an empirically verified physical threshold.

4. **Sequence-Gap Conflation in Packet Loss Tracking:**
   - In `RealCSICollector`, `self.packets_lost` is incremented based on gaps in the firmware sequence counter: `gap = seq - (self.last_sequence + 1)`.
   - The firmware `packet_sequence` counter is a global software counter incremented on every physical callback for *all* received packets on Channel 7.
   - When `filter_by_mac=True`, ambient non-target packets are filtered out, but advance the firmware sequence number. When the next target packet arrives, the collector erroneously tallies this gap as target packet loss.
   - True packet loss cannot be established from a global callback counter when ambient filtering is active.

5. **Calibration Protocol Grounding & Provenance Ledger:**
   - Every threshold in the revised calibration specification is formally categorized as:
     - *Derived from a verified technical constraint* (e.g., UART 921600 baud throughput, 32-bit timer rollover).
     - *Derived from a documented project requirement* (e.g., 50-frame window, Channel 7, target BSSID).
     - *A provisional engineering threshold awaiting validation* (e.g., 28.0 Hz rate gate, 30 ms serial latency abort).
   - **Acquisition-rate adequacy remains strictly UNVERIFIED.**

---

## 2. Source Files and Exact Evidence Inspected

| Component | Source File Path | Key Line Ranges Inspected | Core Evidence Extracted |
| :--- | :--- | :--- | :--- |
| **Physics Preprocessor** | `backend/app/services/physics_csi_preprocessor.py` | L29–47, L190–234, L313–337 | STFT configuration, frequency vector discard, normalized `RectBivariateSpline` interpolation, `CalibratedPhysicsPreprocessor` 2.385x Doppler stretch. |
| **Legacy Preprocessor** | `backend/app/services/csi_preprocessor.py` | L58–76, L245–325 | `resample_time` linear interpolation from arbitrary length to 50 timesteps, discarding `source_rate_hz`. |
| **Live Inference** | `backend/app/services/live_pipeline_service.py` | L56–65, L188–234 | Instantiation with `stft_window=32, stft_noverlap=24, stft_nfft=64`, lack of Doppler scaling, sliding window validation. |
| **Collector Engine** | `backend/app/services/real_csi_collector.py` | L400–485, L486–582, L628–697 | Telemetry parsing, sequence gap tracking, lockstep buffer eviction, timing diagnostics, hardware timestamp extraction. |
| **Dataset Pipeline** | `backend/app/services/build_training_datasets.py` | L50–75, L104–120 | Widar 3.0 extraction (Intel 5300 .dat), NTU-Fi HAR download. |
| **Widar Dataset Loader**| `backend/app/datasets/widar_dataset.py` | L50–70, L234–274 | Binary parsing, adaptation to 50 timesteps, discard of original timestamps. |
| **Phase 13 Training** | `scratch/execute_phase13_2_dual_branch_and_benchmark.py` | L265–315 | Widar 3.0 raw & Doppler extraction using default preprocessor (`source_rate_hz=1000.0`). |
| **Phase 15 Adaptation**| `scratch/execute_phase15_adaptation_benchmark.py` | L51–76, L80–110 | `CalibratedPhysicsPreprocessor` with 2.385x scale, evaluation on real CSI windows. |
| **Baseline Evaluation**| `scratch/evaluate_phase15_baseline.py` | L45–90 | Non-overlapping 50-frame window slicing from `dataset_manifest.json`, complete omission of time/timestamps. |
| **Firmware Source** | `firmware/esp32s3_csi_collector/main/main.c` | L37–85, L121–204 | Unassociated promiscuous STA mode on Channel 7, missing `esp_wifi_connect()`, omitted `rx_ctrl.timestamp`, global software `packet_sequence`. |

---

## 3. Training-versus-Inference Temporal Comparison

### 3.1 Detailed Temporal Parameter Ledger

```
+----------------------------------------------------------------------------------------------------+
|                                 TEMPORAL PARAMETER COMPARISON                                       |
+-----------------------------+-------------------------------+--------------------------------------+
| Dimension                   | Training Pipeline (Phase 15)  | Live Inference Pipeline (LiveService) |
+-----------------------------+-------------------------------+--------------------------------------+
| 1. Frame Count per Window   | Exactly 50 frames             | Exactly 50 frames                    |
| 2. Window Time Duration     | ~1.41 s (35.4 Hz historical)  | Passive: 20.0 s (at 2.5 Hz)          |
|                             | Range: 1.25 s – 1.53 s        | Target: 1.67 s (at 30.0 Hz)          |
| 3. Source Timestamps Used?  | NO. Discarded during slicing  | NO. Sliced by buffer frame count     |
| 4. Temporal Resampling      | None (integer 50-frame slice) | None (integer 50-frame ring buffer)  |
| 5. STFT Window (nperseg)    | 50 (effective min(64, 50))    | 32                                   |
| 6. STFT Overlap (noverlap)  | 48 (effective min(48, 49))    | 24                                   |
| 7. STFT FFT Bins (nfft)     | 128 (max(128, 50))            | 64                                   |
| 8. Doppler Scale Factor     | 2.385x (5.825 GHz expansion)  | 1.000x (No expansion applied)        |
| 9. source_rate_hz Parameter | 35.58 Hz (unused in tensor)   | 30.0 Hz (unused in tensor)           |
| 10. Max Tensor Divergence   | Baseline                      | diff = 3.2667 (HIGH DIVERGENCE)      |
+-----------------------------+-------------------------------+--------------------------------------+
```

### 3.2 Evaluation of the Seven Required Questions:

1. **Frame count per model window:**
   - Both training and live inference operate on windows of **exactly 50 frames** (`seq_len = 50`).
2. **Actual or assumed time duration per window during training:**
   - In Phase 13 pretraining on Widar 3.0, the entire duration of each gesture trial (typically $1.5\text{--}3.0\text{ seconds}$ at 1000 Hz) was linearly resampled down to 50 timesteps.
   - In Phase 15 domain adaptation on real CSI, non-overlapping 50-frame windows were sliced from sessions whose mean acquisition rate was $35.40\text{ Hz}$ ($32.67\text{--}40.00\text{ Hz}$). The physical duration spanned by these 50 frames was **$1.412\text{ seconds}$ on average** ($1.25\text{--}1.53\text{ seconds}$).
3. **Actual or assumed time duration per window during live inference:**
   - Under current passive conditions ($1.66\text{--}3.8\text{ Hz}$), a 50-frame window spans **$13.1\text{ to }30.1\text{ seconds}$** (mean $\approx 20.0\text{ seconds}$).
   - Under the nominal target rate ($30.0\text{ Hz}$), a 50-frame window spans **$1.667\text{ seconds}$**.
4. **Whether source timestamps are used, resampled, interpolated, or discarded:**
   - Source timestamps are **completely discarded**. Slicing in `evaluate_phase15_baseline.py` and `load_real_dataset_windows()` uses integer array indices: `win = mat[start_idx:start_idx + 50, :56]`.
   - In `PhysicsCSIPreprocessor.compute_doppler_spectrogram`, the `t` and `f` vectors output by `signal.stft` are discarded. The spectrogram power array is interpolated onto normalized $[0, 1] \times [0, 1]$ coordinates.
5. **Whether the 30 Hz value changes only the frequency-axis calculation or also affects the actual input tensor:**
   - **It does not affect the input tensor at all.** As proven in `test_phase56_2_preprocessor_invariance_to_source_rate()`, setting `source_rate_hz` to 30.0, 35.58, or 1000.0 produces **0.0 difference** in the output tensor. It changes only the returned frequency vector `f`, which the preprocessor discards.
6. **Whether training and inference use equivalent temporal preprocessing:**
   - **NO.** Live inference and training preprocessing diverge significantly:
     - `LivePipelineService` configures `stft_window=32`, `stft_noverlap=24`, `stft_nfft=64`.
     - Phase 15 adaptation used `CalibratedPhysicsPreprocessor` with `stft_window=64`, `stft_noverlap=48`, `stft_nfft=128`, and a 2.385x Doppler scale expansion (`self.doppler_scale = 5.825 / 2.442`).
     - This discrepancy produces a substantial numerical mismatch (`np.max(np.abs(d_live - d_train)) = 3.2667`).
7. **Which claims can be verified from code and metadata, and which remain unknown:**
   - *Verified:* Window length is 50 frames; `source_rate_hz` has zero effect on tensor values; training and live STFT parameters diverge; historical sessions averaged 35.4 Hz.
   - *Unknown:* The minimum physical CSI frame rate required to maintain acceptable gesture classification accuracy has **never been evaluated via ablation testing** in this repository.

---

## 4. Audit of the Doppler/Nyquist Argument

### 4.1 Theoretical Doppler Derivation

For Wi-Fi transmission at Carrier Frequency $f_c = 2.442\text{ GHz}$ (Channel 7):
$$\lambda = \frac{c}{f_c} = \frac{299,792,458\text{ m/s}}{2,442,000,000\text{ Hz}} \approx 0.12276\text{ m} \approx 12.28\text{ cm}$$

#### Monostatic (Backscatter) Model:
In a monostatic radar configuration where transmitter and receiver are co-located:
$$f_D = \frac{2 v}{\lambda} \cos(\theta)$$
For direct radial motion ($\cos(\theta) = 1$):
- At $v = 0.5\text{ m/s}$ (slow limb motion): $f_D = \frac{2 \times 0.5}{0.12276} \approx 8.15\text{ Hz}$
- At $v = 1.0\text{ m/s}$ (standard gesture speed): $f_D = \frac{2 \times 1.0}{0.12276} \approx 16.29\text{ Hz}$
- At $v = 2.5\text{ m/s}$ (rapid fall or fast sweep): $f_D = \frac{2 \times 2.5}{0.12276} \approx 40.73\text{ Hz}$

#### Bistatic Geometry Correction:
In real-world CSI sensing, the AP (transmitter) and ESP32-S3 (receiver) are separated by distance $L$, forming a bistatic triangle with the human subject. The bistatic Doppler shift is:
$$f_{D, \text{bistatic}} = \frac{2 v}{\lambda} \cos(\delta) \cos\left(\frac{\beta}{2}\right)$$
where $\beta$ is the bistatic angle ($\angle \text{TX-Target-RX}$) and $\delta$ is the angle between the velocity vector and the bistatic bisector. Because $\cos(\beta/2) \le 1$ and $\cos(\delta) \le 1$:
$$f_{D, \text{bistatic}} \le f_{D, \text{monostatic}}$$
For typical indoor geometries ($\beta \approx 60^\circ\text{ to }90^\circ$), $\cos(\beta/2) \in [0.707, 0.866]$, reducing observed Doppler shifts by 15% to 30%.

### 4.2 Critique of the 30 Hz Requirement Claim

1. **Nyquist Criterion Inconsistency:**
   - Under the Nyquist-Shannon sampling theorem, the minimum sampling rate required to avoid frequency aliasing for a bandwidth with maximum frequency $f_{\max}$ is:
     $$f_s \ge 2 f_{\max}$$
   - If the upper bound of human motion is $v = 2.5\text{ m/s}$ ($f_D \approx 40.7\text{ Hz}$), the true Nyquist rate is:
     $$f_s \ge 2 \times 40.73\text{ Hz} \approx \mathbf{81.5\text{ Hz}}$$
   - Claiming that a $40.7\text{ Hz}$ upper bound proves a $30\text{ Hz}$ requirement is mathematically invalid. At $f_s = 30.0\text{ Hz}$, the Nyquist limit is $f_{\text{Nyquist}} = 15.0\text{ Hz}$. Any motion velocity $v > 0.92\text{ m/s}$ will undergo frequency aliasing.
2. **Frequency Discard in Neural Input:**
   - The deep neural network (`CSIDualBranchFusionNet`) does not receive calibrated physical velocity or frequency units. It receives a $50 \times 56$ matrix of normalized relative spectrogram powers.
3. **Absence of Empirical Evidence:**
   - The repository contains no empirical experiments testing model degradation at 10 Hz, 15 Hz, 20 Hz, or 25 Hz.
4. **Formal Status:** The 30 Hz requirement is **UNRESOLVED**. It represents a reasonable engineering heuristic to capture typical gesture velocities ($v \le 0.9\text{ m/s}$) without severe aliasing, but it cannot be claimed as a proven physical necessity.

---

## 5. Audit of Firmware Association Recommendations

### 5.1 Existing Implementation (`firmware/esp32s3_csi_collector/main/main.c`)

```c
// Current Wi-Fi Initialization in app_main():
nvs_flash_init();
esp_netif_init();
esp_event_loop_create_default();
esp_netif_create_default_wifi_sta(); // Netif created, but unassociated

wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
cfg.csi_enable = 1;
esp_wifi_init(&cfg);
esp_wifi_set_storage(WIFI_STORAGE_RAM);
esp_wifi_set_mode(WIFI_MODE_STA);
esp_wifi_start();

esp_wifi_set_channel(7, WIFI_SECOND_CHAN_NONE);
esp_wifi_set_promiscuous(true); // Promiscuous capture active
init_csi();                     // Registers wifi_csi_cb
```

### 5.2 Audit of Proposed Changes

| Proposed Change | Current State in Source | Required API Ordering & Constraints | Status in ESP-IDF v6.1.0 | Potential Adverse Effects |
| :--- | :--- | :--- | :--- | :--- |
| **1. Station Association (`esp_wifi_connect`)** | Omitted. Mode is `WIFI_MODE_STA` but credentials are not set. | Must configure `wifi_sta_config_t` with SSID/password and call `esp_wifi_set_config()` before `esp_wifi_connect()`. | Confirmed compatible with promiscuous capture. | If credentials fail or AP is unreachable, Wi-Fi driver may trigger repeated scans, causing channel hops. |
| **2. Channel Hard-Pinning & Fast Scan** | Fixed channel 7 set via `esp_wifi_set_channel(7)`. | Must set `bssid_set = 1`, `bssid = {target_bssid}`, `channel = 7`, and `scan_method = WIFI_FAST_SCAN` in `wifi_sta_config_t`. | Confirmed in ESP-IDF documentation. | If target AP changes channel dynamically (Auto-Channel), connection will fail permanently. |
| **3. Disable Modem Sleep (`WIFI_PS_NONE`)** | Omitted. Defaults to `WIFI_PS_MIN_MODEM`. | Must be called after `esp_wifi_start()`: `esp_wifi_set_ps(WIFI_PS_NONE)`. | Confirmed critical for CSI timing. | Increases ESP32-S3 power consumption by ~80 mA; chip runs warmer. |
| **4. Event Loop Handlers** | Omitted. System event loop created, but no handlers registered. | Register handlers for `WIFI_EVENT_STA_CONNECTED`, `WIFI_EVENT_STA_DISCONNECTED`, and `IP_EVENT_STA_GOT_IP`. | Confirmed standard ESP-IDF architecture. | None. Necessary for connection state visibility. |
| **5. Format B v2 Telemetry** | Emits Format B v1: `"CSI_DATA,%s,%d,%d,%lu,%d,"`. | Update `wifi_csi_cb()` to format `"CSI_DATA_V2,%s,%d,%d,%lu,%lu,%u,%d,"` including `timestamp` and sequence. | Confirmed supported by native headers. | Slightly increases UART character volume (+15 bytes/packet). |

### 5.3 Safe Offline Verification Procedure (Without Hardware Access)
1. **Compilation Check:** Compile firmware offline using `idf.py build` in a clean environment to verify header compatibility, struct field names, and linking without flashing.
2. **Static ELF Analysis:** Inspect compiled symbols with `riscv32-esp-elf-nm` or `objdump` to verify that `esp_wifi_connect`, `esp_wifi_set_ps`, and event handlers are linked.
3. **Hardware Execution Gate:** Zero firmware flashing or hardware testing may take place until explicit user authorization is provided.

---

## 6. Audit of Timestamp Semantics and Rate Metrics

### 6.1 Telemetry Timestamp Classification

```
+----------------------------------------------------------------------------------------------------+
|                                 TIMESTAMP & TIMING DOMAINS                                         |
+----------------------+---------------------------+-----------------------+-------------------------+
| Field Name           | Clock Source / Domain     | Resolution & Range    | Usage in Pipeline       |
+----------------------+---------------------------+-----------------------+-------------------------+
| `hw_timestamp_us`    | ESP32-S3 Baseband Counter | 1 microsecond (us)    | Hardware inter-arrival  |
|                      | (Receiver Hardware Clock) | Wraps: 71.58 minutes  | interval estimation     |
+----------------------+---------------------------+-----------------------+-------------------------+
| `host_monotonic_time`| Host Python Monotonic     | Nanosecond / float    | Host serial arrival,    |
|                      | (`time.perf_counter()`)   | Never wraps, strictly | empirical window rate,  |
|                      |                           | increasing            | latency tracking        |
+----------------------+---------------------------+-----------------------+-------------------------+
| `timestamp`          | Host Wall-Clock           | Second / float        | Session logging,        |
|                      | (`time.time()`)           | Subject to NTP jumps  | diagnostic timestamps   |
+----------------------+---------------------------+-----------------------+-------------------------+
```

### 6.2 Sequence Numbers and Rate Metrics

1. **Firmware Sequence vs 802.11 MAC Sequence:**
   - In Format B, `seq` is `packet_sequence++` in `wifi_csi_cb()`. This is an internal FreeRTOS firmware counter.
   - It counts *every callback invocation* across all frames on Channel 7.
   - It is **not** an 802.11 MAC sequence number.
2. **Conflation of Packet Loss and Non-Target Filtering:**
   - In `RealCSICollector._process_parsed_frame`:
     ```python
     if self.filter_by_mac and source_mac != self.target_mac:
         self.filtered_non_target_packets += 1
         return
     # ...
     gap = seq - (self.last_sequence + 1)
     if gap > 0:
         self.packets_lost += gap
     ```
   - When non-target frames arrive, they increment `packet_sequence` in firmware, but are dropped at the MAC filter on the host. When the next target frame arrives, `seq` has a gap, causing the collector to increment `packets_lost`.
   - **Correction:** `packets_lost` under MAC filtering reflects total ambient frames plus any true lost frames, making it impossible to calculate target-packet loss without probe-level sequence numbers.

---

## 7. Evidence-Based Calibration Specification

### 7.1 Independent Metric Definitions

$$\begin{aligned}
R_{\text{stim}} &\triangleq \text{UDP datagrams transmitted per second by stimulator} \\
N_{\text{stim}} &\triangleq \text{Total UDP datagrams transmitted (confirmed by socket sendto)} \\
R_{\text{raw}} &\triangleq \text{Total physical CSI callback records emitted by ESP32 per second} \\
R_{\text{target}} &\triangleq \text{CSI records matching target BSSID } (98:\text{BA}:5\text{F}:\text{EF}:28:26) \text{ per second} \\
R_{\text{parsed}} &\triangleq \text{Successfully parsed and admitted records into collector window per second} \\
\Delta t_{\text{hw}} &\triangleq \text{Hardware inter-arrival interval: } (t_{\text{hw}, i} - t_{\text{hw}, i-1}) \pmod{2^{32}}\ (\mu\text{s}) \\
\Delta t_{\text{host}} &\triangleq \text{Host serial arrival interval: } (t_{\text{mono}, i} - t_{\text{mono}, i-1})\ (\text{s})
\end{aligned}$$

### 7.2 Threshold Provenance Ledger

| Metric / Parameter | Proposed Threshold | Provenance Category | Rationale & Basis |
| :--- | :--- | :--- | :--- |
| **Primary Channel** | Channel 7 | **Derived from Documented Project Requirement** | Wi-Fi router and target AP are hard-configured to 2.4 GHz Channel 7. |
| **Target MAC** | `98:BA:5F:EF:28:26` | **Derived from Documented Project Requirement** | Hardware BSSID of the TP-Link Access Point. |
| **Window Frame Count** | $N = 50$ frames | **Derived from Documented Project Requirement** | Architectural input dimension of CSIFormer spatial and Doppler encoders. |
| **Hardware Timer Wraparound** | $2^{32}\ \mu\text{s} \approx 4294.97\text{ s}$ | **Derived from Verified Technical Constraint** | 32-bit unsigned counter in ESP-IDF `wifi_pkt_rx_ctrl_t.timestamp`. |
| **Max Serial Baud Throughput** | $\le 120\text{ records/s}$ | **Derived from Verified Technical Constraint** | At 921,600 baud, raw ASCII telemetry lines (~750 bytes) saturate UART at $\approx 122\text{ Hz}$. |
| **Max Host Serial Latency** | $\le 100\text{ ms}$ (max), $\le 30\text{ ms}$ (mean) | **Provisional Engineering Threshold** | Ensures host serial queue does not introduce temporal lag into live sliding windows. |
| **Operational Rate Gate** | $\ge 28.0\text{ Hz}$ target CSI | **Provisional Engineering Threshold** | Operational target to approximate nominal 30 Hz preprocessor frequency. |
| **Stepped Rates** | [0, 5, 15, 30, 35] pkts/s | **Provisional Engineering Threshold** | Stepped sequence designed to observe routing, linearity, and historical reproducibility safely. |

### 7.3 Mandatory Stop Conditions

Any calibration run MUST be terminated immediately if:
1. Host serial latency exceeds $100\text{ ms}$ (instantaneous) or $30\text{ ms}$ (rolling 1-second mean).
2. Reported primary channel in `rx_ctrl` is not Channel 7.
3. Socket transmission buffer experiences packet drop $> 2\%$.
4. Collector FIFO buffer experiences frame eviction before window consumption.
5. In Stages 1–4, target CSI rate fails to increase with stimulation ($R_{\text{target}} \approx R_{\text{passive}}$).

---

## 8. Validation and Offline Testing

The offline test suite `backend/tests/test_phase56_2.py` was authored and executed using Python 3.11.9. In addition, the full 35-test regression suite was executed across all phase test files:

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\saifu\Desktop\4-1 project
collected 35 items

backend/tests/test_phase52.py::test_phase52_gate0_protected_file_invariance PASSED       [  2%]
backend/tests/test_phase52.py::test_phase52_target_source_filtering_and_fail_closed PASSED [  5%]
backend/tests/test_phase52.py::test_phase52_ht20_physical_carrier_mask PASSED           [  8%]
backend/tests/test_phase52.py::test_phase52_stream_diagnostics_contract PASSED            [ 11%]
backend/tests/test_phase52.py::test_phase52_model_preprocessing_invariance PASSED         [ 14%]
backend/tests/test_phase55.py::test_phase55_gate0_protected_file_invariance PASSED       [ 17%]
backend/tests/test_phase55.py::test_phase55_acquisition_rate_gate_fails_closed_under_passive_conditions PASSED [ 20%]
backend/tests/test_phase55.py::test_phase55_passive_pilot_source_filtering_fail_closed PASSED [ 22%]
backend/tests/test_phase55.py::test_phase55_global_sequence_reconciliation_logic PASSED   [ 25%]
backend/tests/test_phase55.py::test_phase55_temporal_dilation_and_window_semantics PASSED [ 28%]
backend/tests/test_phase55_1.py::test_phase55_1_protected_hashes PASSED                 [ 31%]
backend/tests/test_phase55_1.py::test_phase55_1_record_count_vs_rate_separation PASSED    [ 34%]
backend/tests/test_phase55_1.py::test_phase55_1_window_span_definitions_consistency PASSED [ 37%]
backend/tests/test_phase55_1.py::test_phase55_1_spatial_interpolation_invariance PASSED   [ 40%]
backend/tests/test_phase55_1.py::test_phase55_1_doppler_stft_frequency_scaling PASSED     [ 42%]
backend/tests/test_phase55_1.py::test_phase55_1_carrier_validity_multipath_notch_tolerance PASSED [ 45%]
backend/tests/test_phase55_1.py::test_phase55_1_session_disposition_states PASSED        [ 48%]
backend/tests/test_phase56.py::test_phase56_gate0_protected_file_invariance PASSED       [ 51%]
backend/tests/test_phase56.py::test_phase56_historical_acquisition_evidence_consistency PASSED [ 54%]
backend/tests/test_phase56.py::test_phase56_espidf_timestamp_semantics_contract PASSED   [ 57%]
backend/tests/test_phase56.py::test_phase56_format_b_v2_parser_and_backward_compatibility PASSED [ 60%]
backend/tests/test_phase56.py::test_phase56_host_monotonic_timing_and_sliding_window_metadata PASSED [ 62%]
backend/tests/test_phase56.py::test_phase56_rate_gate_vs_record_count_gate_separation PASSED [ 65%]
backend/tests/test_phase56.py::test_phase56_calibration_procedure_safety_abort_simulation PASSED [ 68%]
backend/tests/test_phase56_1.py::test_phase56_1_gate0_protected_file_invariance PASSED     [ 71%]
backend/tests/test_phase56_1.py::test_phase56_1_collector_buffer_lockstep_alignment PASSED [ 74%]
backend/tests/test_phase56_1.py::test_phase56_1_telemetry_parser_mutual_exclusivity PASSED [ 77%]
backend/tests/test_phase56_1.py::test_phase56_1_historical_provenance_audit PASSED         [ 80%]
backend/tests/test_phase56_1.py::test_phase56_1_diagnostic_timing_robustness PASSED       [ 82%]
backend/tests/test_phase56_1.py::test_phase56_1_decoupled_calibration_quantities PASSED   [ 85%]
backend/tests/test_phase56_2.py::test_phase56_2_gate0_protected_file_invariance PASSED     [ 88%]
backend/tests/test_phase56_2.py::test_phase56_2_preprocessor_invariance_to_source_rate PASSED [ 91%]
backend/tests/test_phase56_2.py::test_phase56_2_training_vs_live_preprocessor_divergence PASSED [ 94%]
backend/tests/test_phase56_2.py::test_phase56_2_sequence_gap_conflation_audit PASSED       [ 97%]
backend/tests/test_phase56_2.py::test_phase56_2_calibration_metric_schema_and_threshold_provenance PASSED [100%]

============================= 35 passed in 22.07s =============================
```

---

## 9. Protected Asset Invariance Ledger

All protected MD5 hashes were verified before and after Phase 56.2 execution:

| Protected Asset | Reference MD5 Hash | Audited MD5 Hash | Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **100% INVARIANT** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **100% INVARIANT** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **100% INVARIANT** |

---

## 10. Unresolved Blockers and Recommended Next Action

### 10.1 Unresolved Blockers
1. **Model Minimum Frame Rate Requirement is UNRESOLVED:** There is no empirical ablation evidence establishing the lower bound of sampling rate needed for CSIFormer accuracy.
2. **Preprocessing Parity Defect:** `LivePipelineService` does not use the `CalibratedPhysicsPreprocessor` settings (STFT window/nfft and 2.385x Doppler scale expansion) used to train `csiformer_phase15_adapted.pth`.
3. **Firmware Station Association & Telemetry Unimplemented:** The firmware running on the hardware has not been updated with Station association, `WIFI_PS_NONE`, or Format B v2 telemetry.
4. **Packet Loss Conflation:** Packet loss tracking in the collector conflates ambient packet filtering with physical packet loss.
5. **Acquisition-Rate Adequacy Has NOT Been Achieved:** Current passive target capture remains at $1.66\text{--}3.8\text{ Hz}$.

### 10.2 Recommended Next Action
1. **Resolve Live vs Training Preprocessing Parity:** Align `LivePipelineService.preprocessor` with `CalibratedPhysicsPreprocessor` so inference representations match model weights.
2. **Authorize Phase 57 (Firmware Enhancement & Offline Build Only):** Add station association, fast scan, disabled modem sleep, and Format B v2 telemetry to `main.c`, and compile with `idf.py build` offline without touching hardware.
3. **Subsequent Authorized Calibration:** After firmware compilation is verified, request explicit authorization for a live stepped calibration run with probe-level sequence tracking.
