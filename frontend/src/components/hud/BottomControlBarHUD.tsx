import React, { useState } from 'react';
import { UserCheck, Activity, Compass, MapPin, Disc, Cpu, Usb, Wifi, Camera, Eye, Radio } from 'lucide-react';
import { setHardwareSource } from '../../services/api';

interface BottomControlBarHUDProps {
  cameraPreset: 'isometric' | 'topdown' | 'sensoreye';
  setCameraPreset: (preset: 'isometric' | 'topdown' | 'sensoreye') => void;
  onOpenRecorder?: () => void;
  currentHardwareMode?: string;
}

export const BottomControlBarHUD: React.FC<BottomControlBarHUDProps> = ({
  cameraPreset,
  setCameraPreset,
  onOpenRecorder,
  currentHardwareMode = 'simulated',
}) => {
  const [activeTab, setActiveTab] = useState<string>('localization');
  const [hardwareMode, setHardwareMode] = useState<string>(currentHardwareMode);

  React.useEffect(() => {
    if (currentHardwareMode) {
      setHardwareMode(currentHardwareMode);
    }
  }, [currentHardwareMode]);

  const tabs = [
    { id: 'presence', label: 'Presence Detection', icon: UserCheck },
    { id: 'activity', label: 'Activity Recognition', icon: Activity },
    { id: 'localization', label: '3D Localization', icon: Compass },
    { id: 'mapping', label: 'Room Mapping', icon: MapPin },
    { id: 'recording', label: 'Dataset Recording', icon: Disc },
    { id: 'simulation', label: 'Simulation Controls', icon: Cpu },
  ];

  const handleSelectHardwareMode = async (mode: string) => {
    setHardwareMode(mode);
    try {
      await setHardwareSource(mode);
    } catch (err) {
      console.error('Failed to set hardware source:', err);
    }
  };

  return (
    <div className="absolute bottom-4 left-4 right-4 z-40 flex items-center justify-between pointer-events-none">
      {/* 1. Perception Mode Switcher Tabs */}
      <div className="hud-panel hud-panel-cyan p-1.5 rounded-2xl flex items-center space-x-1 font-mono text-xs pointer-events-auto shadow-2xl">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                if (tab.id === 'recording' && onOpenRecorder) {
                  onOpenRecorder();
                }
              }}
              className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl font-bold transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-500/25'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 2. Hardware Source Switcher & Camera Controls */}
      <div className="flex items-center space-x-3 pointer-events-auto">
        {/* Quick Hardware Source Toggles */}
        <div className="hud-panel p-1 rounded-xl flex items-center space-x-1 font-mono text-[11px]">
          <button
            onClick={() => handleSelectHardwareMode('simulated')}
            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg font-bold transition-all ${
              hardwareMode === 'simulated'
                ? 'bg-cyan-950 border border-cyan-500 text-cyan-300'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Physics Spatial Simulator"
          >
            <Cpu className="w-3 h-3 text-cyan-400" />
            <span>Sim</span>
          </button>
          <button
            onClick={() => handleSelectHardwareMode('esp32_serial')}
            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg font-bold transition-all ${
              hardwareMode === 'esp32_serial'
                ? 'bg-emerald-950 border border-emerald-500 text-emerald-300 shadow-md shadow-emerald-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="ESP32-S3 Live USB Serial (COM5)"
          >
            <Usb className="w-3 h-3 text-emerald-400" />
            <span>USB (COM5)</span>
          </button>
          <button
            onClick={() => handleSelectHardwareMode('recorded_replay')}
            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg font-bold transition-all ${
              hardwareMode === 'recorded_replay'
                ? 'bg-amber-950 border border-amber-500 text-amber-300 shadow-md shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Replay Real CSI Dataset (30 Hz)"
          >
            <Disc className="w-3 h-3 text-amber-400" />
            <span>Replay (Real)</span>
          </button>
          <button
            onClick={() => handleSelectHardwareMode('esp32_udp')}
            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg font-bold transition-all ${
              hardwareMode === 'esp32_udp'
                ? 'bg-cyan-950 border border-cyan-500 text-cyan-300'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="ESP32 UDP Broadcast (Port 5555)"
          >
            <Wifi className="w-3 h-3 text-cyan-400" />
            <span>UDP</span>
          </button>
        </div>

        {/* Camera Perspective Presets */}
        <div className="hud-panel p-1 rounded-xl flex items-center space-x-1 font-mono text-xs">
          <button
            onClick={() => setCameraPreset('isometric')}
            className={`p-2 rounded-lg font-bold transition-all ${
              cameraPreset === 'isometric'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Isometric 3D Perspective"
          >
            <Camera className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setCameraPreset('topdown')}
            className={`p-2 rounded-lg font-bold transition-all ${
              cameraPreset === 'topdown'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Top-Down 2D Radar"
          >
            <Eye className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setCameraPreset('sensoreye')}
            className={`p-2 rounded-lg font-bold transition-all ${
              cameraPreset === 'sensoreye'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Sensor Eye Perspective"
          >
            <Radio className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
