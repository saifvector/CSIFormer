import numpy as np
import time
import math
from typing import List, Tuple, Dict, Any
from app.models.schemas import CSIPacketFrame, CSIPoint3D, TargetPosition3D

class PhysicsSpatialCSISimulator:
    """
    3D Physics-Grounded Spatial CSI & Point Cloud Telemetry Simulator.
    Calculates 3D spatial target trajectory (X,Y,Z), 250+ CSI scatter point cloud particles,
    and 64-subcarrier OFDM amplitude/phase profiles across wireless sensing nodes.
    """
    def __init__(self, subcarrier_count: int = 64, sampling_rate_hz: float = 30.0):
        self.num_subcarriers = subcarrier_count
        self.sampling_rate = sampling_rate_hz
        self.current_activity = "Walking"
        self.sequence_counter = 0
        self.start_time = time.time()
        self.noise_std = 0.05
        
        # 3D Room Dimensions
        self.room_w = 10.0
        self.room_l = 8.0
        self.room_h = 3.5
        
        # Target position & kinematics state
        self.target_x = 4.5
        self.target_y = 3.5
        self.target_z = 1.0 # Torso height
        self.target_vx = 0.08
        self.target_vy = 0.05
        self.target_vz = 0.0
        
        # Static baseline OFDM channel transfer function H(f)
        sc_indices = np.arange(self.num_subcarriers) - (self.num_subcarriers // 2)
        base_h = 25.0 + 15.0 * np.cos(sc_indices * 0.12) - 5.0 * np.exp(-0.05 * sc_indices**2)
        base_h[self.num_subcarriers // 2] = 2.0
        self.base_amplitude = np.clip(base_h, 3.0, 50.0)
        self.base_phase = np.linspace(-np.pi, np.pi, self.num_subcarriers)

    def set_activity(self, activity: str, noise_level: float = 0.05):
        valid = ["Empty", "Walking", "Sitting", "Standing", "Falling"]
        if activity in valid:
            self.current_activity = activity
            self.noise_std = noise_level
            if activity == "Sitting":
                # Move target precisely to chair location in room coords (3.2m, 6.3m)
                self.target_x = 3.2
                self.target_y = 6.3
                self.target_z = 0.65
            elif activity == "Standing":
                self.target_x = 6.2
                self.target_y = 3.5
                self.target_z = 1.1

    def update_kinematics(self, dt: float):
        """Updates 3D target coordinates (X, Y, Z) and velocities with obstacle avoidance physics."""
        if self.current_activity == "Walking":
            # Potential obstacles in room coords [x, y, radius/half_size]
            obstacles = [
                # Meeting Table at [5.0, 6.0] radius 0.95m
                {"x": 5.0, "y": 6.0, "r": 1.05},
                # Desk at [3.2, 5.5] radius 0.95m
                {"x": 3.2, "y": 5.5, "r": 0.95},
                # Router at [2.7, 5.2] radius 0.55m
                {"x": 2.7, "y": 5.2, "r": 0.55},
                # ESP32 Nodes clearance
                {"x": 0.1, "y": 4.0, "r": 0.50},
                {"x": 9.9, "y": 5.5, "r": 0.50},
                {"x": 5.0, "y": 0.1, "r": 0.50},
                # Restricted Zone at [1.5, 2.0]
                {"x": 1.5, "y": 2.0, "r": 1.25},
            ]

            # Obstacle repulsive steering
            for obs in obstacles:
                dx = self.target_x - obs["x"]
                dy = self.target_y - obs["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < obs["r"] + 0.5 and dist > 0.01:
                    nx = dx / dist
                    ny = dy / dist
                    # Deflect velocity away from obstacle
                    self.target_vx = nx * 0.10 + ny * 0.06
                    self.target_vy = ny * 0.10 - nx * 0.06
                    # Push position outside obstacle
                    self.target_x = obs["x"] + nx * (obs["r"] + 0.1)
                    self.target_y = obs["y"] + ny * (obs["r"] + 0.1)

            self.target_x += self.target_vx
            self.target_y += self.target_vy
            self.target_z = 1.0 + 0.05 * math.sin(time.time() * 7.5) # Vertical gait bounce
            
            # Bounce off room boundaries [0.8m .. 9.2m] x [0.8m .. 7.2m]
            if self.target_x < 1.0:
                self.target_x = 1.0
                self.target_vx = abs(self.target_vx)
            elif self.target_x > 9.0:
                self.target_x = 9.0
                self.target_vx = -abs(self.target_vx)

            if self.target_y < 1.0:
                self.target_y = 1.0
                self.target_vy = abs(self.target_vy)
            elif self.target_y > 7.0:
                self.target_y = 7.0
                self.target_vy = -abs(self.target_vy)

        elif self.current_activity == "Sitting":
            self.target_x = 3.2
            self.target_y = 6.3
            self.target_z = 0.65 # Chair height
            self.target_vx = 0.0
            self.target_vy = 0.0

        elif self.current_activity == "Standing":
            self.target_z = 1.1
            self.target_vx = 0.0
            self.target_vy = 0.0

        elif self.current_activity == "Falling":
            # Rapid drop to floor level
            t = (time.time() - self.start_time) % 4.0
            if t < 0.6:
                fall_progress = t / 0.6
                self.target_z = 1.1 * (1.0 - fall_progress) + 0.15
            else:
                self.target_z = 0.15 # Prone on floor
            self.target_vx = 0.0
            self.target_vy = 0.0

        elif self.current_activity == "Empty":
            self.target_x = 5.0
            self.target_y = 4.0
            self.target_z = -10.0 # Hidden when empty

    def generate_point_cloud(self, num_points: int = 250) -> List[Dict[str, float]]:
        """
        Generates synthetic 3D CSI scatter point cloud particles representing RF energy reflection
        points on the human body with Doppler energy values.
        """
        if self.current_activity == "Empty":
            return []

        points = []
        t = time.time()
        
        # Human height body dimensions (head, torso, limbs)
        body_h = 1.7
        if self.current_activity == "Sitting":
            body_h = 1.2
        elif self.current_activity == "Falling" and self.target_z < 0.3:
            body_h = 0.3 # Horizontal prone body

        for i in range(num_points):
            # Sample point inside bounding ellipsoid of human body
            theta = np.random.uniform(0, 2 * np.pi)
            phi = np.random.uniform(0, np.pi)
            
            # Radial dispersion
            rx = np.random.normal(0, 0.28)
            ry = np.random.normal(0, 0.28)
            rz = np.random.uniform(-body_h / 2, body_h / 2)
            
            px = round(float(self.target_x + rx), 3)
            py = round(float(self.target_y + ry), 3)
            pz = round(float(max(0.1, self.target_z + rz)), 3)
            
            intensity = float(np.random.uniform(0.4, 1.0))
            
            # Activity doppler shift calculation
            if self.current_activity == "Walking":
                doppler = float(np.sin(t * 5.0 + i) * 3.5 + np.random.normal(0, 0.5))
            elif self.current_activity == "Falling" and self.target_z > 0.3:
                doppler = float(np.random.uniform(-8.0, -4.0)) # Rapid downward drop Doppler
            else:
                doppler = float(np.random.normal(0, 0.3))
                
            points.append({
                "x": px,
                "y": py,
                "z": pz,
                "intensity": round(intensity, 2),
                "doppler": round(doppler, 2)
            })

        return points

    def generate_frame(self, node_id: str) -> CSIPacketFrame:
        self.sequence_counter += 1
        t = time.time() - self.start_time
        num_sc = self.num_subcarriers
        sc_indices = np.arange(num_sc)
        node_seed = hash(node_id) % 100 / 100.0

        if self.current_activity == "Empty":
            amp_delta = np.random.normal(0, self.noise_std * 2.0, num_sc)
            phase_delta = np.random.normal(0, 0.02, num_sc)
            rssi = -48.0 + node_seed
            snr = 38.0
        elif self.current_activity == "Walking":
            gait_wave = np.sin(2 * np.pi * 1.8 * t + node_seed * np.pi)
            amp_delta = 8.5 * gait_wave * np.sin(sc_indices * 0.15) + np.random.normal(0, self.noise_std * 4.0, num_sc)
            phase_delta = 0.4 * np.sin(2 * np.pi * 1.8 * t + sc_indices * 0.1)
            rssi = -54.0 + 3.5 * gait_wave
            snr = 28.0 + 2.0 * gait_wave
        else:
            amp_delta = np.random.normal(0, self.noise_std * 2.5, num_sc)
            phase_delta = np.random.normal(0, 0.04, num_sc)
            rssi = -51.0
            snr = 34.0

        amplitudes = np.clip(self.base_amplitude + amp_delta, 0.1, 80.0)
        phases = (self.base_phase + phase_delta) % (2 * np.pi) - np.pi
        noise_floor = rssi - snr

        return CSIPacketFrame(
            node_id=node_id,
            sequence=self.sequence_counter,
            timestamp=time.time(),
            subcarrier_count=num_sc,
            amplitudes=[round(float(a), 3) for a in amplitudes],
            phases=[round(float(p), 4) for p in phases],
            rssi=round(float(rssi), 2),
            noise_floor=round(float(noise_floor), 2),
            snr=round(float(snr), 2)
        )

    def get_target_3d(self) -> TargetPosition3D:
        self.update_kinematics(0.033) # ~30 FPS step
        
        if self.target_x < 3.0:
            zone = "Zone A (Entrance / Doorway)"
        elif self.target_x > 7.0:
            zone = "Zone B (Workstation Desk)"
        elif self.target_y > 5.5:
            zone = "Zone C (Relaxation Bed / Prone)"
        else:
            zone = "Center Active Sensing Area"

        return TargetPosition3D(
            x=round(float(self.target_x), 2),
            y=round(float(self.target_y), 2),
            z=round(float(self.target_z), 2),
            vx=round(float(self.target_vx), 3),
            vy=round(float(self.target_vy), 3),
            vz=round(float(self.target_vz), 3),
            confidence=0.96 if self.current_activity != "Empty" else 0.99,
            zone=zone,
            timestamp=time.time()
        )

spatial_simulator = PhysicsSpatialCSISimulator()
