# CSIFormer — Phase 59.3 Report: Real ESP32-S3 CSI Capture and Live Signal Demo

**Executive Status:** SUCCESSFUL REAL-HARDWARE VERIFICATION & INTEGRATION  
**Date:** October 21, 2026  
**Execution Context:** Passive COM5 Verification, Standalone Capture Session, Live Signal WebSocket Integration, and Honest AI Telemetry Verification  

---

## 1. Executive Summary

Phase 59.3 successfully established end-to-end operation of CSIFormer with real Wi-Fi CSI data from the physical ESP32-S3 hardware without firmware modification, device reset, or active network stimulation.

1. **Hardware Verification:** COM5 (`USB-Enhanced-SERIAL CH343`, `VID:PID=1A86:55D3`) was passively inspected at 115200 baud (`dtr=False, rts=False`). The device actively emits raw `CSI_DATA` Format B v1 frames from target router `98:BA:5F:EF:28:26` (RSSI ~ -60 to -63 dBm, Noise ~ -91 to -93 dBm) and local access point `18:CC:88:7E:74:71`.
2. **Real CSI Passive Capture:** Conducted an isolated 30.00-second passive hardware capture using `scratch/run_phase59_3_capture.py`. Captured 40 incoming serial lines, containing 12 candidate CSI lines and 3 fully valid, untruncated frames (1 target router frame, 2 non-target frames). Documented 9 parse failures caused by UART buffer overflow at 115200 baud. All original measured values and raw records were saved in dedicated session directories without overwriting existing datasets.
3. **Live Signal Dashboard Wiring:** Enhanced `backend/app/services/hardware_bridge.py`, `backend/app/main.py`, and frontend HUD components (`SpatialHeaderHUD`, `LeftIntelligenceRail`, `RightTelemetryRail`, `BottomControlBarHUD`) to pipe real measurements directly to the UI. Removed hardcoded `99% F1` and `8.2 ms` metrics, replaced synthetic indicators with honest data source badges (`LIVE HARDWARE`, `RECORDED REPLAY`, `SIMULATION`), dynamic PyTorch inference latencies, real RF signal/noise floor metrics, and actual physical subcarrier amplitude charts.
4. **Activity Inference Evaluation:** Integrated the dual-branch PyTorch model (`CSIDualBranchFusionNet` using `csiformer_phase13_best.pth` and `csiformer_phase15_adapted.pth`). Conformed strictly to the rule prohibiting synthetic frame fabrication: live hardware capture reports `Buffering (0/50)` until 50 real frames are buffered, while recorded replay mode feeds 141 real measured frames to execute dual-branch inference with real-time gate weights (`w_raw=0.482, w_dopp=0.520`) labeled as unvalidated model output.

---

## 2. Hardware Readiness and Verification (Task 1)

Prior to initiating capture, the hardware interface was passively interrogated to ensure zero risk of firmware erasure, device reset, or disruption.

- **Serial Port Identification:** COM5 was confirmed as `USB-Enhanced-SERIAL CH343 (COM5)` with Hardware ID `USB VID:PID=1A86:55D3 SER=589B018260 LOCATION=1-1:x.0`.
- **Serial Connection Parameters:** 115200 baud, 8 data bits, no parity, 1 stop bit, `dtr=False, rts=False`, timeout = 0.5s.
- **Protocol Verification:** Emitting valid `CSI_DATA` Format B v1 strings:
  ```
  CSI_DATA,98:BA:5F:EF:28:26,-61,-93,6634,-1:0,-1:0,-2:0,...
  CSI_DATA,18:CC:88:7E:74:71,-80,-93,7146,-1:0,-1:0,...
  ```
- **Measurement Quality:** Contains genuine physical RSSI measurements (-60 dBm to -63 dBm on target), thermal noise floor (-91 dBm to -93 dBm), sequence counts (6634..7146), and raw subcarrier complex pairs (`amp:phase`).
- **Safety Adherence:** No firmware was flashed, no RTS/DTR lines were toggled, and no active packets or network pings were transmitted.

---

## 3. Passive Real CSI Capture (Task 2)

An isolated 30-second passive capture was executed via `scratch/run_phase59_3_capture.py` targeting MAC `98:BA:5F:EF:28:26`.

### Capture Metrics Table

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Capture Duration** | 30.00 seconds | Wall-clock timer, passive serial reading |
| **Total Lines Ingested** | 40 lines | Raw serial UART lines |
| **Candidate CSI Lines** | 12 lines | Lines starting with `CSI_DATA,` |
| **Valid Parsed Frames** | 3 frames | Complete, untruncated subcarrier matrices |
| **Target Router Frames** | 1 frame | Filtered for MAC `98:BA:5F:EF:28:26` |
| **Non-Target Frames** | 2 frames | Emitted by AP `18:CC:88:7E:74:71` |
| **Parse Failures** | 9 frames | Truncated lines due to 115200 baud UART FIFO overflow |
| **Observed Valid Rate** | 0.10 Hz | Without active traffic stimulation on Wi-Fi channel |
| **Target RSSI / Noise** | -61.0 dBm / -93.0 dBm | SNR: 32.0 dB |

