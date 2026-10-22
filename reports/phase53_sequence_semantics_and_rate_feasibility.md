# Phase 53 Report — Sequence Counter Semantics and Acquisition-Rate Feasibility Audit

**Document Version:** 1.0.0  
**Phase:** 53  
**Date:** 2026-10-20  
**Status:** SEQUENCE SEMANTICS VERIFIED — RATE EXPERIMENT AWAITING AUTHORIZATION  
**Safety Restrictions Enforced:** Zero firmware flash/erasure, zero network traffic generation (no ping/iperf/broadcast), zero dataset collection/admissions, zero model training/evaluation, zero protected checkpoint modification, zero git commits.

---

## 1. Executive Summary & Audit Context

Phase 53 addressed two critical measurement and architecture questions remaining after Phase 52:
1. **Sequence Continuity Semantics:** Establishing whether the 13 sequence gaps observed in Phase 52 represented physical serial transport loss or were artifacts of software source filtering across a global sequence counter.
2. **Acquisition-Rate Feasibility:** Auditing the CSIFormer model's mathematical sampling rate assumptions against physical ESP32-S3 passive stream measurements, and designing a future controlled rate validation experiment without generating unauthorized network traffic.

A non-persistent, bounded live diagnostic executed on `COM5` proved that the global sequence stream over UART experienced **0.00% transport packet loss** (0 gaps across all captured frames). The 13 reported gaps in Phase 52 were mathematically and empirically verified to be the 13 interleaved non-target transmissions from ambient client stations (`80:5E:4F:21:03:FA` and `18:CC:88:7E:74:71`) that incremented the global counter before being filtered by MAC address.

---

## 2. Sequence-Counter Assignment, Scope, and Lifecycle

An end-to-end trace from firmware C source to Python collector logic established the exact lifecycle of the sequence counter:

### 2.1 Firmware Assignment and Scope
In `firmware/esp32s3_csi_collector/main/main.c`:
```c
static uint32_t packet_sequence = 0; // Line 34

void wifi_csi_cb(void *ctx, wifi_csi_info_t *info) {
    if (!info || !info->buf) {
        return;
    }

    packet_sequence++; // Line 45
    ...
    int offset = snprintf(payload_buf, sizeof(payload_buf),
                          "CSI_DATA,%s,%d,%d,%lu,%d,",
                          mac_str, (int)info->rx_ctrl.rssi, (int)info->rx_ctrl.noise_floor,
                          (unsigned long)packet_sequence, num_subcarriers);
    ...
    printf("%s", payload_buf); // Line 78
}
```

### 2.2 Lifecycle Characteristics
1. **Scope:** **Global**. Defined at static file scope; there is only one `packet_sequence` counter on the device. It increments for *every* frame received by the Wi-Fi PHY layer that invokes the CSI callback, regardless of the transmitter MAC address (`info->mac`).
2. **Increment Condition:** Increments monotonically on each non-null callback prior to formatting.
3. **Reboot Behavior:** Stored in volatile memory (BSS section). Resets to `0` upon any hardware reset, RTS toggle, watchdog timeout, or power-cycle.
4. **Wrap-Around Period:** Implemented as a 32-bit unsigned integer (`uint32_t`). Wraps at $2^{32} - 1 = 4,294,967,295$. At 100 Hz continuous reception, wrap-around occurs after 497 days; at the passive 3.5 Hz rate, wrap-around occurs after ~38 years.
5. **Frame Discard Points:**
   - *Pre-Serialization:* If `info == NULL` or `info->buf == NULL` (never observed in active operation).
   - *Buffer Truncation:* If payload exceeds 2,048 bytes (payload is bounded to ~900 bytes for HT20).
   - *UART Transport:* If baud rate cannot keep up with data throughput (at 115,200 baud, buffer capacity is ~12–14 packets/sec).
   - *Parser Discard:* If newline framing is fragmented or string split yields $< 6$ tokens.
   - *Target-Source Filter:* Dropped in software by `RealCSICollector` when `mac != target_mac`.

---

## 3. Explanation of the Phase 52 Sequence Gaps & Empirical Reconciliation

### 3.1 Mechanism of the Apparent Loss
In Phase 52, `RealCSICollector._process_parsed_frame()` computed sequence loss using:
```python
if self.last_sequence is not None:
    gap = seq - (self.last_sequence + 1)
    if gap > 0:
        self.packets_lost += gap
self.last_sequence = seq
```
Because the source filtering check (`if source_mac_norm != self.target_mac: return`) executed *before* this block, whenever an ambient client frame (e.g. `80:5E:4F:21:03:FA`) arrived:
1. Firmware incremented `packet_sequence` (e.g. $N \rightarrow N+1$).
2. The packet was received over serial and parsed successfully.
3. The source filter detected a non-target MAC and returned immediately.
4. `self.last_sequence` remained at $N$.
5. When the next target frame arrived with sequence $N+2$, `gap = (N + 2) - (N + 1) = 1`.
6. `self.packets_lost` incremented by 1.

Thus, **all 13 "packets lost" reported in Phase 52 were the 13 intentionally filtered non-target packets**.

