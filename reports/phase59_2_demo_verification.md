# Phase 59.2: Existing System Demo and Functional Verification Report

**Author:** Antigravity AI Assistant  
**Date:** 2026-10-21  
**Execution Context:** Strictly Offline Verification (No Hardware Access, No Training, Hashes Protected)  
**Output Artifact:** `reports/phase59_2_demo_verification.md`

---

## Executive Summary

Phase 59.2 conducted an end-to-end inspection, startup verification, architectural audit, and functional test of the existing CSIFormer application stack. The system consists of a FastAPI backend streaming spatial and telemetry frames at 30 Hz and a Vite + React + Three.js frontend providing an interactive 3D digital twin room visualization with head-up displays (HUD).

**Key Findings:**
1. **Application Launch Succeeded:** Both the FastAPI backend (`http://localhost:8000`) and the Vite development server (`http://localhost:5173`) launched successfully and communicate over WebSockets without crashes.
2. **3D Visualization & Kinematics Fully Operational:** The Three.js 3D viewport renders room geometry, furniture, 3 ESP32-S3 sensor nodes, a Wi-Fi TX beacon, animated RF wave beams, a dynamic human avatar, ground heatmap, navmesh grid, and collision boundaries. Interactive camera switching (Isometric, Top Radar, Sensor Eye) and layer visibility toggles function as intended.
3. **Data Source is Exclusively Simulated:** The running application uses simulated synthetic data generated dynamically by `SimulatedSpatialCSIGeneratorProvider` (`spatial_simulator.py`). It does not connect to COM5 or live hardware, nor does it replay recorded sessions from `data/real_csi_dataset/`.
4. **Activity Recognition in Live UI is a Simulation Override:** The 30 Hz streaming loop in `main.py` passes the simulator's current state to `ActivityClassifierPipeline.predict_activity()`. That method explicitly checks `if current_simulated_state in self.classes: predicted_label = current_simulated_state` and clamps confidence to $\ge 88\%$. Selecting activity buttons in the UI merely switches the backend simulation state and updates the 3D avatar pose; it does not evaluate neural network accuracy on real CSI data.
5. **Dual-Branch PyTorch Model Disconnected from Live UI:** The trained 12-class `CSIDualBranchFusionNet` model is loaded in memory via `LivePipelineService`, but is only exposed to serial COM collector endpoints (`/api/v1/hardware/collector/*`), which remain inactive offline. When tested directly against real recorded CSI walking data (`phase14_p15_real_walk_t4_1792303880_1792303880.json`), the Phase 13 checkpoint predicted `Push&Pull (Widar)` (60.81%) and Phase 15 predicted `Clap (Widar)` (81.39%), demonstrating significant real-world domain discrepancy rather than accurate human activity detection.
6. **Hardcoded Dashboard Metrics Identified:** The dashboard displays "MODEL ACCURACY: 99% F1" and "INFERENCE LATENCY: 8.2 ms" as static JSX strings, and the backend evaluation endpoint returns a hardcoded mock confusion matrix.
7. **Protected Hashes Preserved:** All protected model checkpoints and the canonical dataset manifest remain unmodified.

---

## 1. Exact Commands Used to Start the Application

### 1.1 Backend Service
- **Command:**
  ```powershell
  py -3.11 run.py
  ```
  *(Alternative direct command: `py -3.11 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`)*
- **Working Directory:** Workspace root (`c:\Users\saifu\Desktop\4-1 project`)
- **Environment Variables:** None required; configuration defaults are managed in `backend/app/core/config.py` (`PORT=8000`, `HOST="0.0.0.0"`, `CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]`).
- **Bound Endpoints:**
  - REST API Root: `http://localhost:8000/`
  - Interactive OpenAPI Documentation: `http://localhost:8000/docs`
  - OpenAPI JSON Specification: `http://localhost:8000/api/v1/openapi.json`
  - 30 Hz Spatial Telemetry WebSocket: `ws://localhost:8000/api/v1/ws/csi`

### 1.2 Frontend Service
- **Command:**
  ```powershell
  cd frontend
  npm run dev
  ```
- **Working Directory:** `c:\Users\saifu\Desktop\4-1 project\frontend`
- **Bound URL:** `http://localhost:5173/`
- **Dependencies:** React 19, `@react-three/fiber`, `@react-three/drei`, `three`, `lucide-react`, `tailwindcss`, `vite`.

---

## 2. Local URL and Access Verification

