import React, { useMemo, useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { CSIPoint3D, RenderingMode } from '../../types/csi';

interface CSIPointCloud3DProps {
  points: CSIPoint3D[];
  visible?: boolean;
  targetPosition?: { x: number; y: number; z: number } | null;
  renderingMode?: RenderingMode;
}

// ══════════════════════════════════════════════════════════════════════════════
// CSI POINT CLOUD (RF DOPPLER SCATTER LAYER)
// Ambient Doppler-colored RF energy reflections tightly enveloping the target
// ══════════════════════════════════════════════════════════════════════════════

export const CSIPointCloud3D: React.FC<CSIPointCloud3DProps> = ({
  points,
  visible = true,
  targetPosition = null,
  renderingMode = 'production',
}) => {
  const pointsRef = useRef<THREE.Points | null>(null);

  const isProduction = renderingMode === 'production';
  const hasData = points && points.length > 0 && !isProduction;
  const numPoints = hasData ? points.length : 0;

  const [positions, colors] = useMemo(() => {
    const count = Math.max(numPoints, 1);
    return [new Float32Array(count * 3), new Float32Array(count * 3)];
  }, [numPoints]);

  useEffect(() => {
    if (!visible || !hasData) return;

    // Target position in Three.js coordinates
    const tgtX = targetPosition ? targetPosition.x - 5.0 : 0;
    const tgtZ = targetPosition ? targetPosition.y - 4.0 : 0;

    for (let i = 0; i < points.length; i++) {
      const p = points[i];

      // Radial scatter tightly bounded around human body cylinder (radius ~0.45m, height 0.1m to 1.75m)
      const angle = (i * 2.39996); // Golden ratio angle dispersion
      const r = 0.08 + (Math.abs(p.doppler) % 0.32);
      const h = Math.min(1.75, Math.max(0.1, p.z));

      positions[i * 3 + 0] = tgtX + Math.cos(angle) * r;
      positions[i * 3 + 1] = h;
      positions[i * 3 + 2] = tgtZ + Math.sin(angle) * r;

      // Doppler chromatic spectrum: High velocity = magenta/amber, Low velocity = cyan/white
      const dopplerNorm = Math.min(1.0, Math.abs(p.doppler) / 4.0);
      colors[i * 3 + 0] = 0.1 + dopplerNorm * 0.9;
      colors[i * 3 + 1] = 0.9 * (1.0 - dopplerNorm * 0.4);
      colors[i * 3 + 2] = 1.0;
    }

    if (pointsRef.current) {
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
      pointsRef.current.geometry.attributes.color.needsUpdate = true;
    }
  }, [points, visible, positions, colors, targetPosition, hasData]);

  if (!visible || !hasData) {
    return null;
  }

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.038}
        vertexColors
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
};
