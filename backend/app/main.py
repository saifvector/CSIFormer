import asyncio
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.websockets.manager import ws_manager
from app.services.hardware_bridge import bridge_manager
from app.services.esp32_hardware_manager import esp32_hardware_manager
from app.services.experiment_manager import experiment_manager
from app.services.model_evaluator import model_evaluator
from app.services.activity_classifier import ai_pipeline
from app.services.localization_engine import localization_engine
from app.services.multiperson_tracker import multiperson_tracker
from app.services.digital_twin_service import digital_twin_service
from app.services.room_event_detector import room_event_detector
from app.services.room_insight_engine import room_insight_engine
from app.services.room_memory_service import room_memory_service
from app.services.dataset_recorder import dataset_recorder
from app.services.dataset_session_manager import dataset_session_manager
from app.api.endpoints.system import increment_packets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("csiformer.spatial")

async def csi_spatial_stream_loop():
    logger.info("CSI 3D Spatial Stream Loop Started (30 Hz)")
    node_ids = ["esp32-rx-01", "esp32-rx-02", "esp32-rx-03"]
    
    while True:
        try:
            active_hal = bridge_manager.get_active_provider()
            is_real = active_hal.is_real_measurement()
            raw_target = active_hal.get_target_3d()
            
            if is_real:
                # REAL MEASUREMENT: do not run simulated localization, multiperson, digital twin, events
                target_3d = raw_target  # Already truthful (0,0,0 / UNAVAILABLE)
                current_target_act = "UNKNOWN"
                multi_telemetry = {"tracks": [], "available": False, "status": "TRACKING UNAVAILABLE (Single RX Node)"}
                dt_status = {"available": False, "zones": [], "status": "DIGITAL TWIN UNAVAILABLE"}
                events_list = []
                spatial_insights = {"space_utilization_score_pct": 0, "observations": ["Real measurement mode — spatial analytics require multi-node deployment"]}
                point_cloud_3d = []
            else:
                # SIMULATION: run all synthetic engines
                target_3d = localization_engine.update_raw_position(raw_target.x, raw_target.y, raw_target.z)

                if hasattr(active_hal, "simulator"):
                    current_target_act = active_hal.simulator.current_activity
                elif hasattr(active_hal, "fallback"):
                    current_target_act = active_hal.fallback.current_activity
                else:
                    current_target_act = "Walking"

                # Multi-person target generation
                if current_target_act == "Multiple Persons":
                    multi_raw_targets = [
                        (raw_target.x, raw_target.y, raw_target.z),
                        (min(9.5, max(0.5, raw_target.x + 2.2)), min(7.5, max(0.5, raw_target.y - 1.8)), 1.0),
                        (min(9.5, max(0.5, raw_target.x - 2.0)), min(7.5, max(0.5, raw_target.y + 1.5)), 1.0)
                    ]
                else:
                    multi_raw_targets = [(raw_target.x, raw_target.y, raw_target.z)]

                multi_telemetry = multiperson_tracker.update_multi_targets(multi_raw_targets, current_simulated_act=current_target_act)
                active_tracks = multi_telemetry.get("tracks", [])
                dt_status = digital_twin_service.update_digital_twin(active_tracks)
                events_list = room_event_detector.process_telemetry(active_tracks, dt_status["zones"])
                spatial_insights = room_insight_engine.generate_insights(dt_status["zones"], len(active_tracks))
                room_memory_service.record_snapshot(active_tracks, dt_status["zones"], spatial_insights["space_utilization_score_pct"])
                point_cloud_3d = active_hal.generate_point_cloud(250)

            # ESP32 Hardware Status & Live Subcarrier Inspector
            hw_status = active_hal.get_hardware_status()
            subcarriers_inspector = active_hal.get_subcarrier_inspector("esp32-rx-01")
            exp_status = experiment_manager.get_status()

            frames_payload = {}
            for node_id in node_ids:
                frame = active_hal.get_latest_frame(node_id)
                if not is_real:
                    ai_pipeline.add_csi_frame(frame.amplitudes)
                    dataset_recorder.record_frame(
                        frame,
                        target_x=target_3d.x,
                        target_y=target_3d.y,
                        target_z=target_3d.z,
                        zone=target_3d.zone,
                        speed=localization_engine.speed_ms
                    )
                    dataset_session_manager.record_frame(
                        frame,
                        target_x=target_3d.x,
                        target_y=target_3d.y,
                        target_z=target_3d.z,
                        zone=target_3d.zone,
                        speed_ms=localization_engine.speed_ms
                    )
                increment_packets(1)
                frames_payload[node_id] = frame.model_dump()

            # CSIFormerNet Activity Inference: Real Model on Real Data or Simulated Fallback
            real_model_pred = active_hal.get_model_prediction()
            if real_model_pred is not None:
                if real_model_pred.get("status") == "success":
                    activity_pred_dict = {
                        "timestamp": time.time(),
                        "activity": real_model_pred["label"],
                        "confidence": real_model_pred["confidence"],
                        "presence": real_model_pred["predicted_class"] != 0,
                        "probabilities": {item["label"]: item["prob"] for item in real_model_pred.get("top3", [])},
                        "anomaly_detected": real_model_pred.get("is_fall", False),
                        "anomaly_type": "UNVALIDATED_FALL_TRIGGER" if real_model_pred.get("is_fall") else None,
                        "is_unvalidated": True,
                        "latency_ms": real_model_pred.get("latency_ms", 0.0),
                        "gate_weights": {
                            "raw": real_model_pred.get("raw_gate_weight", 0.5),
                            "doppler": real_model_pred.get("doppler_gate_weight", 0.5)
                        }
                    }
                elif real_model_pred.get("status") == "buffering":
                    activity_pred_dict = {
                        "timestamp": time.time(),
                        "activity": f"Buffering ({real_model_pred['buffered_frames']}/{real_model_pred['required_frames']})",
                        "confidence": 0.0,
                        "presence": False,
                        "probabilities": {},
                        "anomaly_detected": False,
                        "anomaly_type": None,
                        "is_unvalidated": True,
                        "buffering": True,
                        "buffered_frames": real_model_pred["buffered_frames"],
                        "required_frames": real_model_pred["required_frames"],
                        "latency_ms": 0.0
                    }
                else:
                    activity_pred_dict = {
                        "timestamp": time.time(),
                        "activity": "Pipeline Incompatible",
                        "confidence": 0.0,
                        "presence": False,
                        "probabilities": {},
                        "anomaly_detected": False,
                        "anomaly_type": None,
                        "is_unvalidated": True,
                        "error": real_model_pred.get("error", "Unknown"),
                        "latency_ms": 0.0
                    }
            else:
                sim_pred = ai_pipeline.predict_activity(current_target_act)
                activity_pred_dict = sim_pred.model_dump()
                activity_pred_dict["is_unvalidated"] = False
                activity_pred_dict["latency_ms"] = 8.2

            nodes = [n.model_dump() for n in localization_engine.get_nodes()]
            dataset_live_status = dataset_session_manager.get_live_status()

            # Build payload with truthful representation based on data source
            target_payload = target_3d.model_dump() if hasattr(target_3d, 'model_dump') else {
                "x": target_3d.x, "y": target_3d.y, "z": target_3d.z,
                "confidence": target_3d.confidence, "zone": target_3d.zone,
                "vx": target_3d.vx, "vy": target_3d.vy
            }
            if is_real:
                target_payload["available"] = False
                target_payload["status"] = "LOCALIZATION UNAVAILABLE (Single RX Node)"

            tracking_payload = localization_engine.get_tracking_telemetry() if not is_real else {
                "available": False,
                "status": "TRACKING UNAVAILABLE (Single RX Node)",
                "speed_ms": 0.0,
                "total_distance_m": 0.0,
                "stability_pct": 0.0
            }

            payload = {
                "type": "csi_spatial_telemetry_frame",
                "timestamp": time.time(),
                "data_source": active_hal.get_acquisition_source_label(),
                "is_real_measurement": is_real,
                "target": target_payload,
                "tracking": tracking_payload,
                "multiperson": multi_telemetry,
                "digital_twin": dt_status,
                "events": events_list,
                "insights": spatial_insights,
                "hardware": hw_status,
                "subcarriers": subcarriers_inspector,
                "experiment": exp_status,
                "dataset_session": dataset_live_status,
                "point_cloud": point_cloud_3d,
                "frames": frames_payload,
                "activity": activity_pred_dict,
                "nodes": nodes
            }

            await ws_manager.broadcast(payload)
            await asyncio.sleep(0.033)
        except asyncio.CancelledError:
            logger.info("CSI Spatial Stream Loop Cancelled")
            break
        except Exception as e:
            logger.error(f"Error in spatial stream loop: {e}")
            await asyncio.sleep(0.1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(csi_spatial_stream_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
    }

@app.websocket("/api/v1/ws/csi")
async def websocket_csi_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.send_personal_message({"type": "pong", "recv": data}, websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
