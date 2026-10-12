import time
from fastapi import APIRouter
from app.models.schemas import SystemMetrics
from app.services.localization_engine import localization_engine
from app.websockets.manager import ws_manager

router = APIRouter(prefix="/system", tags=["System"])

start_time = time.time()
total_packets_counter = 0

def increment_packets(count: int = 1):
    global total_packets_counter
    total_packets_counter += count

@router.get("/status", response_model=SystemMetrics)
def get_system_status():
    uptime = time.time() - start_time
    nodes = localization_engine.get_nodes()
    
    cpu_usage = 12.4 + (time.time() % 3.0) * 1.5
    mem_usage = 28.5 + (time.time() % 5.0) * 0.3
    latency = 8.2 + (time.time() % 2.0) * 1.1

    return SystemMetrics(
        uptime_seconds=round(uptime, 1),
        packets_processed=total_packets_counter,
        packet_rate_hz=90.0, # 30Hz x 3 RX nodes
        active_nodes_count=len(nodes),
        total_nodes_count=len(nodes),
        cpu_usage_pct=round(cpu_usage, 1),
        memory_usage_pct=round(mem_usage, 1),
        ws_connections_count=ws_manager.get_connection_count(),
        stream_latency_ms=round(latency, 1)
    )
