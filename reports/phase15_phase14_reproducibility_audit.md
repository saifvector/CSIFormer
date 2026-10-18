# CSIFormer Phase 15 — Phase 14 Reproducibility Audit & Forensic Verification

**Document Version:** 1.0.0  
**Date:** October 18, 2026  
**Auditor:** Principal Wireless Sensing Research Scientist & RF Signal Processing Auditor  
**Production Checkpoint:** [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth)  
**Verification Target:** Phase 14 Hardware Ingestion, Streaming Pipeline, and Reported Telemetry  
**Audit Status:** AUDIT COMPLETE — DISCREPANCIES IDENTIFIED & DOCUMENTED

---

## 1. Executive Summary

In accordance with Phase 15 Stage 1 directives, an exhaustive forensic reproducibility audit was conducted on all Phase 14 claims, implementation code, automated tests, checkpoint hashes, and hardware telemetry.

### Key Audit Findings:
1. **Production Checkpoint Hash Integrity:** **CONFIRMED 100% UNCHANGED**.
   - MD5: `383b4d98c08f8970b0443738f170ec01`
   - SHA256: `d8683ece1bc9760ab7082879cb9f95b7dd368c93c0420c4f65c5867bb3e608cf`
   - Verified before and after all automated testing.
2. **Automated Test Reproducibility:** **CONFIRMED 100% PASS RATE**.
   - `backend/tests/test_phase14.py`: 10 passed, 0 failed (8.34s).
   - `backend/tests/test_phase10.py` & `test_phase06.py`: 20 passed, 0 failed (51.87s).
3. **Latency & Throughput Computational Reproduction:** **CONFIRMED ACCURATE**.
   - Preprocessing latency: $9.06\text{ ms}$ (P50).
   - Model inference latency: $7.03\text{ ms}$ (P50 on NVIDIA RTX 3050 Laptop GPU).
   - End-to-end latency: $16.27\text{ ms}$ (P50) / $23.12\text{ ms}$ (P99).
   - Sustained throughput: $61.5\text{ FPS}$ (exceeds $25\text{ FPS}$ requirement).
4. **Data Source of Reported 300-Window Benchmark:** **CRITICAL DISCREPANCY IDENTIFIED**.
   - Inspection of `scratch/execute_phase14_4_streaming_validation.py` lines 248–257 revealed that `csi_session_1787048133.json` was not loaded (path mismatch and mock single-packet content), causing the execution to enter the fallback branch:
     `subcarrier_stream = [list(15.0 + np.random.randn(56) * 1.5) for _ in range(500)]`.
   - **Conclusion:** While the computational execution latency is mathematically accurate for $[50, 56]$ float matrices, the RF data contents of the 300 sliding windows benchmarked in Phase 14 were **synthetically generated in memory**, not captured live from hardware.
5. **Firmware Subcarrier Truncation:** **EMPIRICALLY CONFIRMED VIA DIRECT COM5 PROBE**.
   - Real-time probing of `COM5` confirmed the running firmware outputs:
     `RSSI=-59 LEN=128 CSI:0,0,-21,-2,-27,-4,-24,-3,-19,-3,`
   - Only 5 complex subcarrier pairs (10 numbers) are printed despite `LEN=128` hardware capture.
   - `RealCSICollector` linearly interpolates these 5 measurements to 56 subcarriers, which hallucinates spatial tone details.
6. **Ambient Capture Packet Rate:** **MEASURED AT ~2.0 TO 5.0 HZ**.
   - Without an active Wi-Fi traffic generator (e.g., continuous UDP ping or high-rate traffic stream), beacon packet reception is restricted to ~2–5 Hz, requiring ~10–25 seconds to fill a 50-frame buffer.

---

## 2. Production Checkpoint Verification

The Phase 13 production model weights were audited before and after running test executions:

```
+--------------------------------------------------------------------------------------------------+
|                                    CHECKPOINT FORENSIC AUDIT                                     |
+--------------------------+-----------------------------------------------------------------------+
| Attribute                | Verified Value                                                        |
+--------------------------+-----------------------------------------------------------------------+
| Checkpoint Path          | models/csiformer_phase13_best.pth                                     |
| File Size                | 6,091,354 bytes                                                       |
| MD5 Hash (Pre-Test)      | 383b4d98c08f8970b0443738f170ec01                                     |
| MD5 Hash (Post-Test)     | 383b4d98c08f8970b0443738f170ec01 (Exact Match)                       |
| SHA256 Hash              | d8683ece1bc9760ab7082879cb9f95b7dd368c93c0420c4f65c5867bb3e608cf     |
| Architecture Class       | CSIDualBranchFusionNet                                                |
| Model Parameters         | 2,114,828 float32 parameters                                          |
| Fusion Mode              | Gated Attention (Raw Amplitude + Doppler DFS)                         |
+--------------------------+-----------------------------------------------------------------------+
```

---

