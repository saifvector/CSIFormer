// ══════════════════════════════════════════════════════════════════════════════
// CSIFORMER POSITION CORRECTION ENGINE
// Real-Time Smooth Obstacle Penetration Resolver & Occupancy State Machine
// ══════════════════════════════════════════════════════════════════════════════

import { collisionManager } from './CollisionManager';

export type OccupancyStatus = 'SAFE' | 'AVOIDING_OBSTACLE' | 'POSITION_CORRECTED' | 'BLOCKED';

export interface CorrectionState {
  smoothedPosition: [number, number]; // [x, z] in Three.js coordinates
  rawPosition: [number, number];      // [x, z] in Three.js coordinates
  status: OccupancyStatus;
  nearestObstacleName: string;
  distanceToObstacle: number;
  penetrationDepth: number;
  isCorrecting: boolean;
  correctionOffset: [number, number];
}

export class PositionCorrectionEngine {
  private currentX = 0;
  private currentZ = 0;
  private isInitialized = false;

  // Smoothing parameter (Spring-damper / EMA responsiveness)
  public smoothingFactor = 12.0;

  /**
   * Evaluates raw CSI coordinates and smoothly glides the avatar to valid walkable space.
   * @param rawThreeX Three.js raw X coordinate [-5..5]
   * @param rawThreeZ Three.js raw Z coordinate [-4..4]
   * @param dt Delta time in seconds (~0.033s for 30Hz)
   */
  public update(rawThreeX: number, rawThreeZ: number, dt = 0.033): CorrectionState {
    if (!this.isInitialized) {
      // First frame initialization: project if starting inside obstacle
      const initialCheck = collisionManager.testPointCollision(rawThreeX, rawThreeZ);
      this.currentX = initialCheck.isColliding ? initialCheck.correctedPosition[0] : rawThreeX;
      this.currentZ = initialCheck.isColliding ? initialCheck.correctedPosition[1] : rawThreeZ;
      this.isInitialized = true;
    }

    // 1. Collision check on raw predicted position
    const rawCheck = collisionManager.testPointCollision(rawThreeX, rawThreeZ);

    // 2. Determine target destination (projected to safe boundary if raw is colliding)
    const targetX = rawCheck.isColliding ? rawCheck.correctedPosition[0] : rawThreeX;
    const targetZ = rawCheck.isColliding ? rawCheck.correctedPosition[1] : rawThreeZ;

    // 3. Smooth Critically-Damped Spring-Damper / EMA Interpolation
    // dPos = (target - current) * (1 - exp(-smooth * dt))
    const blend = 1.0 - Math.exp(-this.smoothingFactor * Math.min(dt, 0.1));
    this.currentX += (targetX - this.currentX) * blend;
    this.currentZ += (targetZ - this.currentZ) * blend;

    // 4. Hard safety guard: guarantee current position NEVER penetrates any obstacle
    const safetyCheck = collisionManager.testPointCollision(this.currentX, this.currentZ);
    if (safetyCheck.isColliding) {
      this.currentX = safetyCheck.correctedPosition[0];
      this.currentZ = safetyCheck.correctedPosition[1];
    }

    // 5. Determine high-level Occupancy & Collision Status
    let status: OccupancyStatus = 'SAFE';
    if (rawCheck.isColliding && rawCheck.penetrationDepth > 0.08) {
      status = rawCheck.nearestCollider?.isRestricted ? 'BLOCKED' : 'POSITION_CORRECTED';
    } else if (rawCheck.isColliding || safetyCheck.closestDistance < 0.35) {
      status = 'AVOIDING_OBSTACLE';
    }

    const nearestName = (rawCheck.nearestCollider || safetyCheck.nearestCollider)?.name ?? 'None';
    const nearestDist = Math.max(0, safetyCheck.closestDistance);

    return {
      smoothedPosition: [this.currentX, this.currentZ],
      rawPosition: [rawThreeX, rawThreeZ],
      status,
      nearestObstacleName: nearestName,
      distanceToObstacle: Number(nearestDist.toFixed(2)),
      penetrationDepth: Number(rawCheck.penetrationDepth.toFixed(2)),
      isCorrecting: rawCheck.isColliding,
      correctionOffset: [this.currentX - rawThreeX, this.currentZ - rawThreeZ],
    };
  }

  public reset(x = 0, z = 0): void {
    this.currentX = x;
    this.currentZ = z;
    this.isInitialized = false;
  }
}

export const positionCorrectionEngine = new PositionCorrectionEngine();
