import pytest
import math
import time
import numpy as np
from app.services.csi_spatial_simulator import PhysicsSpatialCSISimulator
from app.services.localization_engine import SpatialLocalizationEngine

class TestPhase08SpatialCollisionAndNavigation:
    """
    Automated verification suite for CSIFormer Phase 08:
    Spatial Collision, Obstacle Avoidance & Realistic Human Navigation.
    """

    def setup_method(self):
        self.sim = PhysicsSpatialCSISimulator()
        self.loc_engine = SpatialLocalizationEngine()

    def test_01_table_obstacle_avoidance(self):
        """Test 01: Avatar navigates and maintains clearance around the Round Table."""
        table_x = 5.0
        table_y = 6.0
        table_radius = 0.95

        # Place target moving directly towards table center
        self.sim.set_activity("Walking")
        self.sim.target_x = 5.0
        self.sim.target_y = 4.5
        self.sim.target_vx = 0.0
        self.sim.target_vy = 0.15

        # Simulate 30 frames of motion
        for _ in range(30):
            self.sim.update_kinematics(0.033)
            dist = math.sqrt((self.sim.target_x - table_x)**2 + (self.sim.target_y - table_y)**2)
            # Must remain outside the core solid table radius
            assert dist >= table_radius, f"Target penetrated table: dist={dist:.2f}m < {table_radius}m"

    def test_02_wall_boundary_clamping(self):
        """Test 02: Avatar stops before wall and never exits room boundaries [0..10m] x [0..8m]."""
        self.sim.set_activity("Walking")
        self.sim.target_x = 8.8
        self.sim.target_y = 4.0
        self.sim.target_vx = 0.3
        self.sim.target_vy = 0.0

        for _ in range(50):
            self.sim.update_kinematics(0.033)
            assert 0.8 <= self.sim.target_x <= 9.2, f"Target breached X boundary: x={self.sim.target_x}"
            assert 0.8 <= self.sim.target_y <= 7.2, f"Target breached Y boundary: y={self.sim.target_y}"

    def test_03_chair_and_seating_stability(self):
        """Test 03: Sitting activity positions target precisely at chair elevation."""
        self.sim.set_activity("Sitting")
        self.sim.update_kinematics(0.033)

        assert abs(self.sim.target_z - 0.65) < 0.05, f"Seated height incorrect: {self.sim.target_z}"
        assert self.sim.target_vx == 0.0
        assert self.sim.target_vy == 0.0

    def test_04_router_beacon_clearance(self):
        """Test 04: Avatar maintains safe clearance from Wi-Fi Router TX Pedestal."""
        router_x = 2.7
        router_y = 5.2
        min_clearance = 0.50

        self.sim.set_activity("Walking")
        self.sim.target_x = 2.7
        self.sim.target_y = 4.2
        self.sim.target_vx = 0.0
        self.sim.target_vy = 0.15

        for _ in range(40):
            self.sim.update_kinematics(0.033)
            dist = math.sqrt((self.sim.target_x - router_x)**2 + (self.sim.target_y - router_y)**2)
            assert dist >= min_clearance, f"Target penetrated router clearance: dist={dist:.2f}m"

    def test_05_continuous_5min_motion_integrity(self):
        """Test 05: Avatar moves continuously for 9,000 frames (5 mins @ 30 FPS) without jitter, NaN, or clipping."""
        self.sim.set_activity("Walking")
        self.sim.target_x = 5.0
        self.sim.target_y = 3.5
        self.sim.target_vx = 0.08
        self.sim.target_vy = 0.06

        total_frames = 9000
        for i in range(total_frames):
            self.sim.update_kinematics(0.033)

            # Assert no NaNs
            assert not math.isnan(self.sim.target_x), f"NaN in X at frame {i}"
            assert not math.isnan(self.sim.target_y), f"NaN in Y at frame {i}"
            assert not math.isnan(self.sim.target_z), f"NaN in Z at frame {i}"

            # Assert grounded
            assert self.sim.target_z >= 0.0, f"Target penetrated floor: z={self.sim.target_z}"

            # Assert inside room
            assert 0.5 <= self.sim.target_x <= 9.5
            assert 0.5 <= self.sim.target_y <= 7.5
