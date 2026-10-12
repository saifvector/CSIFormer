// ══════════════════════════════════════════════════════════════════════════════
// CSIFORMER OBSTACLE AVOIDANCE STEERING ENGINE
// Artificial Potential Fields & Tangential Navigation Vector Steering
// ══════════════════════════════════════════════════════════════════════════════

import { collisionManager } from './CollisionManager';
import type { Collider } from './CollisionManager';

export interface SteeringResult {
  velocity: [number, number]; // [vx, vz]
  targetYaw: number;          // Angular heading in radians
  isAvoiding: boolean;
  activeObstacle: Collider | null;
}

export class ObstacleAvoidanceSteering {
  public maxSpeed = 1.2;          // m/s
  public influenceRadius = 0.85;  // Distance at which repulsion kicks in
  public kAtt = 1.8;              // Attractive force constant
  public kRep = 2.4;              // Repulsive force constant
  public kTan = 1.5;              // Tangential sweep force constant

  /**
   * Computes collision-free steering velocity and heading from current position to target.
   */
  public computeSteering(
    currentPos: [number, number],
    goalPos: [number, number],
    _currentVelocity?: [number, number]
  ): SteeringResult {
    const [cx, cz] = currentPos;
    const [gx, gz] = goalPos;

    // 1. Goal Attractive Force Vector
    const toGoalX = gx - cx;
    const toGoalZ = gz - cz;
    const goalDist = Math.sqrt(toGoalX * toGoalX + toGoalZ * toGoalZ);

    let fx = 0;
    let fz = 0;

    if (goalDist > 0.05) {
      fx += (toGoalX / goalDist) * this.kAtt;
      fz += (toGoalZ / goalDist) * this.kAtt;
    }

    // 2. Obstacle Repulsive & Tangential Sweep Forces
    let isAvoiding = false;
    let nearestObstacle: Collider | null = null;
    let minObstacleDist = Infinity;

    const colliders = collisionManager.getColliders();

    for (const col of colliders) {
      if (!col.enabled || col.type === 'ROOM_BOUNDS') continue;

      let obsX = 0;
      let obsZ = 0;
      let effectiveRadius = 0.5;

      if (col.type === 'BOX') {
        obsX = col.center[0];
        obsZ = col.center[2];
        effectiveRadius = Math.max(col.size[0], col.size[2]) * 0.55;
      } else if (col.type === 'CYLINDER' || col.type === 'SPHERE') {
        obsX = col.center[0];
        obsZ = col.center[2];
        effectiveRadius = col.radius;
      }

      const dx = cx - obsX;
      const dz = cz - obsZ;
      const dist = Math.sqrt(dx * dx + dz * dz);
      const clearance = dist - effectiveRadius;

      if (clearance < this.influenceRadius && dist > 0.01) {
        isAvoiding = true;
        if (clearance < minObstacleDist) {
          minObstacleDist = clearance;
          nearestObstacle = col;
        }

        const nx = dx / dist;
        const nz = dz / dist;

        // Repulsive force magnitude: F_rep = k_rep * (1/d - 1/d0) * (1/d^2)
        const dClamped = Math.max(clearance, 0.05);
        const repMag = this.kRep * (1.0 / dClamped - 1.0 / this.influenceRadius) * (1.0 / (dClamped * dClamped));

        fx += nx * Math.min(repMag, 8.0);
        fz += nz * Math.min(repMag, 8.0);

        // Tangential Force (Sweeps around obstacle clockwise or counter-clockwise toward goal)
        // Perpendicular normal: [-nz, nx]
        const cross = toGoalX * nz - toGoalZ * nx;
        const tanSign = cross >= 0 ? 1.0 : -1.0;
        const tanMag = this.kTan * Math.min(repMag * 0.6, 4.0);

        fx += -nz * tanSign * tanMag;
        fz += nx * tanSign * tanMag;
      }
    }

    // 3. Normalize & Scale Resulting Velocity
    const fMag = Math.sqrt(fx * fx + fz * fz);
    let vx = 0;
    let vz = 0;

    if (fMag > 0.01) {
      const speed = Math.min(this.maxSpeed, fMag * 0.5);
      vx = (fx / fMag) * speed;
      vz = (fz / fMag) * speed;
    }

    const targetYaw = Math.atan2(vx, vz);

    return {
      velocity: [vx, vz],
      targetYaw,
      isAvoiding,
      activeObstacle: nearestObstacle,
    };
  }
}

export const obstacleAvoidanceSteering = new ObstacleAvoidanceSteering();