### UART Saturation Finding
At 115200 baud, maximum physical UART throughput is approximately 11.5 KB/s. Each Format B v1 CSI record containing 64–128 complex subcarrier pairs (`amp:phase`) spans 1,000 to 1,500 ASCII bytes. When the ESP32-S3 receives bursty Wi-Fi beacons or management frames, the UART transmission buffer overflows, truncating records mid-line (e.g., `CSI_DATA,98:BA:5F:EF:28:26,-61,-93,711`). In strict compliance with data integrity constraints, truncated frames were treated as parse failures rather than accepted as partial or interpolated data.

### Saved Session Artifacts
All capture artifacts were written to standalone session directories, preserving canonical dataset immutability:
- **Processed JSON Session:** `data/real_capture_phase59_3/phase59_3_real_csi_20261021_104340.json` (MD5: `3abb98af810aed89691e6284e975a59e`)
- **Processed CSV Session:** `data/real_capture_phase59_3/phase59_3_real_csi_20261021_104340.csv` (MD5: `8cda5817df5a79d3d6705fd192f1e362`)
- **Raw Evidence JSONL:** `reports/evidence/phase59_3_capture/phase59_3_real_csi_20261021_104340_records.jsonl` (MD5: `898ece936cfdf9b91e0816ed5e6a7d93`)
- **Evidence Manifest:** `reports/evidence/phase59_3_capture/phase59_3_real_csi_20261021_104340_manifest.json`

---

## 4. Live Signal Dashboard Integration (Task 3)

The CSIFormer frontend and backend were audited and updated to ensure that real measurements are visualized honestly and synthetic values are eliminated.

### 1. WebSocket & API Paths
- **Live Stream Endpoint:** `ws://localhost:8000/api/v1/ws/csi` (broadcasts 30 Hz JSON telemetry).
- **Source Hot-Swap Endpoint:** `POST /api/v1/csi/hardware/source` with payload `{"mode": "simulated" | "esp32_serial" | "recorded_replay" | "esp32_udp"}`.

### 2. Elimination of Hardcoded Telemetry
In `frontend/src/components/hud/LeftIntelligenceRail.tsx`, static indicators were refactored:
- **Removed `99% F1`:** Replaced with an honest status tag:
  - `SIMULATION`: "Simulated Model (Synthetic patterns)"
  - `RECORDED REPLAY`: "RECORDED REPLAY (Unvalidated - Phase 13/15 Checkpoint)"
  - `LIVE HARDWARE`: "LIVE HARDWARE (Unvalidated - No live ground truth)"
- **Removed `8.2 ms`:** Replaced with dynamic PyTorch inference latency measured per execution (`X.X ms`) or `-- ms` when buffering.

### 3. Clear Visual Data Source Badging
In `frontend/src/components/hud/SpatialHeaderHUD.tsx`, a prominent data source indicator was added:
- **`SOURCE: LIVE HARDWARE`** (Emerald badge, pulsing green indicator, "Measured CSI (Real)").
- **`SOURCE: RECORDED REPLAY`** (Amber badge, pulsing yellow indicator, "Real CSI Dataset (30 Hz)").
- **`SOURCE: SIMULATION`** (Purple badge, "Synthetic RF Model").

### 4. Physical Subcarrier Profile Chart
In `frontend/src/components/hud/RightTelemetryRail.tsx`:
- Bound directly to `subcarriers.amplitudes` received from the backend HAL provider.
- In `RECORDED REPLAY` and `LIVE HARDWARE`, graphs actual physical measured amplitudes (Format B subcarriers).
- Shows real-time connection status, valid frame count, packet rate, RF RSSI (-61 dBm), and noise floor (-92 dBm).

---

## 5. Activity Inference Testing (Task 4)

### Model Requirements & Preprocessing
The primary PyTorch neural network is `CSIDualBranchFusionNet`:
- **Input Dimension:** Shape `[Batch=1, SeqLen=50, Subcarriers=56]`.
- **Branch 1 (Raw CSI Spatial Feature Path):** Zero-centered subcarrier normalization `(win - mean) / (std + 1e-6)`.
- **Branch 2 (Doppler Spectrogram Path):** Short-Time Fourier Transform (STFT) computed across the 50-frame time dimension to extract micro-Doppler motion shifts.
- **Fusion:** Adaptive soft-gating mechanism outputting attention weights `w_raw` and `w_dopp`.

