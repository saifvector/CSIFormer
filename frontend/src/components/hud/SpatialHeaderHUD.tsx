import React from 'react';
import { Radio, Wifi, Eye, Camera } from 'lucide-react';

interface SpatialHeaderHUDProps {
  isConnected: boolean;
  cameraPreset: 'isometric' | 'topdown' | 'sensoreye';
  setCameraPreset: (preset: 'isometric' | 'topdown' | 'sensoreye') => void;
  dataSource?: 'LIVE HARDWARE' | 'RECORDED REPLAY' | 'SIMULATION' | string;
  isRealMeasurement?: boolean;
}

export const SpatialHeaderHUD: React.FC<SpatialHeaderHUDProps> = ({
  isConnected,
  cameraPreset,
  setCameraPreset,
  dataSource = 'SIMULATION',
  isRealMeasurement = false,
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

      {/* Data Source Badge, Camera Viewport Perspective Switcher & WS Stream Status */}
      <div className="flex items-center space-x-3 pointer-events-auto">
        {/* Prominent Data Source Badge */}
        <div
          className={`hud-panel px-3 py-1.5 rounded-xl flex items-center space-x-2 font-mono text-xs border ${
            dataSource === 'LIVE HARDWARE'
              ? 'bg-emerald-950/90 border-emerald-500 text-emerald-300 shadow-lg shadow-emerald-500/20'
              : dataSource === 'RECORDED REPLAY'
              ? 'bg-amber-950/90 border-amber-500 text-amber-300 shadow-lg shadow-amber-500/20'
              : 'bg-purple-950/80 border-purple-500/40 text-purple-300'
          }`}
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
                dataSource === 'LIVE HARDWARE'
                  ? 'bg-emerald-400'
                  : dataSource === 'RECORDED REPLAY'
                  ? 'bg-amber-400'
                  : 'bg-purple-400'
              } opacity-75`}
            ></span>
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                dataSource === 'LIVE HARDWARE'
                  ? 'bg-emerald-500'
                  : dataSource === 'RECORDED REPLAY'
                  ? 'bg-amber-500'
                  : 'bg-purple-500'
              }`}
            ></span>
          </span>
          <div className="flex flex-col">
            <span className="font-extrabold tracking-wider leading-none text-[10px]">
              SOURCE: {dataSource}
            </span>
            <span className="text-[8px] text-slate-400 leading-tight">
              {isRealMeasurement ? 'Measured CSI (Real)' : 'Synthetic RF Model'}
            </span>
          </div>
        </div>

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