| Service | Target URL | Verification Method | Status | Observation |
|---|---|---|---|---|
| **Frontend UI** | `http://localhost:5173/` | Chromium Subagent / HTTP GET | **ONLINE (HTTP 200)** | Fully interactive 3D HUD, camera controls, and avatar render cleanly. |
| **Backend Root** | `http://localhost:8000/` | HTTP GET / urllib | **ONLINE (HTTP 200)** | Returns `{"status":"online","system":"CSIFormer Spatial Intelligence Platform","version":"1.0.0-spatial"}` |
| **API Docs** | `http://localhost:8000/docs` | HTTP GET / urllib | **ONLINE (HTTP 200)** | Swagger UI documentation renders complete API schema. |
| **Telemetry Stream** | `ws://localhost:8000/api/v1/ws/csi` | Python `websockets` client | **ONLINE (30 Hz)** | Emits `csi_spatial_telemetry_frame` packets with target, kinematics, and zone data. |

---

## 3. Features Tested: Implemented vs. Placeholders & Mocks

### 3.1 Fully Implemented & Functional Features
1. **Three.js 3D Spatial Canvas (`SpatialCanvas3D`):**
   - Renders 3D digital twin room geometry (`DigitalTwinRoom3D`) including walls, floor, office desk, round meeting table, and chairs.
   - Renders 3 ESP32-S3 RX nodes and 1 Wi-Fi TX router with pulsing RF antenna ripples.
   - Renders dynamic Wi-Fi ray beams (`CSIRayBeams3D`) intersecting the target and nodes.
   - Renders 3D humanoid avatar (`HumanAvatar3D`) whose skeletal posture adapts to the current state (standing, sitting in chair, falling to floor, lying down).
   - Dynamic point cloud (`CSIPointCloud3D`), motion trajectory ribbon (`TrajectoryRibbon3D`), ground heatmap (`GroundHeatmap3D`), and NavMesh visualization (`NavMeshVisualizer3D`).
2. **Camera Controls & Scene Layer Toggles:**
   - Smooth viewport transitions between Isometric, Top Radar, and Sensor Eye presets.
   - 8 independent layer toggles (Spatial Grid, Sensor Nodes, Point Cloud, Wave Beams, Human Avatar, Motion Ribbon, Ground Heatmap, NavMesh & Colliders).
3. **3D Localization & Kinematics Engine:**
   - Smoothed 3D position tracking ($X, Y, Z$), velocity estimation ($v_x, v_y, v_z$), and speed calculation.
   - Semantic zone assignment mapping target coordinates to room zones ("Meeting Area", "Workspace Area", "Entrance Zone", "Waiting Area", "Restricted Area").
4. **Interactive State Switching:**
   - Clicking activity buttons in the left HUD sends `POST /api/v1/csi/simulation/activity`, updating the simulator state and immediately altering the 3D avatar posture and coordinate trajectory.

### 3.2 Placeholders, Mock Implementations, and Disconnected Components
1. **Live Activity Recognition is a Simulation Override:**
   - In `backend/app/services/activity_classifier.py`:
     ```python
     if current_simulated_state in self.classes:
         predicted_label = current_simulated_state
         pred_idx = self.classes.index(current_simulated_state)
     ```
   - The predicted label is explicitly overridden with the simulation target state, and confidence is clamped via `probs_map[cls_name] = round(float(max(0.88, probs_tensor[idx])), 3)`.
   - The underlying network in `activity_classifier.py` is `CSIFormerNet` (an uncalibrated prototype model in `backend/app/models/csiformer_net.py`), not the trained 12-class `CSIDualBranchFusionNet`.
2. **Dual-Branch PyTorch Model Disconnected from Frontend:**
   - `LivePipelineService` in `backend/app/services/live_pipeline_service.py` implements the dual-branch PyTorch model (`CSIDualBranchFusionNet`) loading `models/csiformer_phase13_best.pth` and `models/csiformer_phase15_adapted.pth`.
   - This service is only hooked to `/api/v1/hardware/collector/*`. When offline, `collector` is uninitialized, returning `{"status": "error", "error": "Collector not initialized"}`.
   - The frontend WebSocket stream does not consume or display predictions from `LivePipelineService`.
3. **Replay Functionality is Unwired / In-Memory Only:**
   - `frontend/src/components/hud/DigitalTwinHUD.tsx` contains a historical timeline replay slider (0 to 600s), but is orphaned (not imported or mounted in `App.tsx`).
   - The backend endpoint `/api/v1/spatial/memory/history` only rolls back in-memory simulated trajectory coordinates from `room_memory_service.py`, not CSI subcarrier recordings.
   - No frontend or backend player exists to stream recorded `.json`/`.csv` files from `data/real_csi_dataset/`.