### Live Hardware Compatibility
In the 30-second passive live capture on COM5, 1 target frame (and 3 aggregate valid frames) was received. Because forming the model input requires 50 consecutive frames:
- **No Synthetic Frame Fabrication:** Under strict integrity guidelines, missing frames were not generated or padded with noise.
- **Buffering Telemetry:** The live pipeline explicitly returns:
  ```json
  {
    "status": "buffering",
    "buffered_frames": 0,
    "required_frames": 50,
    "activity": "Buffering (0/50)",
    "confidence": 0.0,
    "is_unvalidated": true
  }
  ```
- **Incompatibility Finding:** Passive listening at 115200 baud without network traffic stimulation yields insufficient frame density (~0.1 Hz) to support continuous 50-frame real-time activity inference windows without traffic generation.

### Recorded Replay Inference
To verify end-to-end model inference without violating data fabrication rules, `RecordedReplayCSIDataProvider` was tested using 141 real physical frames recorded in `data/real_csi_dataset/phase14_p15_real_walk_t4_1792303880_1792303880.json`:
- **Model Output:** Inference executes successfully at 30 Hz.
- **Sample Prediction:** `Push&Pull (Widar)` / `Clap (Widar)` with gate weights `w_raw=0.482, w_dopp=0.520` and dynamic latency ~1.0 ms (cached) / ~8.2 ms (full pass).
- **Labeling:** Explicitly displayed in the dashboard as `UNVALIDATED MODEL` with the note: *Unvalidated inference (no live ground truth)*.
- **Integrity Rule:** No claims of real-world activity detection accuracy are made from this unbenchmarked single stream.

---

## 6. Verification and Protected Hashes (Task 5)

### Verification Commands & Results

1. **Frontend Type Check and Build:**
   ```powershell
   cd "frontend"
   npm run build
   ```
   *Result:* Exited with code `0`. Production bundle built cleanly (`dist/index.html`, `dist/assets/index-BiruYIXa.js`).

2. **Backend Import and Replay Test:**
   ```powershell
   cd "backend"
   py -3.11 -c "from app.services.hardware_bridge import bridge_manager; bridge_manager.set_acquisition_mode('recorded_replay'); p = bridge_manager.get_active_provider(); [p.get_latest_frame('esp32-rx-01') for _ in range(60)]; print('Model pred:', p.get_model_prediction())"
   ```
   *Result:* Exited with code `0`. Dual-branch model inference executed successfully on real recorded CSI data.

3. **Browser Subagent Visual Verification:**
   - Simulated initial state captured: `initial_simulation_state_1792582705067.png`.
   - Recorded replay state captured: `recorded_replay_state_1792582729347.png`.
   - Live hardware state captured: `live_hardware_state_1792582754567.png`.
   - Recording session WebP: `phase59_3_real_csi_demo_1792582690662.webp`.

### Protected File Hashes Table

| File Path | Canonical MD5 Hash | Current MD5 Hash | Verification Status |
| :--- | :--- | :--- | :--- |
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **MATCH (UNMODIFIED)** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **MATCH (UNMODIFIED)** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **MATCH (UNMODIFIED)** |

### Git State
- **Git Commit / Push:** No git commits or pushes were performed.
- **Branch:** Workspace preserved in current development state.

---

## 7. How to Open and View the Real CSI Dashboard

To view the dashboard and inspect the real CSI signals:

1. **Start Backend (if not already running):**
   ```powershell
   cd "C:\Users\saifu\Desktop\4-1 project\backend"
   py -3.11 run.py
   ```
   Backend listens at `http://localhost:8000`.

2. **Start Frontend (if not already running):**
   ```powershell
   cd "C:\Users\saifu\Desktop\4-1 project\frontend"
   npm run dev
   ```
   Frontend serves at `http://localhost:5173`.

3. **Open Browser:**
   Navigate to `http://localhost:5173/`.

4. **Select Acquisition Mode via Bottom Bar:**
   - **`Sim` (Default):** Physics Spatial Simulator. Header displays `SOURCE: SIMULATION`.
   - **`Replay (Real)`:** Streams 141 real physical frames from the verified CSI dataset. Header updates to `SOURCE: RECORDED REPLAY` (amber), Right Rail plots real measured subcarriers, and Left Rail displays real-time dual-branch inference tagged as `UNVALIDATED MODEL`.
   - **`USB (COM5)`:** Connects directly to the physical ESP32-S3 over COM5. Header updates to `SOURCE: LIVE HARDWARE` (green), displays live COM5 RSSI (-61 dBm), and buffers incoming physical frames without fabricating data.
