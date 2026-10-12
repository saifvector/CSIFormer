from fastapi import APIRouter, Query
from typing import Dict, Any, List
from app.services.digital_twin_service import digital_twin_service
from app.services.room_event_detector import room_event_detector
from app.services.room_insight_engine import room_insight_engine
from app.services.room_memory_service import room_memory_service

router = APIRouter(prefix="/spatial", tags=["Semantic Spatial Intelligence & Digital Twin Engine"])

@router.get("/digital_twin", response_model=Dict[str, Any])
def get_digital_twin_status():
    return digital_twin_service.update_digital_twin([])

@router.get("/insights", response_model=Dict[str, Any])
def get_spatial_insights():
    dt_status = digital_twin_service.update_digital_twin([])
    return room_insight_engine.generate_insights(dt_status["zones"], dt_status["active_target_count"])

@router.get("/events", response_model=List[Dict[str, Any]])
def get_room_events():
    return room_event_detector.get_events()

@router.get("/memory/history", response_model=Dict[str, Any])
def get_historical_spatial_memory(offset_seconds: int = Query(0, ge=0, le=1800)):
    return room_memory_service.get_historical_snapshot(offset_seconds)
