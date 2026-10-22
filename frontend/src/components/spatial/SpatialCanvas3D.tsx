import React, { useRef, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type {
  SpatialTelemetryFrame,
  SpatialVisibilitySettings
} from '../../types/csi';

import { DigitalTwinRoom3D } from './DigitalTwinRoom3D';
import { SensorNodes3D } from './SensorNodes3D';
import { CSIRayBeams3D } from './CSIRayBeams3D';
import { HumanAvatar3D } from './HumanAvatar3D';
import { MultiHumanAvatar3D } from './MultiHumanAvatar3D';
import { CSIPointCloud3D } from './CSIPointCloud3D';
import { TrajectoryRibbon3D } from './TrajectoryRibbon3D';
import { GroundHeatmap3D } from './GroundHeatmap3D';
import { NavMeshVisualizer3D } from './NavMeshVisualizer3D';

interface SpatialCanvas3DProps {
  telemetry: SpatialTelemetryFrame | null;
  visibility: SpatialVisibilitySettings;
  cameraPreset: 'isometric' | 'topdown' | 'sensoreye';
}

export const SpatialCanvas3D: React.FC<SpatialCanvas3DProps> = ({
  telemetry,
  visibility,
  cameraPreset
}) => {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);

  const multiTracks = (telemetry as any)?.multiperson?.tracks || [];
  const isReal = Boolean((telemetry as any)?.is_real_measurement);

  useEffect(() => {
    if (!controlsRef.current) return;
    const controls = controlsRef.current;

    if (cameraPreset === 'topdown') {
      controls.object.position.set(0, 8, 0.1);
      controls.target.set(0, 0.0, 0);
    } else if (cameraPreset === 'sensoreye') {
      controls.object.position.set(-1.0, 1.4, -1.5);
      controls.target.set(0, 0.9, 0);
    } else {
      // Isometric — tight framing: human fills ~40% of viewport
      controls.object.position.set(5.0, 4.0, 5.0);
      controls.target.set(0, 0.9, 0);
    }
    controls.update();
  }, [cameraPreset]);

  return (
    <div className="w-full h-full relative bg-[#020617]">
      {/* Watermark when real measurement lacks localization */}
      {isReal && (
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="text-center px-6 py-4 rounded-2xl bg-slate-950/70 border border-amber-500/30 backdrop-blur-sm">
            <p className="text-amber-400 text-sm font-black uppercase tracking-widest">3D Localization Unavailable</p>
            <p className="text-slate-400 text-[10px] mt-1">Single SISO receiver — AoA/multilateration requires multi-anchor deployment</p>
          </div>
        </div>
      )}
      <Canvas
        camera={{ position: [5.0, 4.0, 5.0], fov: 50 }}
        gl={{ antialias: true }}
      >
        {/* Lighting: brighter scene, hero cyan on human */}
        <ambientLight intensity={0.5} />
        <directionalLight position={[8, 12, 8]} intensity={1.4} />
        <pointLight position={[-4.2, 1.5, -2.5]} intensity={2.5} color="#F59E0B" />
        <pointLight position={[0, 2.5, 0]} intensity={4.0} color="#00F0FF" />

        {/* 1. Room with furniture, grid, zones, restricted area */}
        <DigitalTwinRoom3D showGrid={visibility.showGrid} />

        {/* 1b. Walkable NavMesh & Obstacle Footprints Layer */}
        <NavMeshVisualizer3D visible={visibility.showNavMesh ?? true} />

        {/* 2. Router TX Beacon & ESP32 RX Nodes (visible labels) */}
        {visibility.showNodes && (
          <SensorNodes3D
            nodes={telemetry?.nodes || []}
            target={!isReal ? (telemetry?.target || null) : null}
            showBeams={!isReal && visibility.showBeams}
          />
        )}

        {/* 3. RF beams + packet flow particles (simulation only) */}
        {!isReal && visibility.showBeams && (
          <CSIRayBeams3D
            nodes={telemetry?.nodes || []}
            target={telemetry?.target || undefined}
          />
        )}

        {/* 4. Dense CSI point cloud (simulation only — single node cannot reconstruct) */}
        {!isReal && (
          <CSIPointCloud3D
            points={telemetry?.point_cloud || []}
            visible={visibility.showPointCloud}
            targetPosition={telemetry?.target || null}
            renderingMode={visibility.renderingMode || 'production'}
          />
        )}

        {/* 5. HERO: Volumetric Reconstructed Human Avatar (simulation only) */}
        {!isReal && visibility.showAvatar && (
          multiTracks.length > 1 ? (
            <MultiHumanAvatar3D tracks={multiTracks} renderingMode={visibility.renderingMode || 'production'} />
          ) : (
            <HumanAvatar3D
              position={telemetry?.target || undefined}
              activity={telemetry?.activity?.activity || 'Walking'}
              confidence={telemetry?.target?.confidence || 0.98}
              velocity={telemetry?.target ? { vx: telemetry.target.vx, vy: telemetry.target.vy } : undefined}
              renderingMode={visibility.renderingMode || 'production'}
            />
          )
        )}

        {/* 6. Trajectory ribbon (simulation only) */}
        {!isReal && visibility.showTrajectory && multiTracks.length <= 1 && (
          <TrajectoryRibbon3D
            target={telemetry?.target || null}
            visible={visibility.showTrajectory}
          />
        )}

        {/* 7. Ground heatmap (simulation only) */}
        {!isReal && (
          <GroundHeatmap3D
            target={telemetry?.target || null}
            visible={visibility.showHeatmap}
          />
        )}

        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.05}
          maxPolarAngle={Math.PI / 2 - 0.02}
          minDistance={3}
          maxDistance={18}
          autoRotate={visibility.autoRotate}
          autoRotateSpeed={0.8}
        />
      </Canvas>
    </div>
  );
};
