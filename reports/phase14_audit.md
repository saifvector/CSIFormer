# CSIFormer Phase 14 — Stage 1 Complete Repository Audit Report

**Audit Date:** 2026-10-18T05:30:00Z  
**Auditor:** Principal Wireless Sensing Research Scientist & Machine Learning Architect  
**Objective:** Independent audit of codebase, models, preprocessing pipelines, firmware, and dependencies prior to Phase 14 implementation.

---

## 1. Verified Repository Inventory & Artifact Verification

| Component Category | Target Path | File Size | Status | Verification Summary |
| :--- | :--- | :---: | :---: | :--- |
| **Production Model** | [`models/csiformer_phase13_best.pth`](file:///c:/Users/saifu/Desktop/4-1%20project/models/csiformer_phase13_best.pth) | 6.09 MB | **VERIFIED** | Official Phase 13 production model (Gated Dual-Branch Fusion). Verified 0 missing, 0 unexpected keys on load. |
| **Model Architecture** | [`backend/app/models/csiformer_dual_branch.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/models/csiformer_dual_branch.py) | 10.8 KB | **VERIFIED** | `CSIDualBranchFusionNet` implementing dual spatial-spectral CNNs + temporal Transformers with learnable gating. |
| **Physics Preprocessor**| [`backend/app/services/physics_csi_preprocessor.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/physics_csi_preprocessor.py) | 13.1 KB | **VERIFIED** | Static reflection subtraction ($H - \bar{H}$), phase linear detrending, and STFT Doppler velocity conversion. |
| **Hardware Adapter** | [`backend/app/services/esp32_csi_adapter.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_csi_adapter.py) | 9.5 KB | **VERIFIED** | Cubic spline subcarrier alignment from 30/64/114 subcarriers to standardized ESP32-S3 HT20 (56 subcarriers). |
| **Hardware Manager** | [`backend/app/services/esp32_hardware_manager.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/esp32_hardware_manager.py) | 5.8 KB | **VERIFIED** | Serial/UDP device status tracking. Contains mock ports (COM3/4) that need updating to dynamic COM detection. |
| **Dataset Recorder** | [`backend/app/services/dataset_recorder.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/services/dataset_recorder.py) | 4.6 KB | **VERIFIED** | JSON/CSV session capture engine for offline dataset export. |
| **Firmware Source** | [`firmware/esp32s3_csi_collector/main/main.c`](file:///c:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/main/main.c) | 4.1 KB | **VERIFIED** | ESP-IDF C source implementing `wifi_csi_rx_cb` with 921,600 baud serial and UDP 5555 streaming. |
| **Firmware Config** | [`firmware/esp32s3_csi_collector/platformio.ini`](file:///c:/Users/saifu/Desktop/4-1%20project/firmware/esp32s3_csi_collector/platformio.ini) | 248 B | **VERIFIED** | Target: `esp32-s3-devkitc-1`, Platform: `espressif32`, Framework: `espidf`, Monitor speed: `921600`. |
| **Backend API** | [`backend/app/main.py`](file:///c:/Users/saifu/Desktop/4-1%20project/backend/app/main.py) | 7.3 KB | **VERIFIED** | FastAPI application hosting REST endpoints and 30 Hz spatial telemetry WebSocket loop. |
| **Frontend Web App** | [`frontend/src/App.tsx`](file:///c:/Users/saifu/Desktop/4-1%20project/frontend/src/App.tsx) | 12.8 KB | **VERIFIED** | React 19 + React Three Fiber 3D digital twin HUD displaying real-time point clouds and predictions. |

---

## 2. Model Parameters & Input Dimensions

Audited directly from `CSIDualBranchFusionNet` and `csiformer_phase13_best.pth`:

- **Input Tensor Dimensions:**
  - **Branch A (Raw Amplitude):** Shape `[Batch, 50, 56]` (50 timesteps, 56 HT20 subcarriers, normalized $\ge 0$).
  - **Branch B (Doppler DFS):** Shape `[Batch, 50, 56]` (50 timesteps, 56 Doppler velocity bins, Hann-windowed STFT).
- **Core Hyperparameters:**
  - `embed_dim`: `128`
  - `nhead`: `8`
  - `num_layers`: `3`
  - `dim_feedforward`: `512`
  - `dropout`: `0.1`
  - `fusion_mode`: `"gated"`
  - `num_classes`: `12`
- **Class Label Dictionary (`DEFAULT_CLASSES`):**
  - Index 0: `Push&Pull` (Widar 3.0 gesture)
  - Index 1: `Sweep` (Widar 3.0 gesture)
  - Index 2: `Clap` (Widar 3.0 gesture)
  - Index 3: `Slide` (Widar 3.0 gesture)
  - Index 4: `Draw-O` (Widar 3.0 gesture)
  - Index 5: `Draw-Zigzag` (Widar 3.0 gesture)
  - Index 6: `box` (NTU-Fi activity)
  - Index 7: `circle` (NTU-Fi activity)
  - Index 8: `clean` (NTU-Fi activity)
  - Index 9: `fall` (**Life-Safety Critical Class**, 100% recall requirement)
  - Index 10: `run` (NTU-Fi activity)
  - Index 11: `walk` (NTU-Fi activity)

---

## 3. Discrepancy & Gap Analysis

1. **Hardware Serial Driver in Python:**
   `pyserial` is required for Python 3.11 to interface with `COM5`. While PowerShell can read COM5 via `.NET`, the backend service (`real_csi_collector.py`) requires native non-blocking asynchronous Python serial ingestion.
2. **Dynamic Serial Port Discovery:**
   `backend/app/services/esp32_hardware_manager.py` contained hardcoded placeholder ports (`COM3`, `COM4`). It must be upgraded to dynamically discover available COM ports (such as `COM5` with CH343 VID/PID `1A86:55D3`).
3. **Telemetry Packet Ingestion Flexibility:**
   The running firmware emits lines formatted as:
   `=== CSI CALLBACK FIRED ===`
   `RSSI=-55 LEN=128 CSI:0,0,-17,-4,-17,-4,-14,-3,-9,-3,`
   Whereas the repository firmware emits:
   `CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,amp_0:phase_0,amp_1:phase_1,...`
   The receiver must support **both telemetry protocols seamlessly**, parsing subcarriers, estimating noise floors, tracking sequence numbers, and interpolating to 56 subcarriers via `ESP32CSIAdapter`.
4. **Temporal Window Buffer:**
   Incoming CSI packets arrive frame-by-frame (~10 to 30 Hz). CSIFormer requires a sliding temporal window of exactly **50 timesteps**. A thread-safe circular window buffer is required to feed inference without dropping frames or blocking the serial stream.

---

## 4. Phase 14 Implementation Plan

```
+---------------------------------------------------------------------------------------+
|                               PHASE 14 EXECUTION MAP                                  |
+---------------------------------------------------------------------------------------+
|  Stage 0 & 1: Hardware Pre-Check & Repo Audit [COMPLETED]                             |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 2: CSI Capture & Protocol Verification                                         |
|       ├── Install `pyserial` in Python 3.11 environment                               |
|       ├── Verify dual-protocol parser (raw IQ and CSI_DATA formatted strings)         |
|       └── Validate subcarrier alignment to 56 HT20 channels                           |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 3: Real-Time Laptop Receiver (`RealCSICollector`)                             |
|       ├── Implement `backend/app/services/real_csi_collector.py`                      |
|       ├── Thread-safe COM port reader with auto-reconnect & packet loss tracking      |
|       └── 50-sample sliding window queue with microsecond timestamping                |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 4: End-to-End Phase 13 Model Integration                                       |
|       ├── Connect receiver window to `PhysicsCSIPreprocessor`                         |
|       ├── Compute STFT Doppler DFS and Raw Amplitude tensors                          |
|       └── Feed `CSIDualBranchFusionNet` for real-time live inference                  |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 5: FastAPI & WebSocket API Integration                                         |
|       ├── Expose `/api/v1/hardware/live-csi` and `/api/v1/hardware/connect`           |
|       └── Stream real hardware CSI & predictions into the 3D Frontend HUD             |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 6: Automated Testing Suite                                                     |
|       ├── Implement `backend/tests/test_phase14.py` (packet parsing, protocol,        |
|       │   windowing, model loading, dummy inference, disconnect recovery)             |
|       └── Run `pytest backend/tests/test_phase14.py` and record outputs               |
|       │                                                                               |
|       ▼                                                                               |
|  Stage 7: Real-Hardware Live Validation & Reports                                     |
|       ├── Stream live Wi-Fi packets from COM5 through the complete pipeline           |
|       ├── Generate `reports/phase14_hardware_integration.md`                          |
|       └── Generate `reports/phase14_validation.md`                                    |
+---------------------------------------------------------------------------------------+
```
