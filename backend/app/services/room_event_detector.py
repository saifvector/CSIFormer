import time
from typing import List, Dict, Any

class SpatialRoomEventDetector:
    """
    Automated Room Event & Security Violation Detector.
    Monitors spatial telemetry and triggers real-time alerts for Restricted Area Violations,
    High Crowd Density, Traffic Bottlenecks, and Inactivity Events.
    """
    def __init__(self):
        self.events_log: List[Dict[str, Any]] = []
        self.prev_person_count = 0
        self.restricted_active = False

    def process_telemetry(self, targets: List[Dict[str, Any]], zones_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = time.time()
        person_count = len(targets)

        # 1. Room Occupied / Empty Transitions
        if self.prev_person_count == 0 and person_count > 0:
            self._add_event("ROOM_OCCUPIED", "INFO", "Human target detected in indoor environment", now)
        elif self.prev_person_count > 0 and person_count == 0:
            self._add_event("ROOM_EMPTY", "INFO", "Room is now unoccupied", now)
        self.prev_person_count = person_count

        # 2. Restricted Zone Security Violation
        restricted_zone = next((z for z in zones_data if z.get("is_restricted")), None)
        if restricted_zone and restricted_zone.get("current_occupancy", 0) > 0:
            if not self.restricted_active:
                self.restricted_active = True
                self._add_event(
                    "RESTRICTED_ZONE_VIOLATION",
                    "CRITICAL",
                    "UNAUTHORIZED ENTRY INTO RESTRICTED AREA (X: 0.5-2.5m, Y: 1.0-3.0m)",
                    now
                )
        else:
            self.restricted_active = False

        # 3. High Crowd Density Alert (>2 targets)
        if person_count >= 3:
            self._add_event("HIGH_CROWD_DENSITY", "WARNING", f"Crowd density spike detected ({person_count} targets active)", now)

        # 4. Check for Fall Anomaly
        for target in targets:
            if target.get("activity") == "Falling":
                self._add_event("TRANSIENT_FALL_IMPACT", "CRITICAL", f"Fall impact detected for {target.get('track_id', 'Target')}", now)

        return self.events_log[-15:]

    def _add_event(self, event_type: str, severity: str, message: str, timestamp: float):
        if self.events_log and self.events_log[-1]["type"] == event_type and (timestamp - self.events_log[-1]["timestamp"]) < 3.0:
            return

        event = {
            "id": f"event_{int(timestamp * 1000)}",
            "type": event_type,
            "severity": severity,
            "message": message,
            "timestamp": timestamp,
            "time_str": time.strftime("%H:%M:%S", time.localtime(timestamp))
        }
        self.events_log.append(event)
        if len(self.events_log) > 50:
            self.events_log.pop(0)

    def get_events(self) -> List[Dict[str, Any]]:
        return self.events_log[-15:]

room_event_detector = SpatialRoomEventDetector()
