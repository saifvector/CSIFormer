# Phase 58.1: Passive Baseline Evidence and Metric Audit

**Execution Date:** 2026-10-21  
**Audit Scope:** Independent verification of Phase 58 Stage 1 hardware report, capture script, and execution logs.  
**Operational Mode:** Strictly offline audit. Zero hardware communication, zero COM5 access, zero network traffic, zero firmware flashing, zero model operations.  
**Final Verdict:** **PARTIALLY VERIFIED**

---

## 1. Executive Summary

This audit independently reviews the physical baseline capture reported in [`reports/phase58_stage1_passive_baseline.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase58_stage1_passive_baseline.md), the capture script [`scratch/run_phase58_stage1_passive.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_phase58_stage1_passive.py), and the raw task execution log (`task-1258.log`).

### Key Audit Findings:
1. **Physical Execution Confirmed:** The 30-second passive capture executed on `COM5` from 07:36:12Z to 07:36:42Z UTC (duration: 30.0044 s). Serial port `COM5` was cleanly closed and released post-capture.
2. **Mathematical Reconciliations Match:**
   - Candidate parse fraction: $316 / 318 = 99.371\%$ ($99.37\%$).
   - Total candidates: $316 \text{ parsed} + 2 \text{ parse errors} = 318$.
   - Total valid parsed: $107 \text{ target} + 209 \text{ non-target} = 316$.
   - Total raw lines: $318 \text{ candidates} + 15 \text{ non-candidate lines} = 333$.
   - Target arrival rate: $107 / 30.0044 \text{ s} = 3.5661 \text{ Hz}$ ($3.566 \text{ Hz}$).
   - Aggregate arrival rate: $316 / 30.0044 \text{ s} = 10.5318 \text{ Hz}$ ($10.532 \text{ Hz}$).
3. **Evidence Limitation (Absence of Persisted Raw Record Trace):**
   - The capture script held individual packet records in memory and emitted summary statistics and 5 sample raw lines to stdout.
   - The individual per-packet timestamp array ($t_1, \dots, t_{107}$) was not saved to disk as a raw artifact. Consequently, the individual $\Delta t_i$ values and exact quantile distributions cannot be independently re-binned or re-calculated from scratch.
4. **Metric Terminology Correction:**
   - The ratio $316 / 318$ ($99.37\%$) was previously labeled as "UART Delivery Success Rate". This is scientifically inaccurate; it is the **candidate-record parse success fraction**.
   - `firmware_sequence_gaps: 2` represents callback sequence counter discontinuities among observed parsed records, not physical UART transport loss.
   - `target_sequence_gaps: 206` reflects global sequence number interleaving from 209 ambient non-target frames, not target router packet drops.

---

## 2. Evidence Inspected & Raw Data Availability