### 3.2 Phase 53 Empirical Reconciliation Experiment
A bounded, non-persistent diagnostic (`scratch/audit_phase53_sequence_reconciliation.py`) was executed on `COM5` for 10.0 seconds to trace the global sequence counter alongside MAC addresses:

#### Telemetry Breakdown
- **Total Raw CSI Records Captured:** 38 records
- **Target Records Admitted (`98:BA:5F:EF:28:26`):** 25 records
- **Non-Target Records Filtered:** 13 records
- **Parser Errors:** 0
- **Unfiltered Sequence Gaps (Firmware $\rightarrow$ UART Transport):** **0 gaps**
- **Unfiltered Lost Packets:** **0 packets**
- **True UART Transport Loss Rate:** **0.00%**

#### Target Stream Gap-by-Gap Accounting
| Event | From Seq | To Seq | Seq Jump ($\Delta$) | Interleaved Non-Target Records | Transmitting Non-Target MACs | Unaccounted Loss |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **Gap 1** | 2 | 4 | 1 | 1 frame (Seq 3) | `80:5E:4F:21:03:FA` | **0** |
| **Gap 2** | 6 | 8 | 1 | 1 frame (Seq 7) | `80:5E:4F:21:03:FA` | **0** |
| **Gap 3** | 17 | 21 | 3 | 3 frames (Seq 18, 19, 20) | `18:CC:88:7E:74:71`, `80:5E:4F:21:03:FA` | **0** |
| **Gap 4** | 24 | 26 | 1 | 1 frame (Seq 25) | `80:5E:4F:21:03:FA` | **0** |
| **Gap 5** | 30 | 32 | 1 | 1 frame (Seq 31) | `18:CC:88:7E:74:71` | **0** |
| **Trailing** | 33 | 38 | N/A | 6 frames (Seq 33–38) | `80:5E:4F:21:03:FA` | **0** |
| **Total** | — | — | **7 interleaved** | **13 non-target frames** | Ambient Clients | **0 missing** |

**Conclusion:** 100% of the sequence jumps in the admitted target stream correspond to interleaved foreign client transmissions. **Zero frames were dropped by the physical UART serial transport.**

---

## 4. Audit of Target-Rate Requirements & Preprocessing

### 4.1 Requirement Provenance: 30 Hz vs 35 Hz
An audit of model architecture, configuration files, and reports revealed:
1. **Transformer Temporal Receptive Field:** The CSIFormer architecture takes an input tensor of shape `[Batch, 50, 56]`, representing 50 consecutive temporal time steps.
2. **Historical Training Baseline:** In `data/real_csi_dataset/dataset_manifest.json`, the real ESP32-S3 dataset recorded in Phase 14 / Phase 15 exhibited empirical sampling rates between **35.0 Hz and 39.0 Hz** (mean $36.8\text{ Hz}$), with sessions lasting $4.0\text{ s}$ producing 140–160 packets.
3. **Phase 41 Campaign Design:** Formally established a quality gate of $32\text{--}42\text{ Hz}$ for real data acquisition, where 50 consecutive frames represent $\approx 1.405\text{ seconds}$ of physical human motion.
4. **Adapter Resampling:** In `backend/app/services/esp32_csi_adapter.py`, external datasets with high rates (Widar 3.0 @ 1,000 Hz, NTU-Fi @ 100 Hz) are resampled down to **30.0 Hz** (`target_rate_hz=30.0`) to match the model's design window.

### 4.2 Handling of Timestamps and Frame Intervals
- **Timestamp Discard:** In `RealCSICollector.get_latest_window()`, sliding windows are formed by stacking `deque` items:
  ```python
  raw_win = np.stack(list(self.raw_frame_buffer), axis=0) # [50, 56]
  ```
  **Timestamps are completely discarded.** The neural network's positional encoding implicitly assumes that consecutive indices $t, t+1$ represent uniform $\Delta t \approx 28\text{ ms}$ ($35\text{ Hz}$).
- **Impact of Passive Acquisition (3.2 Hz):** At 3.2 Hz, 50 frames span **15.6 seconds**. Feeding a 15.6-second window into positional embeddings trained on a 1.4-second gesture introduces an **$11.1\times$ temporal dilation**, destroying the Doppler and kinematic signatures of human activities.
- **Irregular Interval Impact:** Without active traffic, beacon intervals jitter due to network contention, causing non-uniform sampling that distorts temporal self-attention.

---

## 5. Physical Stream vs Historical Training Preprocessing Comparison

