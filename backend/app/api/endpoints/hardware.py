from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List
from app.services.esp32_hardware_manager import esp32_hardware_manager
from app.services.experiment_manager import experiment_manager
from app.services.model_evaluator import model_evaluator

router = APIRouter(prefix="/hardware", tags=["ESP32-S3 Hardware Integration & CSI Acquisition System"])

@router.get("/devices", response_model=Dict[str, Any])
def get_esp32_hardware_status():
    return esp32_hardware_manager.get_hardware_status()

@router.get("/subcarriers", response_model=Dict[str, Any])
def get_live_subcarrier_inspector(device_id: str = Query("esp32-rx-01")):
    return esp32_hardware_manager.get_live_subcarriers(device_id)

@router.get("/ports", response_model=List[Dict[str, str]])
def scan_serial_com_ports():
    return esp32_hardware_manager.scan_available_ports()

@router.get("/experiments", response_model=List[Dict[str, Any]])
def list_research_experiments():
    return experiment_manager.list_experiments()

@router.post("/experiments/start", response_model=Dict[str, Any])
def start_experiment_workflow(exp_id: str = Query("exp_01")):
    return experiment_manager.start_experiment(exp_id)

@router.post("/experiments/stop", response_model=Dict[str, Any])
def stop_experiment_workflow():
    return experiment_manager.stop_experiment()

@router.get("/evaluation/report", response_model=Dict[str, Any])
def get_real_hardware_evaluation_report():
    return model_evaluator.evaluate_real_hardware_dataset()

# =============================================================================
# Phase 14: Real-Time Hardware CSI Acquisition & Live Prediction Endpoints
# =============================================================================
from app.services.live_pipeline_service import live_pipeline_service

@router.get("/collector/status", response_model=Dict[str, Any])
def get_real_csi_collector_status():
    """Returns connection, packet rate, loss percentage, and buffer status of the live ESP32-S3 collector."""
    return live_pipeline_service.get_status()

@router.post("/collector/start", response_model=Dict[str, Any])
def start_real_csi_collector(port: str = Query(None), baud_rate: int = Query(115200)):
    """Starts live USB-UART serial CSI streaming on the specified COM port (or auto-detected port)."""
    return live_pipeline_service.start_collector(port=port, baud_rate=baud_rate)

@router.post("/collector/stop", response_model=Dict[str, Any])
def stop_real_csi_collector():
    """Stops the active serial capture and disconnects the COM port."""
    return live_pipeline_service.stop_collector()

@router.get("/collector/prediction", response_model=Dict[str, Any])
def get_live_stream_prediction():
    """
    Executes live forward pass through the dual-branch CSIFormer model using the latest
    [50, 56] sliding window captured from the physical ESP32-S3 hardware.
    """
    return live_pipeline_service.predict_latest_window()

@router.get("/collector/window", response_model=Dict[str, Any])
def get_live_stream_window():
    """Returns the latest buffered [50, 56] CSI subcarrier matrix for frontend visualization."""
    return live_pipeline_service.get_latest_window()

