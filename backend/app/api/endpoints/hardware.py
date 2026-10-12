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
