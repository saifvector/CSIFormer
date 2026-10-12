import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.digital_twin_service import digital_twin_service
from app.services.room_event_detector import room_event_detector
from app.services.room_insight_engine import room_insight_engine
from app.services.room_memory_service import room_memory_service

def test_digital_twin_service():
    print("Testing DigitalTwinService 6 Semantic Room Zones...")
    active_targets = [
        {"track_id": "Track-001", "x": 1.2, "y": 2.0, "z": 1.0}, # Inside Restricted Area & Entrance Zone
        {"track_id": "Track-002", "x": 8.0, "y": 2.0, "z": 1.0}  # Inside Workspace Area
    ]
    
    status = digital_twin_service.update_digital_twin(active_targets)
    assert status["status"] == "synchronized"
    assert len(status["zones"]) == 6
    
    workspace = next(z for z in status["zones"] if z["name"] == "Workspace Area")
    assert workspace["current_occupancy"] == 1
    assert workspace["entry_count"] >= 1
    print("PASSED: DigitalTwinService 6 Semantic Room Zones test!")

def test_room_event_detector():
    print("Testing SpatialRoomEventDetector & Restricted Zone Violations...")
    active_targets = [{"track_id": "Track-001", "x": 1.2, "y": 2.0, "z": 1.0, "activity": "Walking"}]
    dt_status = digital_twin_service.update_digital_twin(active_targets)
    
    events = room_event_detector.process_telemetry(active_targets, dt_status["zones"])
    assert len(events) > 0
    event_types = [e["type"] for e in events]
    assert "RESTRICTED_ZONE_VIOLATION" in event_types, f"Expected RESTRICTED_ZONE_VIOLATION in {event_types}"
    print("PASSED: SpatialRoomEventDetector violation alert test!")

def test_room_insight_engine():
    print("Testing SpatialRoomInsightEngine Utilization Score & AI Observations...")
    dt_status = digital_twin_service.update_digital_twin([{"track_id": "Track-001", "x": 8.0, "y": 2.0, "z": 1.0}])
    insights = room_insight_engine.generate_insights(dt_status["zones"], 1)
    
    assert "space_utilization_score_pct" in insights
    assert insights["space_utilization_score_pct"] > 0
    assert len(insights["observations"]) > 0
    print("PASSED: SpatialRoomInsightEngine test!")

def test_room_memory_service():
    print("Testing SpatialRoomMemoryService 30-Minute Memory Store & Timeline Replay...")
    room_memory_service.record_snapshot(
        targets=[{"track_id": "Track-001", "x": 4.18, "y": 2.50, "z": 1.10}],
        zones_data=[],
        space_score=85.0
    )
    
    snapshot = room_memory_service.get_historical_snapshot(offset_seconds=0)
    assert snapshot["target_count"] == 1
    assert snapshot["space_utilization_score"] == 85.0
    print("PASSED: SpatialRoomMemoryService timeline replay test!")

if __name__ == "__main__":
    test_digital_twin_service()
    test_room_event_detector()
    test_room_insight_engine()
    test_room_memory_service()
    print("ALL PHASE 06 DIGITAL TWIN & SEMANTIC INTELLIGENCE TESTS PASSED!")
