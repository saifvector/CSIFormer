import React from 'react';
import type { TargetPosition3D } from '../../types/csi';

interface GroundHeatmap3DProps {
  target: TargetPosition3D | null;
  visible?: boolean;
}

export const GroundHeatmap3D: React.FC<GroundHeatmap3DProps> = ({ target, visible = true }) => {
  if (!visible || !target || target.z < 0) {
    return null;
  }

  const tx = target.x - 5.0;
  const ty = target.y - 4.0;

  return (
    <group position={[tx, 0.02, ty]}>
      {/* Ground Subcarrier Energy Dispersion Rings */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0, 1.4, 32]} />
        <meshBasicMaterial
          color="#00F0FF"
          transparent
          opacity={0.25}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.4, 2.2, 32]} />
        <meshBasicMaterial
          color="#6366F1"
          transparent
          opacity={0.12}
        />
      </mesh>
    </group>
  );
};
