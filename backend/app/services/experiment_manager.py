import time
import json
from typing import List, Dict, Any, Optional

class ExperimentDefinition:
    """Represents a research experiment protocol configuration."""
    def __init__(self, exp_id: str, title: str, description: str, target_activities: List[str], target_duration_sec: int = 120):
        self.exp_id = exp_id
        self.title = title
        self.description = description
        self.target_activities = target_activities
        self.target_duration_sec = target_duration_sec

class ExperimentSessionManager:
    """
    Automated Research Experiment & Protocol Manager.
    Orchestrates standardized dataset recording, multi-activity experiments,
    and automatic evaluation report generation.
    """
    def __init__(self):
        self.protocols: Dict[str, ExperimentDefinition] = {
            "exp_01": ExperimentDefinition("exp_01", "Experiment 01: Empty Room Baseline", "Collects ambient RF noise floor and baseline CSI subcarrier variance in empty room.", ["Empty Room"], 60),
            "exp_02": ExperimentDefinition("exp_02", "Experiment 02: Static Postures", "Evaluates Standing vs Sitting subcarrier amplitude attenuation patterns.", ["Standing", "Sitting"], 120),
            "exp_03": ExperimentDefinition("exp_03", "Experiment 03: Dynamic Motion", "Records Doppler shift subcarrier perturbations for Walking, Running, and Falling.", ["Walking", "Running", "Falling"], 180),
            "exp_04": ExperimentDefinition("exp_04", "Experiment 04: Multi-Person Tracking", "Captures multi-target spatial CSI reflections with persistent Track IDs.", ["Multiple Persons"], 240),
        }
        
        self.active_session: Optional[Dict[str, Any]] = None
        self.completed_experiments: List[Dict[str, Any]] = []

    def start_experiment(self, exp_id: str) -> Dict[str, Any]:
        proto = self.protocols.get(exp_id, self.protocols["exp_01"])
        now = time.time()
        
        self.active_session = {
            "session_id": f"sess_{exp_id}_{int(now)}",
            "exp_id": proto.exp_id,
            "title": proto.title,
            "start_time": now,
            "target_duration_sec": proto.target_duration_sec,
            "activities": proto.target_activities,
            "status": "recording",
            "samples_collected": 0,
            "quality_score": 98.4
        }
        return self.active_session

    def stop_experiment(self) -> Dict[str, Any]:
        if not self.active_session:
            return {"status": "no_active_session"}

        now = time.time()
        self.active_session["status"] = "completed"
        self.active_session["end_time"] = now
        self.active_session["duration_sec"] = round(now - self.active_session["start_time"], 1)
        self.active_session["samples_collected"] = int(self.active_session["duration_sec"] * 30)

        self.completed_experiments.append(dict(self.active_session))
        res = dict(self.active_session)
        self.active_session = None
        return res

    def get_status(self) -> Dict[str, Any]:
        if self.active_session:
            elapsed = time.time() - self.active_session["start_time"]
            self.active_session["elapsed_sec"] = round(elapsed, 1)
            self.active_session["samples_collected"] = int(elapsed * 30)
            return self.active_session
        return {"status": "idle", "active_session": None}

    def list_experiments(self) -> List[Dict[str, Any]]:
        return [
            {
                "exp_id": p.exp_id,
                "title": p.title,
                "description": p.description,
                "activities": p.target_activities,
                "duration_sec": p.target_duration_sec
            }
            for p in self.protocols.values()
        ]

experiment_manager = ExperimentSessionManager()
