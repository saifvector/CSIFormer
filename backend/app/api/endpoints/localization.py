from fastapi import APIRouter
from typing import List, Dict, Any
from app.models.schemas import NodeInfo, TargetPosition3D
from app.services.localization_engine import localization_engine

router = APIRouter(prefix="/localization", tags=["Spatial Localization & Tracking Engine"])

@router.get("/nodes", response_model=List[NodeInfo])
def get_sensor_nodes():
    return localization_engine.get_nodes()

@router.get("/tracking", response_model=Dict[str, Any])
def get_realtime_tracking():
    return localization_engine.get_tracking_telemetry()

@router.get("/heatmap", response_model=List[List[float]])
def get_occupancy_heatmap():
    return localization_engine.get_occupancy_heatmap()
