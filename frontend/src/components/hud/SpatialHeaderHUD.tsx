import React from 'react';
import { Radio, Wifi, Eye, Camera } from 'lucide-react';

interface SpatialHeaderHUDProps {
  isConnected: boolean;
  cameraPreset: 'isometric' | 'topdown' | 'sensoreye';
  setCameraPreset: (preset: 'isometric' | 'topdown' | 'sensoreye') => void;
}

export const SpatialHeaderHUD: React.FC<SpatialHeaderHUDProps> = ({
  isConnected,
  cameraPreset,
  setCameraPreset
}) => {
  return (
    <div className="absolute top-4 left-4 right-4 z-40 flex items-center justify-between pointer-events-none">
      {/* Brand & Platform Identifier */}
      <div className="hud-panel hud-panel-cyan px-4 py-2.5 rounded-2xl flex items-center space-x-3 pointer-events-auto">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
          <Radio className="w-5 h-5 text-white animate-pulse" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-black tracking-wider bg-gradient-to-r from-cyan-400 via-sky-200 to-indigo-400 bg-clip-text text-transparent uppercase">
              CSIFormer
            </h1>
            <span className="px-2 py-0.5 text-[9px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 rounded-full font-mono">
              3D SPATIAL PERCEPTION
            </span>
          </div>
          <p className="text-[10px] text-slate-400 font-medium">
            Privacy-Preserving Wi-Fi CSI Spatial Intelligence Engine
          </p>
        </div>
      </div>

      {/* Camera Viewport Perspective Switcher & WS Stream Status */}
      <div className="flex items-center space-x-3 pointer-events-auto">
        {/* Camera Preset Switcher */}
        <div className="hud-panel p-1 rounded-xl flex items-center space-x-1 font-mono text-xs">
          <button
            onClick={() => setCameraPreset('isometric')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-bold transition-all ${
              cameraPreset === 'isometric'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            <span>Isometric</span>
          </button>

          <button
            onClick={() => setCameraPreset('topdown')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-bold transition-all ${
              cameraPreset === 'topdown'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Top Radar</span>
          </button>

          <button
            onClick={() => setCameraPreset('sensoreye')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-bold transition-all ${
              cameraPreset === 'sensoreye'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Sensor Eye</span>
          </button>
        </div>

        {/* WebSocket Stream Badge */}
        <div className={`hud-panel px-3.5 py-2 rounded-xl flex items-center space-x-2 font-mono text-xs ${
          isConnected ? 'text-emerald-400' : 'text-rose-400'
        }`}>
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
              isConnected ? 'bg-emerald-400' : 'bg-rose-400'
            } opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${
              isConnected ? 'bg-emerald-500' : 'bg-rose-500'
            }`}></span>
          </span>
          <Wifi className="w-3.5 h-3.5" />
          <span className="font-bold">{isConnected ? '30 FPS Telemetry' : 'Disconnected'}</span>
        </div>
      </div>
    </div>
  );
};