| Artifact | Location | Nature of Evidence | Availability / Status |
|---|---|---|---|
| **Phase 58 Stage 1 Report** | [`reports/phase58_stage1_passive_baseline.md`](file:///c:/Users/saifu/Desktop/4-1%20project/reports/phase58_stage1_passive_baseline.md) | Formatted findings & tables | Complete |
| **Capture Script** | [`scratch/run_phase58_stage1_passive.py`](file:///c:/Users/saifu/Desktop/4-1%20project/scratch/run_phase58_stage1_passive.py) | Capture execution logic & CLI | Complete |
| **Task Execution Log** | `task-1258.log` | Stdout output containing full JSON result and raw sample lines | Complete |
| **Raw Per-Packet Timestamps** | In-memory only during capture | Individual arrival timestamps ($t_i$) for 316 packets | **Not Persisted to Disk** |
| **Raw Serial Byte Dump** | In-memory buffer only | Full raw serial log of all 333 lines | **Not Persisted to Disk** |

### Explicit Statement on Non-Recalculable Metrics:
Because the full array of raw timestamps was not written to a standalone `.json` or `.csv` artifact, the following metrics **cannot be independently recalculated from raw ground truth** and must be taken from the script's emitted summary:
- Individual inter-arrival intervals $\Delta t_i = t_i - t_{i-1}$.
- Percentile quantiles (P50 = 149.90 ms, P95 = 806.84 ms).
- Standard deviation of target intervals (242.18 ms) and aggregate intervals (38.10 ms).
- Minimum and maximum observed intervals (72.19 ms, 1607.07 ms).

---

## 3. Metric Recalculations and Reconciliations

### 3.1 Timing and Acquisition Rates

| Metric | Stage 1 Reported | Audit Recalculation | Formula | Status |
|---|---|---|---|---|
| **Wall Clock Duration** | — | **30.0052 s** | $t_{\text{stop}} - t_{\text{start}} = 1792568202.268363 - 1792568172.263114$ | Validated |
| **Actual Perf Duration** | 30.0044 s | **30.0044 s** | $\Delta t_{\text{perf}}$ (monotonic high-res clock) | Validated |
| **Target Rate** | 3.566 Hz | **3.5661 Hz** | $107 / 30.0044 \text{ s}$ | Validated |
| **Aggregate Rate** | 10.532 Hz | **10.5318 Hz** | $316 / 30.0044 \text{ s}$ | Validated |

### 3.2 Record Counts Reconciliation

```text
Total Raw Lines (333)
├── Candidate Records (318)
│   ├── Valid Parsed Records (316)
│   │   ├── Target MAC: 98:BA:5F:EF:28:26 (107) [33.9%]
│   │   └── Filtered Ambient MACs (209) [66.1%]
│   │       ├── 00:2D:F4:5B:4B:7D (205) [64.9%]
│   │       ├── 18:CC:88:7E:74:71 (3)   [0.9%]
│   │       └── 80:5E:4F:21:03:FA (1)   [0.3%]
│   └── Parser Errors (2) [0.63%] (Initial serial buffer sync split)
└── Non-Candidate Serial Lines (15) (Startup logs, partial lines, blank lines)
```

- $316 \text{ valid} + 2 \text{ parse errors} = 318 \text{ candidates}$ (**Exact Match**).
- $107 \text{ target} + 209 \text{ non-target} = 316 \text{ valid}$ (**Exact Match**).
- $205 + 107 + 3 + 1 = 316 \text{ total by MAC}$ (**Exact Match**).
- $318 \text{ candidate} + 15 \text{ non-candidate} = 333 \text{ total raw lines}$ (**Exact Match**).

### 3.3 Interval Statistics Consistency Check

The script calculated intervals using monotonic time (`time.perf_counter()`):
- **Target intervals:** $107 - 1 = 106$ intervals.
  - Reported mean interval: $277.63 \text{ ms} = 0.27763 \text{ s}$.
  - Implied total span between first and last target frame: $106 \times 0.27763 \text{ s} = \mathbf{29.429 \text{ s}}$.
  - This fits properly inside the $30.0044 \text{ s}$ duration ($29.429 \text{ s} \le 30.0044 \text{ s}$).
- **Aggregate intervals:** $316 - 1 = 315$ intervals.
  - Reported mean interval: $94.76 \text{ ms} = 0.09476 \text{ s}$.
  - Implied total span: $315 \times 0.09476 \text{ s} = \mathbf{29.849 \text{ s}}$.
  - Fits properly within $30.0044 \text{ s}$ ($29.849 \text{ s} \le 30.0044 \text{ s}$).

---

## 4. Correct Metric Semantics & Terminology Corrections

The Stage 1 report used several legacy terms that must be formally corrected:

### 4.1 "UART Delivery Rate" vs "Parse Success Fraction"
- **Correction:** The ratio $316 / 318 \approx 99.37\%$ must **not** be called a "UART delivery rate".
- **Technical Basis:** Physical UART delivery can only be proven if the exact number of frames placed onto the UART bus by the ESP32-S3 firmware is known via hardware bus capture or internal firmware counters. The host only observed 318 candidate lines that arrived across serial. Among those 318 candidate lines, 316 were successfully parsed and 2 failed parse due to boundary chunking.
- **Correct Term:** **Candidate-Record Parse Success Fraction** ($316 / 318 = 99.371\%$).

### 4.2 Firmware Sequence Gaps
- **Correction:** `firmware_sequence_gaps: 2` measures **callback-counter discontinuities among observed records**.
- **Technical Basis:** It proves that between the first observed frame ($\text{seq}=6128$) and the final observed frame, the sequence counter skipped 2 counts. It does not prove whether those 2 frames were dropped on the UART wire, inside the FreeRTOS UART ring buffer, or by the ESP-IDF Wi-Fi driver before string emission.

### 4.3 Target Sequence Gaps
- **Correction:** `target_sequence_gaps: 206` is an artifact of **interleaving ambient traffic**, not packet loss.
- **Technical Basis:** The ESP32-S3 firmware maintains a single global callback counter. When an ambient packet arrives (such as from `00:2D:F4:5B:4B:7D`), the global counter increments. When the collector filters out that packet, the next packet from `98:BA:5F:EF:28:26` exhibits a gap. Over 30 seconds, 209 ambient packets were filtered, explaining the 206 target sequence gaps.

### 4.4 Disentangled Metric Taxonomy

| Metric Category | Value | What It Measures | What It Does NOT Prove |
|---|---|---|---|
| **Parser Errors** | 2 | Malformed / split candidate lines | Does not indicate wireless loss |
| **Filtered Records** | 209 | Valid frames from unassociated MACs | Does not indicate target corruption |
| **Callback Counter Gaps** | 2 | Discontinuities in global firmware counter | Does not prove UART wire drops |
| **Target Sequence Gaps** | 206 | Sequence jumps in filtered target stream | Does not indicate target router packet drops |
| **Parse Success Fraction** | 99.37% | Host parsing success on received candidate lines | Does not measure physical UART bus efficiency |

---

## 5. Assessment of Temporal Sufficiency

### 5.1 50-Frame Window Accumulation Estimates

CSIFormer processes gestures in sliding windows of 50 temporal frames. Based on the measured target baseline rate of approximately **3.566 Hz**:

$$\text{Estimated Time to Accumulate 50 Frames} = \frac{50 \text{ frames}}{3.5661 \text{ frames/s}} \approx \mathbf{14.02 \text{ seconds}}$$

Alternatively, using the observed mean inter-arrival time ($\bar{\Delta t} = 277.63 \text{ ms}$ over 49 intervals):

$$\text{Estimated Window Temporal Span} = 49 \times 0.27763 \text{ s} \approx \mathbf{13.60 \text{ seconds}}$$

> [!NOTE]
> These calculations represent an **offline estimate** based on steady-state passive beacon arrival rates. They do **not** represent a measured inference window duration, as no windowing buffer or inference pipeline was executed.

### 5.2 Comparison with Historical Training Distribution

| Parameter | Historical Dataset (Phase 16) | Passive Hardware Baseline (Phase 58 Stage 1) | Discrepancy Factor |
|---|---|---|---|
| **Sampling Rate** | 34.0–37.3 Hz (mean ~35.5 Hz) | **3.566 Hz** | **~10× slower** |
| **Mean Interval** | ~28.2 ms | **277.63 ms** | **~9.8× longer** |
| **50-Frame Window Span** | **~1.35–1.45 seconds** | **~13.6–14.0 seconds** | **~10× longer span** |
| **Target Packet Source** | Active traffic / Unicast link | Passive beacon/mgmt frames | Different traffic type |

### 5.3 Technical Implications for Model Temporal Requirements
1. **Passive Rate Inadequacy for Continuous Motion:** A typical human gesture (e.g. `push_pull`, `clap`, `sit`) spans 1.5 to 3.0 seconds. Under a passive 3.57 Hz capture rate, an entire 2-second gesture produces only 7 target frames. If a 50-frame window is forced, 43 of the 50 frames represent static pre-gesture or post-gesture background, severely degrading the gesture's time-frequency signature in the STFT spectrogram.
2. **Rate Sufficiency vs Model Necessity:**
   - The fact that 3.57 Hz is too slow to capture 2-second dynamic gestures does **not** scientifically prove that exactly 25 Hz or 35 Hz is a mathematically minimal requirement.
   - Passive arrival rate alone cannot establish model classification accuracy or define the strict lower bound of acceptable sampling frequency without controlled sensitivity experiments.

---

## 6. Safety & Asset Integrity Verification

- **COM5 & Hardware:** No communication with COM5 or any serial port occurred during Phase 58.1.
- **Network Traffic:** Zero UDP packets, ICMP pings, or network stimulation were transmitted.
- **Firmware:** No compilation or flashing was performed.
- **Models & Manifest:** Zero model training, evaluation, or manifest modifications were performed.

### Cryptographic Hash Audit:

| Asset | Expected MD5 | Actual Audited MD5 | Status |
|---|---|---|---|
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH** |

---

## 7. Remaining Uncertainties and Recommended Next Step

### Remaining Engineering Uncertainties:
1. **Raw Trace Persistence:** Phase 58 Stage 1 did not persist the raw list of individual arrival timestamps. Any future hardware stage must write a complete timestamp log to disk so independent audits have full raw ground truth.
2. **Behavior Under Active Traffic:** Because Phase 58 Stage 1 was strictly passive, it remains experimentally unverified whether low-rate unicast stimulation (e.g. 10–25 pkts/s) will scale target CSI acquisition cleanly without triggering buffer overruns.

### Recommended Next Step:
- **Proceed to Phase 58 Stage 2 Planning / Authorization:**
  - Before running Stage 2 (active traffic capture), update the capture harness to persist a complete per-record timestamp artifact (`stage2_raw_records.json`).
  - Stage 2 must remain bounded to a low-rate unicast probe (e.g. 5–10 Hz) with immediate abort conditions (latency > 50 ms or loss > 2%).
  - Do not begin Stage 2 automatically without explicit user authorization.

---

## 8. Final Audit Verdict

**PARTIALLY VERIFIED**

*Rationale:* The macro-metrics (30.0044 s duration, 3.566 Hz target rate, 10.532 Hz aggregate rate, 99.37% candidate parse success fraction, and full record count reconciliations) are verified and mathematically consistent. However, detailed quantile distributions (P50, P95, std dev) cannot be independently recalculated from raw ground truth because the per-packet timestamp array was not persisted to disk.
