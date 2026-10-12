import React, { useRef, useEffect } from 'react';
import { Line } from '@react-three/drei';
import type { TargetPosition3D } from '../../types/csi';

interface TrajectoryRibbon3DProps {
  target: TargetPosition3D | null;
  visible?: boolean;
}

export const TrajectoryRibbon3D: React.FC<TrajectoryRibbon3DProps> = ({ target, visible = true }) => {
  const historyRef = useRef<[number, number, number][]>([]);

  useEffect(() => {
    if (!target) return;

    // Trajectory ribbon originates from pelvis center mass (y = 0.95m)
    const pt: [number, number, number] = [target.x - 5.0, 0.95, target.y - 4.0];
    historyRef.current.push(pt);
    if (historyRef.current.length > 50) {
      historyRef.current.shift();
    }
  }, [target]);

  if (!visible || historyRef.current.length < 2) {
    return null;
  }

  return (
    <Line
      points={historyRef.current}
      color="#00F0FF"
      lineWidth={2.5}
      transparent
      opacity={0.75}
    />
  );
};