4. **Hardcoded Dashboard Metrics:**
   - In `frontend/src/components/hud/LeftIntelligenceRail.tsx`, "MODEL ACCURACY: 99% F1" and "INFERENCE LATENCY: 8.2 ms" are static string literals.
   - In `backend/app/services/model_evaluator.py`, `evaluate_real_hardware_dataset()` returns a hardcoded $8 \times 8$ confusion matrix with static $99.4\%$ accuracy and $0.18\text{ m}$ localization error.
   - In `backend/app/api/endpoints/system.py`, CPU usage, memory usage, and latency are calculated using synthetic mathematical formulas based on system clock modulo.

---

## 4. Data Source Provenance

The active demo operates **strictly on simulated data**:
- **Active Data Provider:** `SimulatedSpatialCSIGeneratorProvider` (`backend/app/services/hardware_bridge.py`).
- **Generator Implementation:** `spatial_simulator.generate_frame()` (`backend/app/services/csi_spatial_simulator.py`).
- **Subcarrier Synthesis:** Generates 64 subcarriers per node using synthetic sinusoid curves and Gaussian noise perturbation.
- **Hardware Status:** `is_hardware_connected()` returns `False`. The serial COM port is closed, and COM5 was not opened or accessed.
- **Dataset Replay Status:** Real recorded sessions from `data/real_csi_dataset/` are not ingested by the active demo stream.

---

## 5. Actual Test Commands and Execution Results

### 5.1 Backend REST API Probing
All 16 major backend REST endpoints were probed via HTTP GET requests:
```powershell
py -3.11 -c "import urllib.request, json
# Probed 16 endpoints across system, localization, spatial, datasets, and hardware
"
```
**Results:**
- `GET /` $\rightarrow$ `200 OK` (bytes: 96)
- `GET /docs` $\rightarrow$ `200 OK` (bytes: 1045)
- `GET /api/v1/system/status` $\rightarrow$ `200 OK` (bytes: 213)
- `GET /api/v1/localization/nodes` $\rightarrow$ `200 OK` (bytes: 750)
- `GET /api/v1/csi/hardware/status` $\rightarrow$ `200 OK` (bytes: 293)
- `GET /api/v1/spatial/digital_twin` $\rightarrow$ `200 OK` (bytes: 1481)
- `GET /api/v1/spatial/insights` $\rightarrow$ `200 OK` (bytes: 449)
- `GET /api/v1/spatial/events` $\rightarrow$ `200 OK` (bytes: 180)
- `GET /api/v1/datasets/session/status` $\rightarrow$ `200 OK` (bytes: 297)
- `GET /api/v1/datasets/dashboard` $\rightarrow$ `200 OK` (bytes: 1278)
- `GET /api/v1/hardware/devices` $\rightarrow$ `200 OK` (bytes: 1095)
- `GET /api/v1/hardware/subcarriers?device_id=esp32-rx-01` $\rightarrow$ `200 OK` (bytes: 2549)
- `GET /api/v1/hardware/evaluation/report` $\rightarrow$ `200 OK` (bytes: 610)
- `GET /api/v1/hardware/collector/status` $\rightarrow$ `200 OK` (bytes: 156)
- `GET /api/v1/hardware/collector/window` $\rightarrow$ `200 OK` (bytes: 39)
- `GET /api/v1/hardware/collector/prediction` $\rightarrow$ `200 OK` (bytes: 54)

### 5.2 Real CSI Window Inference Test
To evaluate actual model inference pipeline performance, a real recorded session window from `data/real_csi_dataset/phase14_p15_real_walk_t4_1792303880_1792303880.json` (Ground Truth: `Walk`) was preprocessed and evaluated through `LivePipelineService`:
```powershell
py -3.11 -c "import sys; sys.path.insert(0, 'backend')
import json, numpy as np, torch
from app.services.live_pipeline_service import live_pipeline_service, LABEL_MAP
from pathlib import Path

session_file = Path('data/real_csi_dataset/phase14_p15_real_walk_t4_1792303880_1792303880.json')
# Preprocessed window [50, 56] and evaluated through phase13 and phase15 checkpoints
"
```
**Results:**
- Input: 50 frames $\times$ 56 subcarriers real ESP32-S3 CSI amplitude matrix.
- **Default Checkpoint (`csiformer_phase13_best.pth`):**
  - Predicted Class: `Class 0 (Push&Pull (Widar))`
  - Confidence: $0.6081$
  - Top 3 Probabilities:
    1. Class 0 (`Push&Pull (Widar)`): $0.6081$
    2. Class 2 (`Clap (Widar)`): $0.2945$
    3. Class 3 (`Slide (Widar)`): $0.0386$
  - Actual Label: `Walk` (Class 11) $\rightarrow$ **Incorrect (0.00% accuracy on sample)**.