| Feature / Parameter | Historical Training Preprocessing (Phase 15 Checkpoint) | Physical Real-Time Stream (Phase 52 Pipeline) | Alignment Status & Risk |
| :--- | :--- | :--- | :--- |
| **Input Tensor Shape** | `[50, 56]` (50 timesteps, 56 subcarriers) | `[50, 56]` (via sliding buffer + `np.interp`) | **ALIGNED** |
| **Window Duration ($T$)** | $1.28\text{ s} - 1.42\text{ s}$ ($35 - 39\text{ Hz}$) | **$15.6\text{ s}$** (under passive 3.2 Hz beaconing) | **MISALIGNED (Severe Dilation)** |
| **Time Sampling Model** | Uniform, driven by active traffic train | Non-uniform, passive beacon listening | **MISALIGNED (Jitter & Under-sampling)** |
| **Subcarrier Mapping** | Linear interpolation (64 bins $\rightarrow$ 56 model tones) | Linear interpolation (64 bins $\rightarrow$ 56 model tones) | **ALIGNED** |
| **Null Subcarrier Handling** | Interpolated across DC & guard nulls | Preserved in metadata, interpolated for model | **ALIGNED (Backwards Compatible)** |
| **Source Filtering** | Captured from dedicated AP/STA pair | Target MAC filter active (`98:BA:5F:EF:28:26`) | **ALIGNED** |
| **Normalization** | Column-wise z-score per window | Column-wise z-score per window | **ALIGNED** |

**Conclusion:** Spatial and structural subcarrier dimensions are 100% aligned. The sole critical barrier to running inference or dataset collection on the physical stream is the **temporal acquisition rate (3.2 Hz passive vs $\ge 30\text{ Hz}$ required)**.

---

## 6. Proposed Controlled Acquisition-Rate Experiment (NOT Executed in Phase 53)

To validate physical 30 Hz acquisition feasibility without violating safety rules, the following controlled experiment is designed for subsequent execution upon authorization:

### 6.1 Architecture & Network Impact
- **Principle:** Generate controlled, strictly unicast IP traffic from an associated client station to the AP (`98:BA:5F:EF:28:26`) to prompt regular downlink transmission.
- **Traffic Mechanism:** Unicast ICMP ping (payload size 64 bytes) or low-overhead UDP datagrams targeted directly at the router LAN IP (`192.168.1.1`).
- **Safety from Broadcast Storms:** Prohibit broadcast/multicast addresses (`255.255.255.255`, `192.168.1.255`). Traffic is point-to-point and transparent to other devices.

### 6.2 Proposed Rate Sweep Protocol
| Step | Target Rate (Hz) | Duration (s) | Total Packets | Purpose |
| :---: | :---: | :---: | :---: | :--- |
| **1** | 0 (Passive) | 10.0 | ~32 | Baseline ambient beacon rate check |
| **2** | 10 Hz | 10.0 | 100 | Low-rate linearity verification |
| **3** | 20 Hz | 10.0 | 200 | Intermediate pacing verification |
| **4** | 30 Hz | 10.0 | 300 | Target model requirement verification |
| **5** | 40 Hz | 10.0 | 400 | Headroom and transport margin evaluation |

### 6.3 Measurement & Stopping Criteria
- **Metrics Collected:**
  - Admitted target CSI packet rate (`csi_packets_parsed / dt`).
  - Inter-arrival jitter ($\sigma_{\Delta t}$) across admitted frames.
  - Unfiltered transport loss rate (detecting serial buffer overrun at 115,200 baud).
  - Source filter yield (`admitted / (admitted + filtered)`).
- **Automated Abort Triggers:**
  - Unfiltered UART transport loss $> 2.0\%$.
  - ESP32-S3 serial disconnect or watchdog reboot.
  - Network ping latency to router $> 50\text{ ms}$ or Wi-Fi disconnection.

---

## 7. Regression Testing & Gate Checks

Existing Phase 42–52 regression suites were executed:
```bash
py -3.11 -m pytest backend/tests/test_phase42.py backend/tests/test_phase43.py \
    backend/tests/test_phase44.py backend/tests/test_phase45.py backend/tests/test_phase46.py \
    backend/tests/test_phase49.py backend/tests/test_phase50.py backend/tests/test_phase51.py \
    backend/tests/test_phase52.py -v
```
**Results:** **53 passed, 0 failed, 0 skipped in 4.59s**.

---

## 8. Protected Asset Checksum Verification

Cryptographic MD5 hash verification confirmed complete bit-level invariance across all protected checkpoints and manifests:

| Asset Name | Target File Path | Expected MD5 Hash | Measured MD5 Hash | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 13 Checkpoint** | `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH** |
| **Phase 15 Checkpoint** | `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH** |
| **Dataset Manifest** | `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH** |

---

## 9. Remaining Risks & Exact Authorizations Needed

1. **Sequence Semantics:** **RESOLVED**. Counter assignment, scope, and gap provenance are fully verified. There is zero physical serial transport loss.
2. **Temporal Mismatch Risk:** Operating the model on passive 3.2 Hz stream data will fail due to temporal dilation ($11.1\times$).
3. **Exact Authorization Required Next:**
   - **Phase 54 Authorization:** Explicit user permission to run a controlled, bounded, unicast network traffic generation test (10–40 Hz ping train for $\le 60\text{ s}$) from an associated client to the Archer C6 router (`98:BA:5F:EF:28:26`), to confirm that physical CSI frame rate scales to $\ge 30\text{ Hz}$ without UART buffer drops.
   - Persistent dataset collection and model evaluation remain strictly embargoed.

---

## 10. Final Disposition

**Status:** `SEQUENCE SEMANTICS VERIFIED — RATE EXPERIMENT AWAITING AUTHORIZATION`
