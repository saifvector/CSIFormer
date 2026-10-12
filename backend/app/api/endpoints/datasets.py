import os
from fastapi import APIRouter, Response, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.services.dataset_session_manager import dataset_session_manager
from app.services.dataset_recorder import dataset_recorder

router = APIRouter(prefix="/datasets", tags=["Phase 09: Real CSI Dataset Acquisition & Analytics"])

class StartSessionRequest(BaseModel):
    activity_class: str = Field("Walking", description="Standard 8 Activity Classes")
    subject_id: str = Field("Subject-01", description="Participant ID")
    room_name: str = Field("Defense Lab 101", description="Environment Name")
    room_size: str = Field("10.0m x 8.0m x 3.5m", description="Dimensions")
    router_id: str = Field("Router-TX-01", description="Wi-Fi AP Identifier")
    router_location: str = Field("X: 8.2m, Y: 1.5m, Z: 0.82m", description="AP Location")
    esp32_nodes: Optional[List[str]] = Field(default_factory=lambda: ["esp32-rx-01", "esp32-rx-02", "esp32-rx-03"])
    experiment_id: str = Field("EXP-CSI-001", description="Protocol ID")
    notes: str = Field("", description="Field Notes")
    custom_session_id: Optional[str] = None

class LegacyStartRecordingRequest(BaseModel):
    name: str = "CSI_Session"
    activity_label: str = "Walking"
    subject_id: str = "Subject-01"

# =========================================================================
# PHASE 09: ADVANCED DATASET ACQUISITION SESSION ENDPOINTS
# =========================================================================

@router.post("/session/start", response_model=Dict[str, Any])
def start_dataset_acquisition_session(req: StartSessionRequest):
    """Starts a validated, metadata-tracked CSI acquisition session."""
    return dataset_session_manager.start_session(
        activity_class=req.activity_class,
        subject_id=req.subject_id,
        room_name=req.room_name,
        room_size=req.room_size,
        router_id=req.router_id,
        router_location=req.router_location,
        esp32_nodes=req.esp32_nodes,
        experiment_id=req.experiment_id,
        notes=req.notes,
        custom_session_id=req.custom_session_id
    )

@router.post("/session/pause", response_model=Dict[str, Any])
def pause_dataset_acquisition_session():
    """Pauses an in-progress acquisition session."""
    return dataset_session_manager.pause_session()

@router.post("/session/resume", response_model=Dict[str, Any])
def resume_dataset_acquisition_session():
    """Resumes a paused acquisition session."""
    return dataset_session_manager.resume_session()

@router.post("/session/stop", response_model=Dict[str, Any])
def stop_dataset_acquisition_session():
    """Finalizes session, validates quality, and serializes CSV, JSON, and NumPy NPY tensors."""
    return dataset_session_manager.stop_session()

@router.post("/session/cancel", response_model=Dict[str, Any])
def cancel_dataset_acquisition_session():
    """Cancels and discards active recording buffer."""
    return dataset_session_manager.cancel_session()

@router.get("/session/status", response_model=Dict[str, Any])
def get_dataset_session_status():
    """Returns live session telemetry, frame counter, and real-time quality score."""
    return dataset_session_manager.get_live_status()

# =========================================================================
# PHASE 09: DATASET ANALYTICS & RESEARCH READINESS
# =========================================================================

@router.get("/dashboard", response_model=Dict[str, Any])
def get_dataset_analytics_dashboard():
    """Scans physical dataset storage on disk and returns class distributions, balance %, and storage bytes."""
    return dataset_session_manager.get_dataset_statistics()

@router.get("/readiness/report", response_model=Dict[str, Any])
def get_research_readiness_report():
    """Generates programmatic, evidence-based research readiness assessment."""
    return dataset_session_manager.generate_research_readiness_report()

# =========================================================================
# MULTI-FORMAT EXPORT & DOWNLOAD ENDPOINTS (CSV, JSON, NPY)
# =========================================================================

@router.get("/export/{session_id}/{file_format}")
def download_dataset_export(session_id: str, file_format: str):
    """
    Downloads dataset files in CSV, JSON, or NumPy NPY formats.
    """
    fmt = file_format.lower()
    if fmt not in ["csv", "json", "npy"]:
        raise HTTPException(status_code=400, detail=f"Invalid format '{file_format}'. Must be 'csv', 'json', or 'npy'.")

    # Search in sessions or class folders
    root_dir = dataset_session_manager.root_dir
    target_path = None

    # Check exports directory for CSV
    if fmt == "csv":
        exp_path = os.path.join(root_dir, "exports", f"{session_id}.csv")
        if os.path.exists(exp_path):
            target_path = exp_path

    # Check sessions directory for JSON
    if fmt == "json":
        sess_path = os.path.join(root_dir, "sessions", f"{session_id}.json")
        if os.path.exists(sess_path):
            target_path = sess_path

    # Search class subdirectories
    if not target_path:
        for sub in os.listdir(root_dir):
            sub_path = os.path.join(root_dir, sub)
            if os.path.isdir(sub_path):
                fpath = os.path.join(sub_path, f"{session_id}.{fmt}")
                if os.path.exists(fpath):
                    target_path = fpath
                    break

    if not target_path or not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"Session file '{session_id}.{fmt}' not found on disk.")

    media_types = {
        "csv": "text/csv",
        "json": "application/json",
        "npy": "application/octet-stream"
    }

    return FileResponse(
        path=target_path,
        media_type=media_types.get(fmt, "application/octet-stream"),
        filename=f"{session_id}.{fmt}"
    )

# =========================================================================
# LEGACY PHASE 02 ENDPOINTS (PRESERVED FOR BACKWARD COMPATIBILITY)
# =========================================================================

@router.get("/record/status")
def get_legacy_recording_status() -> Dict[str, Any]:
    if dataset_session_manager.is_recording:
        return dataset_session_manager.get_live_status()
    return dataset_recorder.get_recording_status()

@router.post("/record/start")
def start_legacy_recording(req: LegacyStartRecordingRequest):
    # Delegate to dataset_session_manager for Phase 09 unified storage
    dataset_recorder.start_recording(req.name, req.activity_label, req.subject_id)
    return dataset_session_manager.start_session(
        activity_class=req.activity_label,
        subject_id=req.subject_id,
        custom_session_id=req.name
    )

@router.post("/record/stop")
def stop_legacy_recording():
    dataset_recorder.stop_recording()
    return dataset_session_manager.stop_session()

@router.get("/export/{session_id}/csv")
def export_legacy_csv(session_id: str):
    return download_dataset_export(session_id, "csv")
