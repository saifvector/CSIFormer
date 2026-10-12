import React, { useRef, useMemo, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';
import { positionCorrectionEngine } from '../../services/spatial/PositionCorrectionEngine';
import type { OccupancyStatus } from '../../services/spatial/PositionCorrectionEngine';
import { obstacleAvoidanceSteering } from '../../services/spatial/ObstacleAvoidanceSteering';
import { humanIKController } from '../../services/spatial/HumanIKController';
import type { RenderingMode } from '../../types/csi';

interface HumanAvatar3DProps {
  position?: { x: number; y: number; z: number };
  activity?: string;
  confidence?: number;
  velocity?: { vx: number; vy: number };
  primaryColor?: string;
  accentColor?: string;
  scale?: number;
  showCollisionStatus?: boolean;
  renderingMode?: RenderingMode;
}

// ══════════════════════════════════════════════════════════════════════════════════
// CSIFORMER VOLUMETRIC DIGITAL HUMAN RECONSTRUCTION
// Advanced Wi-Fi CSI Spatial Perception & Inverse Kinematics Seating Controller
// ══════════════════════════════════════════════════════════════════════════════════

export const HumanAvatar3D: React.FC<HumanAvatar3DProps> = ({
  position = { x: 5.0, y: 1.0, z: 4.0 },
  activity = 'Walking',
  confidence = 0.98,
  velocity = { vx: 0.3, vy: 0.2 },
  primaryColor = '#00F0FF',
  accentColor = '#7DF9FF',
  scale = 1.0,
  showCollisionStatus = true,
  renderingMode = 'production',
}) => {
  // Main root groups
  const avatarGroupRef = useRef<THREE.Group>(null);
  const bodyRootRef = useRef<THREE.Group>(null);
  const cloudRef = useRef<THREE.Points>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const auraRef = useRef<THREE.Mesh>(null);
  const ringMatRef = useRef<THREE.MeshBasicMaterial>(null);
  const auraMatRef = useRef<THREE.MeshBasicMaterial>(null);

  // Articulated limb references for procedural biomechanics
  const headRef = useRef<THREE.Group>(null);
  const chestRef = useRef<THREE.Group>(null);
  const leftArmRef = useRef<THREE.Group>(null);
  const rightArmRef = useRef<THREE.Group>(null);
  const leftForearmRef = useRef<THREE.Group>(null);
  const rightForearmRef = useRef<THREE.Group>(null);
  const leftThighRef = useRef<THREE.Group>(null);
  const rightThighRef = useRef<THREE.Group>(null);
  const leftCalfRef = useRef<THREE.Group>(null);
  const rightCalfRef = useRef<THREE.Group>(null);

  // Smooth rotation and collision states
  const currentYawRef = useRef<number>(0);
  const [collisionStatus, setCollisionStatus] = useState<OccupancyStatus>('SAFE');
  const [nearestObstacle, setNearestObstacle] = useState<string>('None');

  // Map 10m x 8m room coordinates -> Three.js center [-5..+5, -4..+4]
  const rawThreeX = (position.x ?? 5.0) - 5.0;
  const rawThreeZ = (position.y ?? 4.0) - 4.0; // In 2D floor plane, y represents depth (z in Three.js)

  // ══════════════════════════════════════════════════════════════════════════════
  // 1. SUBTLE CSI PARTICLE ENVELOPE (For Research & Debug Modes)
  // Max opacity 35%, subtle RF energy flow contouring volumetric human surface
  // ══════════════════════════════════════════════════════════════════════════════
  const [particlePositions, particleColors] = useMemo(() => {
    const count = 1800;
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    const cCyan = new THREE.Color('#00F0FF');
    const cIce = new THREE.Color('#7DF9FF');
    const cWhite = new THREE.Color('#FFFFFF');
    const cSapphire = new THREE.Color('#0080FF');

    for (let i = 0; i < count; i++) {
      const seg = Math.random();
      let lx = 0, ly = 0, lz = 0;
      let colChoice = cCyan;

      if (seg < 0.15) {
        // Head Envelope (y=1.52 to 1.74m)
        const th = Math.random() * Math.PI * 2;
        const ph = Math.acos(2 * Math.random() - 1);
        const r = 0.11 + Math.random() * 0.03;
        lx = r * Math.sin(ph) * Math.cos(th) * 0.85;
        ly = 1.62 + r * Math.cos(ph) * 1.05;
        lz = r * Math.sin(ph) * Math.sin(th) * 0.9;
        colChoice = cWhite;
      } else if (seg < 0.45) {
        // Torso & Pelvis Envelope (y=0.88 to 1.48m)
        const u = Math.random();
        const th = Math.random() * Math.PI * 2;
        const rx = 0.17 + Math.random() * 0.03;
        const rz = 0.11 + Math.random() * 0.03;
        lx = rx * Math.cos(th);
        ly = 0.88 + u * 0.60;
        lz = rz * Math.sin(th);
        colChoice = cCyan;
      } else if (seg < 0.70) {
        // Arm & Hand Flow
        const isLeft = Math.random() > 0.5;
        const t = Math.random();
        const th = Math.random() * Math.PI * 2;
        const r = 0.05 + Math.random() * 0.02;
        lx = (isLeft ? -0.22 : 0.22) + r * Math.cos(th);
        ly = 1.42 - t * 0.54;
        lz = r * Math.sin(th);
        colChoice = cIce;
      } else {
        // Leg & Foot Flow
        const isLeft = Math.random() > 0.5;
        const t = Math.random();
        const th = Math.random() * Math.PI * 2;
        const r = 0.07 + Math.random() * 0.02;
        lx = (isLeft ? -0.11 : 0.11) + r * Math.cos(th);
        ly = 0.88 - t * 0.84;
        lz = r * Math.sin(th);
        colChoice = cSapphire;
      }

      pos[i * 3 + 0] = lx;
      pos[i * 3 + 1] = ly;
      pos[i * 3 + 2] = lz;

      col[i * 3 + 0] = colChoice.r;
      col[i * 3 + 1] = colChoice.g;
      col[i * 3 + 2] = colChoice.b;
    }

    return [pos, col];
  }, []);

  // ══════════════════════════════════════════════════════════════════════════════
  // 2. PROCEDURAL INVERSE KINEMATICS & PHYSICS ENGINE (useFrame @ 60 FPS)
  // ══════════════════════════════════════════════════════════════════════════════
  useFrame(({ clock }, delta) => {
    const t = clock.getElapsedTime();
    const dt = Math.min(delta, 0.1);

    // ── A. Movement Velocity & Speed Calculation ──
    const vx = velocity.vx || 0;
    const vy = velocity.vy || 0; // vy in 2D is vz in 3D
    const speed = Math.sqrt(vx * vx + vy * vy);

    // ── B. Real-Time Spatial Collision Check & Position Correction ──
    const correctionState = positionCorrectionEngine.update(rawThreeX, rawThreeZ, dt);
    const [smoothedX, smoothedZ] = correctionState.smoothedPosition;

    // ── C. Inverse Kinematics Controller (Seating, Standing, Walking, Running) ──
    const ik = humanIKController.computeIK(activity, speed, t, dt);

    // Apply smoothed grounded position or chair-aligned seating position
    let finalX = smoothedX;
    let finalZ = smoothedZ;

    if (ik.targetWorldPosition && activity === 'Sitting') {
      finalX = ik.targetWorldPosition[0];
      finalZ = ik.targetWorldPosition[1];
    }

    if (avatarGroupRef.current) {
      avatarGroupRef.current.position.set(finalX, 0, finalZ);
    }

    if (correctionState.status !== collisionStatus) {
      setCollisionStatus(correctionState.status);
      setNearestObstacle(correctionState.nearestObstacleName);
    }

    // ── D. Dynamic Orientation (Yaw Rotation) ──
    if (ik.targetYaw !== undefined && activity === 'Sitting') {
      const targetYaw = ik.targetYaw;
      let diff = targetYaw - currentYawRef.current;
      while (diff < -Math.PI) diff += Math.PI * 2;
      while (diff > Math.PI) diff -= Math.PI * 2;
      currentYawRef.current += diff * 0.20;
    } else if (speed > 0.05) {
      const steering = obstacleAvoidanceSteering.computeSteering(
        [smoothedX, smoothedZ],
        [rawThreeX + vx * 0.5, rawThreeZ + vy * 0.5]
      );
      const targetYaw = steering.targetYaw;

      let diff = targetYaw - currentYawRef.current;
      while (diff < -Math.PI) diff += Math.PI * 2;
      while (diff > Math.PI) diff -= Math.PI * 2;
      currentYawRef.current += diff * 0.15;
    }

    if (bodyRootRef.current) {
      bodyRootRef.current.rotation.y = currentYawRef.current;
    }

    if (bodyRootRef.current) {
      bodyRootRef.current.position.y = ik.pelvisYOffset;
      bodyRootRef.current.rotation.x = ik.pelvisRotationX;
      bodyRootRef.current.rotation.z = ik.pelvisRotationZ;
    }

    if (chestRef.current) {
      chestRef.current.scale.set(1.0, ik.chestScaleY, 1.0);
    }

    if (leftThighRef.current) leftThighRef.current.rotation.x = ik.leftThighRotX;
    if (rightThighRef.current) rightThighRef.current.rotation.x = ik.rightThighRotX;
    if (leftCalfRef.current) leftCalfRef.current.rotation.x = ik.leftCalfRotX;
    if (rightCalfRef.current) rightCalfRef.current.rotation.x = ik.rightCalfRotX;
    if (leftArmRef.current) leftArmRef.current.rotation.x = ik.leftArmRotX;
    if (rightArmRef.current) rightArmRef.current.rotation.x = ik.rightArmRotX;
    if (leftForearmRef.current) leftForearmRef.current.rotation.x = ik.leftForearmRotX;
    if (rightForearmRef.current) rightForearmRef.current.rotation.x = ik.rightForearmRotX;

    // ── D. Volumetric Particle Shimmer & Multi-State Floor Rings ──
    if (cloudRef.current) {
      const mat = cloudRef.current.material as THREE.PointsMaterial;
      mat.size = 0.016 + Math.sin(t * 3.5) * 0.002;
    }

    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.9;
    }

    if (auraRef.current) {
      const auraScale = 1.0 + Math.sin(t * 2.5) * 0.06;
      auraRef.current.scale.set(auraScale, 1.0, auraScale);
    }

    // Dynamic Multi-State Ring Color Update (Always positive green/cyan for verified/corrected)
    const ringColor =
      collisionStatus === 'SAFE'
        ? '#10B981' // Emerald Green for Valid Safe Zone
        : collisionStatus === 'AVOIDING_OBSTACLE'
        ? '#F59E0B' // Amber for Warning / Avoiding
        : '#06B6D4'; // Cyan for Verified / Refined

    if (ringMatRef.current) {
      ringMatRef.current.color.set(ringColor);
    }
    if (auraMatRef.current) {
      auraMatRef.current.color.set(ringColor);
    }
  });

  const confOpacity = Math.min(0.95, Math.max(0.6, confidence));

  // ══════════════════════════════════════════════════════════════════════════════
  // 3. HIGH-END VOLUMETRIC DIGITAL HUMAN PHYSICAL MATERIALS
  // ══════════════════════════════════════════════════════════════════════════════
  const volumetricBodyMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#032030',
        emissive: primaryColor,
        emissiveIntensity: renderingMode === 'production' ? 0.65 : 0.45,
        roughness: 0.25,
        metalness: 0.55,
        transparent: true,
        opacity: renderingMode === 'production' ? 0.88 : 0.60,
        side: THREE.DoubleSide,
      }),
    [primaryColor, renderingMode]
  );

  const volumetricAccentMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#063B54',
        emissive: accentColor,
        emissiveIntensity: 0.80,
        roughness: 0.20,
        metalness: 0.60,
        transparent: true,
        opacity: 0.90,
      }),
    [accentColor]
  );

  const internalSkeletonMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#FFFFFF',
        emissive: '#00F0FF',
        emissiveIntensity: 3.5,
        roughness: 0.1,
      }),
    []
  );

  const boneConnectorMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#7DF9FF',
        emissive: '#0080FF',
        emissiveIntensity: 2.0,
        roughness: 0.2,
      }),
    []
  );

  const showSkeleton = renderingMode === 'research' || renderingMode === 'debug';
  const showParticles = renderingMode === 'research' || renderingMode === 'debug';
  const showDebugVectors = renderingMode === 'debug';

  // Format positive, non-alarming status message
  const statusLabel =
    collisionStatus === 'SAFE'
      ? 'OCCUPANCY VERIFIED'
      : collisionStatus === 'AVOIDING_OBSTACLE'
      ? `AVOIDING: ${nearestObstacle.split(' ')[0].toUpperCase()}`
      : 'LOCALIZATION REFINED';

  return (
    <group ref={avatarGroupRef} scale={[scale, scale, scale]}>
      {/* ══════════════════════════════════════════════════════════════════
          LAYER 1: GROUND OCCUPANCY RING (Green = Verified, Amber = Avoiding)
         ══════════════════════════════════════════════════════════════════ */}
      {/* Concentric Rotating Outer Tracking Ring */}
      <mesh ref={ringRef} position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.48, 64]} />
        <meshBasicMaterial ref={ringMatRef} color="#10B981" transparent opacity={confOpacity * 0.85} side={THREE.DoubleSide} />
      </mesh>

      {/* Outer Breathing Aura Ring */}
      <mesh ref={auraRef} position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.54, 0.58, 64]} />
        <meshBasicMaterial ref={auraMatRef} color="#10B981" transparent opacity={0.3} side={THREE.DoubleSide} />
      </mesh>

      {/* Internal Radar Target Disc */}
      <mesh position={[0, 0.005, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.42, 48]} />
        <meshBasicMaterial color={primaryColor} transparent opacity={0.08} side={THREE.DoubleSide} />
      </mesh>

      {/* ─── FLOATING TACTICAL STATUS BADGE (Positive Green/Cyan) ─── */}
      {showCollisionStatus && collisionStatus !== 'SAFE' && (
        <Html position={[0, 1.95, 0]} center distanceFactor={10} zIndexRange={[100, 0]}>
          <div
            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase border whitespace-nowrap shadow-lg backdrop-blur-md transition-colors ${
              collisionStatus === 'AVOIDING_OBSTACLE'
                ? 'bg-amber-950/80 text-amber-300 border-amber-500/60 shadow-amber-500/20'
                : 'bg-cyan-950/80 text-cyan-300 border-cyan-500/60 shadow-cyan-500/20'
            }`}
          >
            {collisionStatus === 'AVOIDING_OBSTACLE' ? `⚡ ${statusLabel}` : `🛡️ ${statusLabel}`}
          </div>
        </Html>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          LAYER 2: FULL VOLUMETRIC DIGITAL HUMAN RECONSTRUCTION MESH
         ══════════════════════════════════════════════════════════════════ */}
      <group ref={bodyRootRef}>
        {/* ─── A. HEAD & CRANIUM (Volumetric Anatomical Head) ─── */}
        <group ref={headRef} position={[0, 1.62, 0]}>
          {/* Volumetric Cranium */}
          <mesh position={[0, 0, 0]} material={volumetricBodyMaterial}>
            <sphereGeometry args={[0.118, 24, 24]} />
          </mesh>
          {/* Facial Plane / Jaw Contour */}
          <mesh position={[0, -0.04, 0.045]} material={volumetricBodyMaterial}>
            <boxGeometry args={[0.11, 0.10, 0.085]} />
          </mesh>
          {/* Internal Skull Node (Research/Debug Mode Only) */}
          {showSkeleton && (
            <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
              <sphereGeometry args={[0.040, 16, 16]} />
            </mesh>
          )}
        </group>

        {/* ─── B. NECK (Volumetric Neck Cylinder) ─── */}
        <mesh position={[0, 1.48, 0]} material={volumetricBodyMaterial}>
          <cylinderGeometry args={[0.055, 0.065, 0.12, 16]} />
        </mesh>
        {showSkeleton && (
          <mesh position={[0, 1.48, 0]} material={internalSkeletonMaterial}>
            <sphereGeometry args={[0.024, 12, 12]} />
          </mesh>
        )}

        {/* ─── C. UPPER TORSO / CHEST & RIBCAGE (Volumetric Torso Mass) ─── */}
        <group ref={chestRef} position={[0, 1.32, 0]}>
          <mesh position={[0, 0, 0]} material={volumetricBodyMaterial}>
            <boxGeometry args={[0.36, 0.26, 0.20]} />
          </mesh>
          {/* Chest Sternum Accent */}
          <mesh position={[0, 0.02, 0.095]} material={volumetricAccentMaterial}>
            <boxGeometry args={[0.12, 0.18, 0.02]} />
          </mesh>
          {showSkeleton && (
            <>
              <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
                <sphereGeometry args={[0.038, 16, 16]} />
              </mesh>
              <mesh position={[0, 0, 0]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.012, 0.012, 0.24, 8]} />
              </mesh>
            </>
          )}
        </group>

        {/* ─── D. MID-TORSO / ABDOMEN (Volumetric Core) ─── */}
        <mesh position={[0, 1.12, 0]} material={volumetricBodyMaterial}>
          <cylinderGeometry args={[0.145, 0.135, 0.18, 18]} />
        </mesh>
        {showSkeleton && (
          <mesh position={[0, 1.12, 0]} material={internalSkeletonMaterial}>
            <sphereGeometry args={[0.030, 12, 12]} />
          </mesh>
        )}

        {/* ─── E. PELVIS & HIP GIRDLE (Volumetric Pelvis) ─── */}
        <group position={[0, 0.95, 0]}>
          <mesh position={[0, 0, 0]} material={volumetricBodyMaterial}>
            <boxGeometry args={[0.32, 0.18, 0.19]} />
          </mesh>
          {showSkeleton && (
            <>
              <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
                <sphereGeometry args={[0.040, 16, 16]} />
              </mesh>
              <mesh position={[0, -0.02, 0]} rotation={[0, 0, Math.PI / 2]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.014, 0.014, 0.24, 8]} />
              </mesh>
            </>
          )}
        </group>

        {/* ─── F. LEFT ARM & HAND ASSEMBLY ─── */}
        <group position={[-0.20, 1.42, 0]}>
          {/* Deltoid Cap */}
          <mesh position={[0, 0, 0]} material={volumetricBodyMaterial}>
            <sphereGeometry args={[0.072, 16, 16]} />
          </mesh>
          {showSkeleton && (
            <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
              <sphereGeometry args={[0.032, 12, 12]} />
            </mesh>
          )}

          <group ref={leftArmRef}>
            {/* Upper Arm / Bicep */}
            <mesh position={[-0.03, -0.14, 0]} material={volumetricBodyMaterial}>
              <cylinderGeometry args={[0.052, 0.044, 0.26, 16]} />
            </mesh>
            {showSkeleton && (
              <mesh position={[-0.03, -0.14, 0]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.01, 0.01, 0.24, 6]} />
              </mesh>
            )}

            <group position={[-0.05, -0.28, 0]}>
              {/* Elbow Joint */}
              <mesh material={volumetricBodyMaterial}>
                <sphereGeometry args={[0.048, 14, 14]} />
              </mesh>
              {showSkeleton && (
                <mesh material={internalSkeletonMaterial}>
                  <sphereGeometry args={[0.028, 12, 12]} />
                </mesh>
              )}

              <group ref={leftForearmRef}>
                {/* Forearm */}
                <mesh position={[0, -0.13, 0]} material={volumetricBodyMaterial}>
                  <cylinderGeometry args={[0.044, 0.036, 0.24, 16]} />
                </mesh>
                {showSkeleton && (
                  <mesh position={[0, -0.13, 0]} material={boneConnectorMaterial}>
                    <cylinderGeometry args={[0.009, 0.009, 0.22, 6]} />
                  </mesh>
                )}

                {/* Hand */}
                <group position={[0, -0.26, 0]}>
                  <mesh material={volumetricBodyMaterial}>
                    <boxGeometry args={[0.065, 0.08, 0.03]} />
                  </mesh>
                  {showSkeleton && (
                    <mesh material={internalSkeletonMaterial}>
                      <sphereGeometry args={[0.02, 10, 10]} />
                    </mesh>
                  )}
                </group>
              </group>
            </group>
          </group>
        </group>

        {/* ─── G. RIGHT ARM & HAND ASSEMBLY ─── */}
        <group position={[0.20, 1.42, 0]}>
          <mesh position={[0, 0, 0]} material={volumetricBodyMaterial}>
            <sphereGeometry args={[0.072, 16, 16]} />
          </mesh>
          {showSkeleton && (
            <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
              <sphereGeometry args={[0.032, 12, 12]} />
            </mesh>
          )}

          <group ref={rightArmRef}>
            <mesh position={[0.03, -0.14, 0]} material={volumetricBodyMaterial}>
              <cylinderGeometry args={[0.052, 0.044, 0.26, 16]} />
            </mesh>
            {showSkeleton && (
              <mesh position={[0.03, -0.14, 0]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.01, 0.01, 0.24, 6]} />
              </mesh>
            )}

            <group position={[0.05, -0.28, 0]}>
              <mesh material={volumetricBodyMaterial}>
                <sphereGeometry args={[0.048, 14, 14]} />
              </mesh>
              {showSkeleton && (
                <mesh material={internalSkeletonMaterial}>
                  <sphereGeometry args={[0.028, 12, 12]} />
                </mesh>
              )}

              <group ref={rightForearmRef}>
                <mesh position={[0, -0.13, 0]} material={volumetricBodyMaterial}>
                  <cylinderGeometry args={[0.044, 0.036, 0.24, 16]} />
                </mesh>
                {showSkeleton && (
                  <mesh position={[0, -0.13, 0]} material={boneConnectorMaterial}>
                    <cylinderGeometry args={[0.009, 0.009, 0.22, 6]} />
                  </mesh>
                )}

                <group position={[0, -0.26, 0]}>
                  <mesh material={volumetricBodyMaterial}>
                    <boxGeometry args={[0.065, 0.08, 0.03]} />
                  </mesh>
                  {showSkeleton && (
                    <mesh material={internalSkeletonMaterial}>
                      <sphereGeometry args={[0.02, 10, 10]} />
                    </mesh>
                  )}
                </group>
              </group>
            </group>
          </group>
        </group>

        {/* ─── H. LEFT LEG & FOOT ASSEMBLY (Grounded at y=0) ─── */}
        <group position={[-0.11, 0.88, 0]}>
          {showSkeleton && (
            <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
              <sphereGeometry args={[0.036, 12, 12]} />
            </mesh>
          )}

          <group ref={leftThighRef}>
            {/* Muscular Thigh */}
            <mesh position={[0, -0.20, 0]} material={volumetricBodyMaterial}>
              <cylinderGeometry args={[0.082, 0.064, 0.38, 16]} />
            </mesh>
            {showSkeleton && (
              <mesh position={[0, -0.20, 0]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.012, 0.012, 0.36, 6]} />
              </mesh>
            )}

            <group position={[0, -0.40, 0]}>
              {/* Knee / Patella */}
              <mesh material={volumetricBodyMaterial}>
                <sphereGeometry args={[0.064, 16, 16]} />
              </mesh>
              {showSkeleton && (
                <mesh material={internalSkeletonMaterial}>
                  <sphereGeometry args={[0.032, 12, 12]} />
                </mesh>
              )}

              <group ref={leftCalfRef}>
                {/* Calf & Shin */}
                <mesh position={[0, -0.20, 0]} material={volumetricBodyMaterial}>
                  <cylinderGeometry args={[0.064, 0.048, 0.38, 16]} />
                </mesh>
                {showSkeleton && (
                  <mesh position={[0, -0.20, 0]} material={boneConnectorMaterial}>
                    <cylinderGeometry args={[0.011, 0.011, 0.36, 6]} />
                  </mesh>
                )}

                {/* Grounded Foot Sole */}
                <group position={[0, -0.42, 0.05]}>
                  <mesh position={[0, 0.03, 0.03]} material={volumetricBodyMaterial}>
                    <boxGeometry args={[0.09, 0.06, 0.20]} />
                  </mesh>
                  {showSkeleton && (
                    <mesh position={[0, 0.06, -0.05]} material={internalSkeletonMaterial}>
                      <sphereGeometry args={[0.026, 10, 10]} />
                    </mesh>
                  )}
                </group>
              </group>
            </group>
          </group>
        </group>

        {/* ─── I. RIGHT LEG & FOOT ASSEMBLY (Grounded at y=0) ─── */}
        <group position={[0.11, 0.88, 0]}>
          {showSkeleton && (
            <mesh position={[0, 0, 0]} material={internalSkeletonMaterial}>
              <sphereGeometry args={[0.036, 12, 12]} />
            </mesh>
          )}

          <group ref={rightThighRef}>
            <mesh position={[0, -0.20, 0]} material={volumetricBodyMaterial}>
              <cylinderGeometry args={[0.082, 0.064, 0.38, 16]} />
            </mesh>
            {showSkeleton && (
              <mesh position={[0, -0.20, 0]} material={boneConnectorMaterial}>
                <cylinderGeometry args={[0.012, 0.012, 0.36, 6]} />
              </mesh>
            )}

            <group position={[0, -0.40, 0]}>
              <mesh material={volumetricBodyMaterial}>
                <sphereGeometry args={[0.064, 16, 16]} />
              </mesh>
              {showSkeleton && (
                <mesh material={internalSkeletonMaterial}>
                  <sphereGeometry args={[0.032, 12, 12]} />
                </mesh>
              )}

              <group ref={rightCalfRef}>
                <mesh position={[0, -0.20, 0]} material={volumetricBodyMaterial}>
                  <cylinderGeometry args={[0.064, 0.048, 0.38, 16]} />
                </mesh>
                {showSkeleton && (
                  <mesh position={[0, -0.20, 0]} material={boneConnectorMaterial}>
                    <cylinderGeometry args={[0.011, 0.011, 0.36, 6]} />
                  </mesh>
                )}

                <group position={[0, -0.42, 0.05]}>
                  <mesh position={[0, 0.03, 0.03]} material={volumetricBodyMaterial}>
                    <boxGeometry args={[0.09, 0.06, 0.20]} />
                  </mesh>
                  {showSkeleton && (
                    <mesh position={[0, 0.06, -0.05]} material={internalSkeletonMaterial}>
                      <sphereGeometry args={[0.026, 10, 10]} />
                    </mesh>
                  )}
                </group>
              </group>
            </group>
          </group>
        </group>
      </group>

      {/* ══════════════════════════════════════════════════════════════════
          LAYER 3: CSI ENERGY PARTICLE HALO (Research & Debug Modes Only, max 35% opacity)
         ══════════════════════════════════════════════════════════════════ */}
      {showParticles && (
        <points ref={cloudRef}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[particlePositions, 3]} />
            <bufferAttribute attach="attributes-color" args={[particleColors, 3]} />
          </bufferGeometry>
          <pointsMaterial
            size={0.016}
            vertexColors
            transparent
            opacity={0.30}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </points>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          LAYER 4: MOTION PREDICTION & VELOCITY VECTOR (Debug Mode Only)
         ══════════════════════════════════════════════════════════════════ */}
      {showDebugVectors && (
        <group position={[0, 1.05, 0]}>
          <mesh position={[0.2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.008, 0.008, 0.4, 6]} />
            <meshBasicMaterial color={primaryColor} transparent opacity={0.65} />
          </mesh>
        </group>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          LAYER 5: VOLUMETRIC AURA FIELD (Subtle Cinematic Lighting)
         ══════════════════════════════════════════════════════════════════ */}
      <pointLight position={[0, 1.1, 0]} intensity={2.2} color={primaryColor} distance={3.8} />
      <pointLight position={[0, 1.6, 0.2]} intensity={1.2} color={accentColor} distance={2.2} />
    </group>
  );
};
