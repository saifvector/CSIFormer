import React, { useState, useEffect } from 'react';
import {
  Disc, Square, Play, Pause, XCircle, Download, Database,
  BarChart3, ShieldCheck, AlertTriangle, CheckCircle2,
  FileCode, Layers, RefreshCw, X
} from 'lucide-react';
import {
  startDatasetSession, pauseDatasetSession, resumeDatasetSession,
  stopDatasetSession, cancelDatasetSession, fetchDatasetSessionStatus,
  fetchDatasetDashboard, fetchReadinessReport, getDatasetExportUrl
} from '../../services/api';
import type {
  DatasetSessionStatus, DatasetDashboardStats, ResearchReadinessReport
} from '../../types/csi';

const ALL_8_CLASSES = [
  "Empty Room",
  "Standing",
  "Sitting",
  "Walking",
  "Running",
  "Falling",
  "Lying Down",
  "Multiple Persons"
];

interface DatasetRecorderHUDProps {
  onClose?: () => void;
}

export const DatasetRecorderHUD: React.FC<DatasetRecorderHUDProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState<'record' | 'dashboard' | 'readiness'>('record');
  
  // Session Form State
  const [activityClass, setActivityClass] = useState<string>('Walking');
  const [subjectId, setSubjectId] = useState<string>('Subj-01');
  const [roomName, setRoomName] = useState<string>('Defense Lab 101');
  const [routerId, setRouterId] = useState<string>('Router-TX-01');
  const [notes, setNotes] = useState<string>('Phase 09 Real ESP32-S3 Capture');
  
  // Live Status & Metadata
  const [sessionStatus, setSessionStatus] = useState<DatasetSessionStatus | null>(null);
  const [dashboardStats, setDashboardStats] = useState<DatasetDashboardStats | null>(null);
  const [readinessReport, setReadinessReport] = useState<ResearchReadinessReport | null>(null);
  const [lastCompletedSessionId, setLastCompletedSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Polling for live session telemetry and stats
  useEffect(() => {
    const pollStatus = async () => {
      try {
        const st = await fetchDatasetSessionStatus();
        setSessionStatus(st);
      } catch (e) {
        // quiet fallback
      }
    };

    pollStatus();
    const interval = setInterval(pollStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const refreshDashboard = async () => {
    setIsLoading(true);
    try {
      const [dash, rep] = await Promise.all([
        fetchDatasetDashboard(),
        fetchReadinessReport()
      ]);
      setDashboardStats(dash);
      setReadinessReport(rep);
    } catch (e) {
      console.warn("Failed to fetch dashboard stats:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'dashboard' || activeTab === 'readiness') {
      refreshDashboard();
    }
  }, [activeTab]);

  const handleStart = async () => {
    setIsLoading(true);
    try {
      await startDatasetSession({
        activity_class: activityClass,
        subject_id: subjectId,
        room_name: roomName,
        router_id: routerId,
        notes: notes
      });
      setLastCompletedSessionId(null);
      const st = await fetchDatasetSessionStatus();
      setSessionStatus(st);
    } catch (err) {
      console.error("Failed to start session:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePause = async () => {
    try {
      await pauseDatasetSession();
      const st = await fetchDatasetSessionStatus();
      setSessionStatus(st);
    } catch (err) {
      console.error("Failed to pause session:", err);
    }
  };

  const handleResume = async () => {
    try {
      await resumeDatasetSession();
      const st = await fetchDatasetSessionStatus();
      setSessionStatus(st);
    } catch (err) {
      console.error("Failed to resume session:", err);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      const res = await stopDatasetSession();
      if (res && res.session_id) {
        setLastCompletedSessionId(res.session_id);
      }
      const st = await fetchDatasetSessionStatus();
      setSessionStatus(st);
      refreshDashboard();
    } catch (err) {
      console.error("Failed to stop session:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async () => {
    if (window.confirm("Are you sure you want to discard this recording?")) {
      try {
        await cancelDatasetSession();
        const st = await fetchDatasetSessionStatus();
        setSessionStatus(st);
      } catch (err) {
        console.error("Failed to cancel session:", err);
      }
    }
  };

  const isRec = sessionStatus?.is_recording || false;
  const isPaused = sessionStatus?.is_paused || false;

  const getQualityBadgeColor = (qLevel?: string) => {
    switch (qLevel) {
      case 'Excellent': return 'text-cyan-400 bg-cyan-950/80 border-cyan-700';
      case 'Good': return 'text-emerald-400 bg-emerald-950/80 border-emerald-700';
      case 'Acceptable': return 'text-amber-400 bg-amber-950/80 border-amber-700';
      case 'Poor': return 'text-orange-400 bg-orange-950/80 border-orange-700';
      default: return 'text-rose-400 bg-rose-950/80 border-rose-700';
    }
  };

  return (
    <div className="absolute top-16 left-4 z-50 w-[420px] max-h-[85vh] flex flex-col bg-slate-950/95 backdrop-blur-xl border border-slate-800/90 rounded-2xl shadow-2xl shadow-cyan-950/40 text-slate-200 font-mono text-xs overflow-hidden pointer-events-auto transition-all animate-in fade-in zoom-in-95 duration-200">
      
      {/* 1. HEADER BAR */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900/60">
        <div className="flex items-center space-x-2.5">
          <div className={`p-1.5 rounded-lg ${isRec ? (isPaused ? 'bg-amber-950 text-amber-400 border border-amber-700' : 'bg-rose-950 text-rose-400 border border-rose-700 animate-pulse') : 'bg-cyan-950 text-cyan-400 border border-cyan-800'}`}>
            <Database className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-1.5">
              CSI Dataset Acquisition
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-semibold">Phase 09</span>
            </h3>
            <p className="text-[10px] text-slate-400">Real ESP32-S3 CSI Capture & Research Storage</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {isRec && (
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${isPaused ? 'bg-amber-950 text-amber-300 border-amber-700 animate-pulse' : 'bg-rose-950 text-rose-400 border-rose-700 animate-pulse'}`}>
              {isPaused ? 'PAUSED' : 'REC'}
            </span>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* 2. TAB SELECTOR */}
      <div className="flex items-center border-b border-slate-800/80 bg-slate-900/40 p-1">
        <button
          onClick={() => setActiveTab('record')}
          className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 rounded-xl font-bold text-[11px] transition-all ${activeTab === 'record' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <Disc className={`w-3.5 h-3.5 ${isRec ? 'text-rose-400 animate-spin' : ''}`} />
          <span>Live Capture</span>
        </button>

        <button
          onClick={() => setActiveTab('dashboard')}
          className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 rounded-xl font-bold text-[11px] transition-all ${activeTab === 'dashboard' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Analytics</span>
        </button>

        <button
          onClick={() => setActiveTab('readiness')}
          className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 rounded-xl font-bold text-[11px] transition-all ${activeTab === 'readiness' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm' : 'text-slate-400 hover:text-slate-200'}`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Readiness</span>
        </button>
      </div>

      {/* 3. SCROLLABLE CONTENT BODY */}
      <div className="flex-1 p-4 overflow-y-auto max-h-[calc(85vh-130px)] space-y-4">
        
        {/* ========================================================================= */}
        {/* TAB 1: LIVE ACQUISITION SESSION */}
        {/* ========================================================================= */}
        {activeTab === 'record' && (
          <div className="space-y-3.5">
            
            {/* Form Fields */}
            <div className="space-y-2.5">
              <div>
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">
                  1. Activity Class Label (Standard 8)
                </label>
                <select
                  value={activityClass}
                  onChange={(e) => setActivityClass(e.target.value)}
                  disabled={isRec}
                  className="w-full bg-slate-900 text-cyan-300 border border-slate-800 rounded-xl p-2 text-xs focus:outline-none focus:border-cyan-500 disabled:opacity-50 cursor-pointer font-bold"
                >
                  {ALL_8_CLASSES.map((cls) => (
                    <option key={cls} value={cls} className="bg-slate-950 text-slate-200">
                      {cls}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Subject ID</label>
                  <input
                    type="text"
                    value={subjectId}
                    onChange={(e) => setSubjectId(e.target.value)}
                    disabled={isRec}
                    className="w-full bg-slate-900 text-slate-200 border border-slate-800 rounded-xl p-1.5 text-[11px] focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Room / Site Name</label>
                  <input
                    type="text"
                    value={roomName}
                    onChange={(e) => setRoomName(e.target.value)}
                    disabled={isRec}
                    className="w-full bg-slate-900 text-slate-200 border border-slate-800 rounded-xl p-1.5 text-[11px] focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Wi-Fi Router ID</label>
                  <input
                    type="text"
                    value={routerId}
                    onChange={(e) => setRouterId(e.target.value)}
                    disabled={isRec}
                    className="w-full bg-slate-900 text-slate-200 border border-slate-800 rounded-xl p-1.5 text-[11px] focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-1">Experiment Notes</label>
                  <input
                    type="text"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={isRec}
                    placeholder="Optional notes"
                    className="w-full bg-slate-900 text-slate-200 border border-slate-800 rounded-xl p-1.5 text-[11px] focus:outline-none focus:border-cyan-500 disabled:opacity-50"
                  />
                </div>
              </div>
            </div>

            {/* Live Telemetry & Quality Gauges (While Recording) */}
            {isRec && sessionStatus && (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 space-y-2.5 animate-in fade-in duration-300">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Live Capture Metrics</span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${getQualityBadgeColor(sessionStatus.quality_level)}`}>
                    {sessionStatus.quality_level} ({sessionStatus.composite_quality_score}%)
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                  <div className="bg-slate-950 p-2 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 block text-[9px]">Frames</span>
                    <span className="text-cyan-400 font-bold text-sm">{sessionStatus.recorded_frames}</span>
                  </div>
                  <div className="bg-slate-950 p-2 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 block text-[9px]">Duration</span>
                    <span className="text-emerald-400 font-bold text-sm">{sessionStatus.elapsed_seconds}s</span>
                  </div>
                  <div className="bg-slate-950 p-2 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 block text-[9px]">Packet Loss</span>
                    <span className={`font-bold text-sm ${sessionStatus.packet_loss_pct > 5 ? 'text-rose-400' : 'text-emerald-400'}`}>
                      {sessionStatus.packet_loss_pct}%
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-800/60">
                  <span>Avg SNR: <strong className="text-cyan-300">{sessionStatus.avg_snr} dB</strong></span>
                  <span>Avg RSSI: <strong className="text-emerald-300">{sessionStatus.avg_rssi} dBm</strong></span>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="space-y-2 pt-1">
              {!isRec ? (
                <button
                  onClick={handleStart}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-red-600 text-white font-bold text-xs shadow-lg shadow-rose-900/30 hover:from-rose-500 hover:to-red-500 transition-all active:scale-98 disabled:opacity-50"
                >
                  <Play className="w-4 h-4 fill-white" />
                  <span>Start Recording Session</span>
                </button>
              ) : (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    {!isPaused ? (
                      <button
                        onClick={handlePause}
                        className="flex items-center justify-center space-x-1.5 py-2 rounded-xl bg-slate-900 text-amber-300 border border-amber-700/60 font-bold text-xs hover:bg-slate-800 transition-all"
                      >
                        <Pause className="w-3.5 h-3.5" />
                        <span>Pause Session</span>
                      </button>
                    ) : (
                      <button
                        onClick={handleResume}
                        className="flex items-center justify-center space-x-1.5 py-2 rounded-xl bg-emerald-950 text-emerald-300 border border-emerald-700 font-bold text-xs hover:bg-emerald-900 transition-all"
                      >
                        <Play className="w-3.5 h-3.5 fill-emerald-300" />
                        <span>Resume</span>
                      </button>
                    )}

                    <button
                      onClick={handleCancel}
                      className="flex items-center justify-center space-x-1.5 py-2 rounded-xl bg-slate-900 text-slate-400 border border-slate-800 font-bold text-xs hover:text-rose-400 hover:bg-slate-800 transition-all"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Discard</span>
                    </button>
                  </div>

                  <button
                    onClick={handleStop}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white font-bold text-xs shadow-lg shadow-emerald-900/30 hover:from-emerald-500 hover:to-teal-500 transition-all active:scale-98"
                  >
                    <Square className="w-3.5 h-3.5 fill-white" />
                    <span>Finalize & Export Multi-Format (.csv, .json, .npy)</span>
                  </button>
                </div>
              )}
            </div>

            {/* One-Click Multi-Format Downloads */}
            {lastCompletedSessionId && (
              <div className="bg-slate-900/90 border border-emerald-800/60 rounded-xl p-3 space-y-2 mt-3 animate-in fade-in">
                <div className="flex items-center space-x-1.5 text-emerald-400 font-bold text-[11px]">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Session Saved: {lastCompletedSessionId}</span>
                </div>
                
                <p className="text-[10px] text-slate-400">Download research-ready dataset files:</p>

                <div className="grid grid-cols-3 gap-1.5">
                  <a
                    href={getDatasetExportUrl(lastCompletedSessionId, 'csv')}
                    download
                    className="flex items-center justify-center space-x-1 py-1.5 rounded-lg bg-slate-950 text-emerald-300 border border-emerald-800/80 font-bold text-[10px] hover:bg-emerald-950 transition-all"
                  >
                    <Download className="w-3 h-3" />
                    <span>CSV</span>
                  </a>
                  <a
                    href={getDatasetExportUrl(lastCompletedSessionId, 'json')}
                    download
                    className="flex items-center justify-center space-x-1 py-1.5 rounded-lg bg-slate-950 text-cyan-300 border border-cyan-800/80 font-bold text-[10px] hover:bg-cyan-950 transition-all"
                  >
                    <FileCode className="w-3 h-3" />
                    <span>JSON</span>
                  </a>
                  <a
                    href={getDatasetExportUrl(lastCompletedSessionId, 'npy')}
                    download
                    className="flex items-center justify-center space-x-1 py-1.5 rounded-lg bg-slate-950 text-purple-300 border border-purple-800/80 font-bold text-[10px] hover:bg-purple-950 transition-all"
                  >
                    <Layers className="w-3 h-3" />
                    <span>NumPy .npy</span>
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: DATASET ANALYTICS DASHBOARD */}
        {/* ========================================================================= */}
        {activeTab === 'dashboard' && (
          <div className="space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Physical Storage Status</span>
              <button
                onClick={refreshDashboard}
                disabled={isLoading}
                className="flex items-center space-x-1 text-[10px] text-cyan-400 hover:text-cyan-300"
              >
                <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
                <span>Rescan Disk</span>
              </button>
            </div>

            {/* Overview Summary Cards */}
            {dashboardStats ? (
              <>
                <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                  <div className="bg-slate-900 p-2 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[9px]">Recordings</span>
                    <span className="text-cyan-300 font-bold text-sm">{dashboardStats.total_recordings}</span>
                  </div>
                  <div className="bg-slate-900 p-2 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[9px]">Total Frames</span>
                    <span className="text-emerald-300 font-bold text-sm">{dashboardStats.total_frames}</span>
                  </div>
                  <div className="bg-slate-900 p-2 rounded-xl border border-slate-800">
                    <span className="text-slate-500 block text-[9px]">Storage</span>
                    <span className="text-purple-300 font-bold text-sm">{dashboardStats.storage_mb} MB</span>
                  </div>
                </div>

                {/* Health & Balance Score */}
                <div className="bg-slate-900/80 p-3 rounded-xl border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Class Balance Index:</span>
                    <span className="font-bold text-cyan-400">{dashboardStats.class_balance_score_pct}%</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400">Dataset Status:</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${dashboardStats.status_indicator === 'HEALTHY' ? 'bg-emerald-950 text-emerald-300 border-emerald-700' : 'bg-amber-950 text-amber-300 border-amber-700'}`}>
                      {dashboardStats.status_indicator}
                    </span>
                  </div>
                </div>

                {/* 8-Class Distribution Breakdown */}
                <div className="space-y-2">
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Class Distribution (8 Classes)</span>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {Object.entries(dashboardStats.class_distribution).map(([cls, cs]) => {
                      const maxFrames = Math.max(1, ...Object.values(dashboardStats.class_distribution).map(v => v.frames_count));
                      const pct = Math.min(100, Math.round((cs.frames_count / maxFrames) * 100));
                      return (
                        <div key={cls} className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/60 space-y-1">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="font-bold text-slate-200">{cls}</span>
                            <span className="text-slate-400">{cs.recordings_count} sessions ({cs.frames_count} frames)</span>
                          </div>
                          <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${cs.frames_count > 0 ? 'bg-gradient-to-r from-cyan-500 to-blue-500' : 'bg-slate-800'}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Missing Classes Alert */}
                {dashboardStats.missing_classes.length > 0 && (
                  <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-2.5 flex items-start space-x-2 text-[10px] text-amber-300">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">Missing Dataset Categories ({dashboardStats.missing_classes.length}):</span>
                      <span className="text-amber-200/80">{dashboardStats.missing_classes.join(', ')}</span>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-6 text-slate-500">Loading disk analytics...</div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: RESEARCH READINESS REPORT */}
        {/* ========================================================================= */}
        {activeTab === 'readiness' && (
          <div className="space-y-3.5">
            {readinessReport ? (
              <>
                <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Research Maturity Level</span>
                    <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700">
                      {readinessReport.readiness_level}
                    </span>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-slate-400">Readiness Score:</span>
                      <span className="font-bold text-cyan-400">{readinessReport.readiness_score_pct}%</span>
                    </div>
                    <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all duration-500"
                        style={{ width: `${readinessReport.readiness_score_pct}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Recommendations */}
                <div className="space-y-2">
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">Recommended Next Steps</span>
                  <div className="space-y-1.5">
                    {readinessReport.recommendations.map((rec, i) => (
                      <div key={i} className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80 flex items-start space-x-2 text-[10px]">
                        <span className="w-4 h-4 rounded-full bg-cyan-950 border border-cyan-800 text-cyan-400 flex items-center justify-center text-[9px] font-bold shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        <span className="text-slate-300 leading-relaxed">{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-6 text-slate-500">Loading readiness report...</div>
            )}
          </div>
        )}
      </div>

    </div>
  );
};
