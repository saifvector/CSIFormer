import React from 'react';
import * as THREE from 'three';
import { HumanAvatar3D } from './HumanAvatar3D';

import type { RenderingMode } from '../../types/csi';

interface SingleTrackInfo {
  track_id: string;
  color: string;
  x: number;
  y: number;
  z: number;
  speed_ms: number;
  activity: string;
  trajectory_history?: { x: number; y: number; z: number }[];
}

interface MultiHumanAvatar3DProps {
  tracks: SingleTrackInfo[];
  renderingMode?: RenderingMode;
}

export const MultiHumanAvatar3D: React.FC<MultiHumanAvatar3DProps> = ({ tracks, renderingMode = 'production' }) => {
  if (!tracks || tracks.length === 0) return null;

  return (
    <group>
      {tracks.map((track) => {
        const trackColor = track.color || '#00F0FF';

        // Construct 3D Trajectory Ribbon line points (pelvis height = 0.95m)
        const points = (track.trajectory_history || []).map(
          (p) => new THREE.Vector3(p.x - 5.0, 0.95, p.y - 4.0)
        );

        return (
          <group key={track.track_id}>
            {/* Volumetric Holographic Human Avatar for each tracked person */}
            <HumanAvatar3D
              position={{ x: track.x, y: track.y, z: track.z }}
              activity={track.activity || 'Walking'}
              confidence={0.96}
              velocity={{ vx: track.speed_ms * 0.7, vy: 0.3 }}
              primaryColor={trackColor}
              accentColor={trackColor === '#00F0FF' ? '#7DF9FF' : '#FFFFFF'}
              scale={1.0}
              renderingMode={renderingMode}
            />

            {/* Multi-Target 3D Trajectory Ribbon originating from pelvis */}
            {points.length > 2 && (
              <line>
                <bufferGeometry
                  attach="geometry"
                  onUpdate={(self) => self.setFromPoints(points)}
                />
                <lineBasicMaterial
                  attach="material"
                  color={trackColor}
                  linewidth={2}
                  transparent
                  opacity={0.85}
                />
              </line>
            )}
          </group>
        );
      })}
    </group>
  );
};