## 3. Discrepancy Matrix: Reported Claims vs Ground Truth Evidence

```
+-----------------------------------------------------------------------------------------------------------------------------+
|                                                   PHASE 14 AUDIT MATRIX                                                     |
+------------------------------+-------------------------------+-------------------------------+------------------------------+
| Investigation Item           | Phase 14 Reported Status      | Actual Ground-Truth Evidence  | Forensic Audit Verdict       |
+------------------------------+-------------------------------+-------------------------------+------------------------------+
| Physical ESP32-S3 Detection  | COM5 (WCH CH343)              | USB\VID_1A86&PID_55D3 (COM5)  | VERIFIED & ACCURATE          |
| Wi-Fi AP Ingestion           | Tp link, Channel 7 (-55 dBm)  | RSSI -57 dBm, Ch 7, LEN=128   | VERIFIED & ACCURATE          |
| Checkpoint Hash Integrity    | Phase 13 preserved            | MD5: 383b4d98c08f89...        | VERIFIED & ACCURATE          |
| 300-Window Benchmark Data    | "Real hardware capture"       | Memory generator: 15.0+randn  | DISCREPANCY: SYNTHETIC DATA  |
| Subcarrier Dimension         | 56 active tones from hardware | 5 physical tones -> 56 interp | DISCREPANCY: 11.2x INTERP    |
| Live Packet Rate             | 30.0 Hz sustained             | 2.0 to 5.0 Hz (ambient)       | DISCREPANCY: TRAFFIC LIMITED |
| Computation Pipeline Latency | 16.27 ms (P50), 61.5 FPS      | 16.27 ms (P50), 61.5 FPS      | VERIFIED & ACCURATE (COMP)   |
| Fall Recall Preservation     | 100.00% (44/44 held-out falls)| 100.00% (44/44 held-out falls)| VERIFIED & ACCURATE          |
| Input Fault Rejection        | 4/4 fault cases rejected      | 4/4 fault cases rejected      | VERIFIED & ACCURATE          |
+------------------------------+-------------------------------+-------------------------------+------------------------------+
```

---

## 4. Root Cause Analysis

### 4.1 Benchmark Data Source Mismatch
In `scratch/execute_phase14_4_streaming_validation.py`, line 249:
```python
session_file = BASE_DIR / "csi_session_1787048133.json"
```
The file was located in `BASE_DIR / "data" / "recordings" / "csi_session_1787048133.json"`, causing `session_file.exists()` to evaluate to `False`. Furthermore, inspection of the actual JSON file revealed it contained only a single mock packet with static amplitude `15.0`. The script automatically fell back to Gaussian noise around static level `15.0`.

**Impact on Results:**
- **Latency & Throughput:** Unaffected. PyTorch CUDA tensor operations and SciPy STFT algorithms take identical processor cycles regardless of tensor values.
- **Classification Predictions:** The reported sample predictions (`Push&Pull`, `Walk`, etc.) in the 300-window test were model inferences on synthetic noise, NOT real human gestures.

### 4.2 Firmware Printf Truncation
The ESP-IDF firmware flashed on the ESP32-S3 captures `LEN=128` (64 complex tones), but the UART output loop restricts logging to the first 10 integers (5 complex subcarriers). 
`RealCSICollector` bridges this gap using 1D linear interpolation:
```python
aligned_amp = np.interp(x_new, x_old, raw_amps).astype(np.float32)
```
This maps 5 tones into 56 tones. While dimensionally compatible with `[1, 50, 56]`, it severely attenuates higher-frequency spatial multipath information.

### 4.3 Ambient Beacon Rate vs 30 Hz Requirement
Standard 802.11 beacon intervals are typically 100 TU (~102.4 ms $\approx 9.76\text{ Hz}$). When the AP is idle (no active streaming), the ESP32-S3 in promiscuous mode only captures occasional beacon and management frames (2–5 Hz). Reaching 30–100 Hz CSI sampling requires sustained Wi-Fi traffic (such as high-rate UDP pings, video streaming, or iperf3 traffic).

---

## 5. Corrective Action Plan for Phase 15

1. **Establish a Real-CSI Dataset Collection Pipeline:**
   - Record immutable multi-packet sessions from real hardware with dedicated metadata manifests.
   - Implement controlled Wi-Fi traffic generation (continuous ping / UDP burst) to achieve stable $\ge 30\text{ Hz}$ frame rates.
2. **Domain Gap Adaptation:**
   - Account for the 5-tone vs 56-tone subcarrier interpolation.
   - Implement Doppler scaling correction ($2.38\times$ factor for 2.4 GHz vs 5.8 GHz).
   - Implement temporal resampling with anti-aliasing.
3. **Rigorous Baseline Evaluation:**
   - Evaluate the unmodified Phase 13 checkpoint on actual captured ESP32-S3 CSI frames.
   - Clearly separate offline dataset evaluation from real-world hardware evaluations.
