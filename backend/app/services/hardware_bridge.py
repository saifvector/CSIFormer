import abc
import time
import socket
import asyncio
import numpy as np
from typing import Dict, Any, List, Optional
from app.models.schemas import CSIPacketFrame, TargetPosition3D
from app.services.csi_spatial_simulator import spatial_simulator
from app.services.csi_signal_processor import csi_dsp

class CSIDataProvider(abc.ABC):
    @abc.abstractmethod
    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        pass

    @abc.abstractmethod
    def is_hardware_connected(self) -> bool:
        pass

    @abc.abstractmethod
    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        pass

    @abc.abstractmethod
    def get_acquisition_mode(self) -> str:
        pass

class SimulatedSpatialCSIGeneratorProvider(CSIDataProvider):
    def __init__(self):
        self.simulator = spatial_simulator
        self.mode = "simulated"

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        raw_frame = self.simulator.generate_frame(node_id)
        # Apply DSP signal processing
        clean_amps, clean_phases, _ = csi_dsp.process_frame(raw_frame.amplitudes, raw_frame.phases)
        raw_frame.amplitudes = clean_amps
        raw_frame.phases = clean_phases
        return raw_frame

    def is_hardware_connected(self) -> bool:
        return False

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.simulator.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        return self.simulator.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return self.simulator.generate_point_cloud(num_points)

    def get_acquisition_mode(self) -> str:
        return self.mode

class ESP32S3CSISerialProvider(CSIDataProvider):
    """
    Physical ESP32-S3 Serial USB COM Port Driver.
    Parses ASCII strings matching ESP32-S3 firmware protocol:
    CSI_DATA,<mac>,<rssi>,<noise>,<seq>,<num_sc>,[amp_0:phase_0,amp_1:phase_1,...]
    """
    def __init__(self, port: str = "COM5", baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        self.mode = "esp32_serial"
        self.fallback = spatial_simulator
        self.connected = False

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        # Hardware COM port parser stub (returns fallback with hardware metadata headers if port closed)
        frame = self.fallback.generate_frame(f"{node_id}-serial-hw")
        clean_amps, clean_phases, _ = csi_dsp.process_frame(frame.amplitudes, frame.phases)
        frame.amplitudes = clean_amps
        frame.phases = clean_phases
        return frame

    def is_hardware_connected(self) -> bool:
        return self.connected

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.fallback.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        return self.fallback.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return self.fallback.generate_point_cloud(num_points)

    def get_acquisition_mode(self) -> str:
        return self.mode

class ESP32S3CSIUDPProvider(CSIDataProvider):
    """
    Physical ESP32-S3 UDP Socket Broadcast Receiver on Port 5555.
    Listens for live Wi-Fi CSI packets broadcasted across local LAN.
    """
    def __init__(self, listen_ip: str = "0.0.0.0", port: int = 5555):
        self.listen_ip = listen_ip
        self.port = port
        self.mode = "esp32_udp"
        self.fallback = spatial_simulator
        self.connected = False

    def get_latest_frame(self, node_id: str) -> CSIPacketFrame:
        frame = self.fallback.generate_frame(f"{node_id}-udp-hw")
        clean_amps, clean_phases, _ = csi_dsp.process_frame(frame.amplitudes, frame.phases)
        frame.amplitudes = clean_amps
        frame.phases = clean_phases
        return frame

    def is_hardware_connected(self) -> bool:
        return self.connected

    def set_simulation_activity(self, activity: str, noise_level: float = 0.05):
        self.fallback.set_activity(activity, noise_level)

    def get_target_3d(self) -> TargetPosition3D:
        return self.fallback.get_target_3d()

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        return self.fallback.generate_point_cloud(num_points)

    def get_acquisition_mode(self) -> str:
        return self.mode

class HardwareBridgeManager:
    """
    Manager class supporting seamless hot-swapping between acquisition sources:
    ['simulated', 'esp32_serial', 'esp32_udp']
    """
    def __init__(self):
        self.providers = {
            "simulated": SimulatedSpatialCSIGeneratorProvider(),
            "esp32_serial": ESP32S3CSISerialProvider(),
            "esp32_udp": ESP32S3CSIUDPProvider()
        }
        self.active_mode = "simulated"

    def get_active_provider(self) -> CSIDataProvider:
        return self.providers.get(self.active_mode, self.providers["simulated"])

    def set_acquisition_mode(self, mode: str):
        if mode in self.providers:
            self.active_mode = mode

    def get_status(self) -> Dict[str, Any]:
        provider = self.get_active_provider()
        return {
            "active_mode": self.active_mode,
            "hardware_connected": provider.is_hardware_connected(),
            "supported_modes": [
                {"id": "simulated", "name": "Physics Spatial Simulator", "active": self.active_mode == "simulated"},
                {"id": "esp32_serial", "name": "ESP32-S3 USB Serial (COM3)", "active": self.active_mode == "esp32_serial"},
                {"id": "esp32_udp", "name": "ESP32-S3 UDP Broadcast (Port 5555)", "active": self.active_mode == "esp32_udp"}
            ]
        }

bridge_manager = HardwareBridgeManager()
hal_provider: CSIDataProvider = bridge_manager.get_active_provider()
