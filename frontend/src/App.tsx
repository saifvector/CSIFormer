import { useState, useEffect } from 'react';
import { spatialWSClient } from './services/websocket';
import { fetchNodes, setSimulatedActivity } from './services/api';
import type {
  SpatialTelemetryFrame,
  SpatialVisibilitySettings,
  NodeInfo
} from './types/csi';

import { SpatialCanvas3D } from './components/spatial/SpatialCanvas3D';
import { LeftIntelligenceRail } from './components/hud/LeftIntelligenceRail';
import { RightTelemetryRail } from './components/hud/RightTelemetryRail';
import { SpatialHeaderHUD } from './components/hud/SpatialHeaderHUD';
import { BottomControlBarHUD } from './components/hud/BottomControlBarHUD';
import { VisibilityControlsHUD } from './components/hud/VisibilityControlsHUD';
import { DatasetRecorderHUD } from './components/hud/DatasetRecorderHUD';

export function App() {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [telemetry, setTelemetry] = useState<SpatialTelemetryFrame | null>(null);
  const [cameraPreset, setCameraPreset] = useState<'isometric' | 'topdown' | 'sensoreye'>('isometric');
  const [showRecorder, setShowRecorder] = useState<boolean>(false);

  const [visibility, setVisibility] = useState<SpatialVisibilitySettings>({
    showGrid: true,
    showNodes: true,
    showPointCloud: true,
    showBeams: true,
    showAvatar: true,
    showTrajectory: true,
    showHeatmap: true,
    showNavMesh: true,
    autoRotate: false,
  });

  useEffect(() => {
    spatialWSClient.connect();
    const unsubWS = spatialWSClient.subscribe((data) => setTelemetry(data));
    const unsubConn = spatialWSClient.subscribeConnection((conn) => setIsConnected(conn));

    fetchNodes().then((nodesData: NodeInfo[]) => {
      setTelemetry((prev) => (prev ? { ...prev, nodes: nodesData } : null));
    }).catch(err => console.warn("Node fetch warn:", err));

    return () => {
      unsubWS();
      unsubConn();
      spatialWSClient.disconnect();
    };
  }, []);

  const handleActivityChange = async (act: string) => {
    try {
      await setSimulatedActivity(act);
    } catch (err) {
      console.error('Failed to change activity simulation:', err);
    }
  };

  return (
    <div className="w-screen h-screen flex bg-[#020617] text-[#E2F8FF] font-sans selection:bg-[#00F0FF] selection:text-slate-950 overflow-hidden">
      {/* 1. LEFT INTELLIGENCE RAIL (20% Width) */}
      <LeftIntelligenceRail
        activity={telemetry?.activity || null}
        digitalTwin={(telemetry as any)?.digital_twin || null}
        events={(telemetry as any)?.events || null}
        insights={(telemetry as any)?.insights || null}
        onSelectActivity={handleActivityChange}
      />

      {/* 2. CENTER HERO SPATIAL CANVASES SECTION (60% Width) */}
      <div className="flex-1 h-full relative overflow-hidden flex flex-col">
        {/* Floating Top Header Bar */}
        <SpatialHeaderHUD
          isConnected={isConnected}
          cameraPreset={cameraPreset}
          setCameraPreset={setCameraPreset}
        />

        {/* Massive 3D Spatial Canvas */}
        <div className="flex-1 w-full h-full relative">
          <SpatialCanvas3D
            telemetry={telemetry}
            visibility={visibility}
            cameraPreset={cameraPreset}
          />
        </div>

        {/* Scene Layer Visibility Controls */}
        <VisibilityControlsHUD
          visibility={visibility}
          setVisibility={setVisibility}
        />

        {/* Dataset Acquisition & Analytics Dashboard HUD */}
        {showRecorder && <DatasetRecorderHUD onClose={() => setShowRecorder(false)} />}

        {/* Bottom Perception Bar */}
        <BottomControlBarHUD
          cameraPreset={cameraPreset}
          setCameraPreset={setCameraPreset}
          onOpenRecorder={() => setShowRecorder(!showRecorder)}
        />
      </div>

      {/* 3. RIGHT TELEMETRY RAIL (20% Width) */}
      <RightTelemetryRail
        target={telemetry?.target || null}
        tracking={(telemetry as any)?.tracking || null}
        hardware={(telemetry as any)?.hardware || null}
        subcarriers={(telemetry as any)?.subcarriers || null}
        nodes={telemetry?.nodes || []}
        experimentStatus={(telemetry as any)?.experiment || null}
      />
    </div>
  );
}