- **Adapted Checkpoint (`csiformer_phase15_adapted.pth`):**
  - Predicted Class: `Class 2 (Clap (Widar))`
  - Confidence: $0.8139$
  - Top 3 Probabilities:
    1. Class 2 (`Clap (Widar)`): $0.8139$
    2. Class 3 (`Slide (Widar)`): $0.1398$
    3. Class 0 (`Push&Pull (Widar)`): $0.0140$
  - Actual Label: `Walk` (Class 11) $\rightarrow$ **Incorrect (0.00% accuracy on sample)**.

This proves that while the neural network inference forward pass executes without errors, the model outputs collapsed gesture classes on real ESP32-S3 Wi-Fi CSI data, matching the findings of the Phase 59 evaluation audit.

### 5.3 Automated Backend Test Suite
The full backend pytest regression suite was executed:
```powershell
py -3.11 -m pytest backend/tests/ -q
```
**Result:** 376 passed in 105.88s (100% pass rate).

---

## 6. Identified Discrepancies and Minimum Remediation Steps

| Discrepancy / Gap | Root Cause | Severity | Minimum Remediation Step |
|---|---|---|---|
| **Live UI doesn't use trained dual-branch model** | `ActivityClassifierPipeline` in `activity_classifier.py` uses prototype `CSIFormerNet` with hardcoded simulation bypass. | **HIGH** | Replace `ai_pipeline` with `LivePipelineService` in `main.py` so the streaming loop feeds actual window tensors through `CSIDualBranchFusionNet`. |
| **No replay player for recorded datasets** | Replay HUD is orphaned; backend lacks a recorded `.json`/`.csv` frame feeder. | **MEDIUM** | Implement a `RecordedCSIReplayProvider` in `hardware_bridge.py` that reads timestamps and subcarriers from `data/real_csi_dataset/` and broadcasts them over `/api/v1/ws/csi`. |
| **Hardcoded dashboard accuracy & latency** | `LeftIntelligenceRail.tsx` has literal JSX strings (`99% F1`, `8.2 ms`). | **MEDIUM** | Connect the HUD metric cards to dynamic API endpoints delivering validated benchmark metrics (e.g. Phase 59 audited test metrics). |
| **Simulated confusion matrix** | `model_evaluator.py` returns hardcoded numbers instead of running batch evaluation. | **LOW** | Hook `evaluate_real_hardware_dataset()` to execute batch inference across `data/real_csi_dataset/` using canonical split definitions. |

---

## 7. Confirmation of Protected Hashes

Integrity verification confirmed that zero modifications occurred to protected model weights or canonical dataset manifests:

| File | Expected MD5 Hash | Verified MD5 Hash | Status |
|---|---|---|---|
| `models/csiformer_phase13_best.pth` | `383b4d98c08f8970b0443738f170ec01` | `383b4d98c08f8970b0443738f170ec01` | **UNCHANGED** |
| `models/csiformer_phase15_adapted.pth` | `ab3d97a04d78edf75d807178772bc828` | `ab3d97a04d78edf75d807178772bc828` | **UNCHANGED** |
| `data/real_csi_dataset/dataset_manifest.json` | `a58e1280fb2c0a6649335a9a381d00c6` | `a58e1280fb2c0a6649335a9a381d00c6` | **UNCHANGED** |

---

## 8. Git Status and Working Tree State

Git status verification confirmed:
- **Tracked Files Modified:** 0
- **Tracked Files Deleted:** 0
- **Staged Changes:** 0
- **Untracked Artifacts:** Reports and scratch scripts from previous phases preserved.

---

## Conclusion & Recommendation

The CSIFormer demo is a visually sophisticated, fully responsive 3D spatial perception application. However, users and researchers must understand that:
1. The currently running demo displays **simulated kinematics and avatar states**, not live hardware activity recognition.
2. The model forward pass works technically, but the underlying checkpoints do not achieve reliable activity classification on real ESP32-S3 Wi-Fi CSI data (frequently predicting gesture classes like `Push&Pull` or `Clap`).
3. Next engineering priorities should focus on connecting the real recorded CSI dataset replay feeder to the dual-branch model and replacing hardcoded UI metrics with validated benchmark outputs.
