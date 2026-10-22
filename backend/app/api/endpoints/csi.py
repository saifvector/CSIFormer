from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from app.models.schemas import SetActivitySimulationRequest
from app.services.hardware_bridge import bridge_manager, hal_provider
from app.services.trainer import ai_trainer

router = APIRouter(prefix="/csi", tags=["CSI Spatial Engine & Hardware"])

class SetHardwareModeRequest(BaseModel):
    mode: str # 'simulated', 'esp32_serial', 'esp32_udp'

class TrainModelRequest(BaseModel):
    epochs: int = 15
    batch_size: int = 32

@router.post("/simulation/activity")
def set_simulated_activity(req: SetActivitySimulationRequest):
    provider = bridge_manager.get_active_provider()
    provider.set_simulation_activity(req.activity, req.noise_level or 0.05)
    return {
        "status": "success",
        "active_activity": req.activity,
        "noise_level": req.noise_level
    }

@router.get("/hardware/status")
def get_hardware_status() -> Dict[str, Any]:
    return bridge_manager.get_status()

@router.post("/hardware/source")
def set_hardware_source(req: SetHardwareModeRequest):
    bridge_manager.set_acquisition_mode(req.mode)
    return bridge_manager.get_status()

@router.get("/model/status")
def get_model_status() -> Dict[str, Any]:
    return ai_trainer.last_training_metrics

@router.post("/model/train")
def train_csiformer_model(req: TrainModelRequest):
    metrics = ai_trainer.train(epochs=req.epochs, batch_size=req.batch_size)
    return metrics
