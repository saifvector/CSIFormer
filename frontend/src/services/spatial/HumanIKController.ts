// ══════════════════════════════════════════════════════════════════════════════
// CSIFORMER INVERSE KINEMATICS (IK) CONTROLLER
// Analytical Posture, Foot Grounding & Furniture-Aligned Seating Engine
// ══════════════════════════════════════════════════════════════════════════════

export interface IKJointRotations {
  pelvisYOffset: number;
  pelvisRotationX: number;
  pelvisRotationZ: number;
  leftThighRotX: number;
  rightThighRotX: number;
  leftCalfRotX: number;
  rightCalfRotX: number;
  leftArmRotX: number;
  rightArmRotX: number;
  leftForearmRotX: number;
  rightForearmRotX: number;
  chestScaleY: number;
  targetWorldPosition?: [number, number]; // [x, z] in Three.js coordinates
  targetYaw?: number;                     // Target orientation in radians
}

export class HumanIKController {
  // Smooth state transition tracking
  private sitProgress = 0.0;
  private fallProgress = 0.0;

  // Chair reference geometry in Three.js coordinates
  // Chair base at [-1.8, 0, 2.3], seat surface at y=0.46, backrest at z=2.48
  public readonly chairSeatedPos: [number, number] = [-1.80, 2.34];
  public readonly chairFacingYaw = Math.PI; // 180° - faces desk at Z=1.5
  public readonly seatHeight = 0.44;

  /**
   * Computes smooth anatomical joint transformations and foot grounding based on activity state.
   */
  public computeIK(
    activity: string,
    speed: number,
    time: number,
    dt = 0.033
  ): IKJointRotations {
    const isSittingTarget = activity === 'Sitting';
    const isFallingTarget = activity === 'Falling' || activity === 'Lying Down';

    // 1. Smoothly interpolate posture progress factors (6.0 blend speed)
    const sitSpeed = 5.0;
    this.sitProgress += ((isSittingTarget ? 1.0 : 0.0) - this.sitProgress) * Math.min(1.0, dt * sitSpeed);
    this.fallProgress += ((isFallingTarget ? 1.0 : 0.0) - this.fallProgress) * Math.min(1.0, dt * sitSpeed);

    const isWalking = activity === 'Walking' || (speed > 0.12 && !isSittingTarget && !isFallingTarget);
    const isRunning = activity === 'Running' || (speed > 1.3 && !isSittingTarget && !isFallingTarget);

    const breath = Math.sin(time * 2.2) * 0.018;

    // ── CASE A: SEATED POSE IK (Hips on seat, knees 90°, feet flat on floor, back on backrest) ──
    if (this.sitProgress > 0.01) {
      const sp = this.sitProgress;
      // Pelvis lowers by 0.42m so base of pelvis rests on seat at y=0.46m
      const seatedPelvisY = -0.42 * sp;
      const seatedThigh = (-Math.PI / 2.0) * sp;
      const seatedCalf = (Math.PI / 2.0) * sp;
      const seatedArm = -0.36 * sp;
      const seatedForearm = -0.65 * sp;

      return {
        pelvisYOffset: seatedPelvisY + breath * 0.15 * (1.0 - sp),
        pelvisRotationX: 0.04 * sp, // Slight natural backrest incline
        pelvisRotationZ: 0.0,
        leftThighRotX: seatedThigh,
        rightThighRotX: seatedThigh,
        leftCalfRotX: seatedCalf,
        rightCalfRotX: seatedCalf,
        leftArmRotX: seatedArm,
        rightArmRotX: seatedArm,
        leftForearmRotX: seatedForearm,
        rightForearmRotX: seatedForearm,
        chestScaleY: 1.0 + breath * 0.25,
        targetWorldPosition: this.chairSeatedPos,
        targetYaw: this.chairFacingYaw,
      };
    }

    // ── CASE B: FALLING / PRONE POSE IK ──
    if (this.fallProgress > 0.01) {
      const fp = this.fallProgress;
      return {
        pelvisYOffset: -0.72 * fp,
        pelvisRotationX: (Math.PI / 2.1) * fp,
        pelvisRotationZ: 0.2 * Math.sin(time * 3.0) * fp,
        leftThighRotX: 0.2 * fp,
        rightThighRotX: -0.15 * fp,
        leftCalfRotX: 0.0,
        rightCalfRotX: 0.0,
        leftArmRotX: -0.8 * fp,
        rightArmRotX: 0.6 * fp,
        leftForearmRotX: 0.0,
        rightForearmRotX: 0.0,
        chestScaleY: 1.0,
      };
    }

    // ── CASE C: RUNNING GAIT IK ──
    if (isRunning) {
      const runFreq = 6.5;
      const runPhase = time * runFreq;
      const legStride = Math.sin(runPhase) * 0.85;
      const armStride = Math.sin(runPhase + Math.PI) * 0.75;
      const bounce = Math.abs(Math.sin(runPhase)) * 0.065;

      return {
        pelvisYOffset: bounce,
        pelvisRotationX: 0.14, // Forward lean
        pelvisRotationZ: Math.sin(runPhase) * 0.04,
        leftThighRotX: legStride,
        rightThighRotX: -legStride,
        leftCalfRotX: Math.max(0, -legStride * 1.3),
        rightCalfRotX: Math.max(0, legStride * 1.3),
        leftArmRotX: armStride,
        rightArmRotX: -armStride,
        leftForearmRotX: -0.60,
        rightForearmRotX: -0.60,
        chestScaleY: 1.0,
      };
    }

    // ── CASE D: WALKING GAIT IK ──
    if (isWalking) {
      const walkFreq = 3.8;
      const walkPhase = time * walkFreq;
      const legStride = Math.sin(walkPhase) * 0.48;
      const armStride = Math.sin(walkPhase + Math.PI) * 0.38;
      const bounce = Math.abs(Math.sin(walkPhase)) * 0.032;

      return {
        pelvisYOffset: bounce,
        pelvisRotationX: 0.04,
        pelvisRotationZ: Math.sin(walkPhase) * 0.025,
        leftThighRotX: legStride,
        rightThighRotX: -legStride,
        leftCalfRotX: Math.max(0, -legStride * 1.1),
        rightCalfRotX: Math.max(0, legStride * 1.1),
        leftArmRotX: armStride,
        rightArmRotX: -armStride,
        leftForearmRotX: -0.25,
        rightForearmRotX: -0.25,
        chestScaleY: 1.0,
      };
    }

    // ── CASE E: STANDING / IDLE IK (Natural Ground Contact) ──
    return {
      pelvisYOffset: breath * 0.3,
      pelvisRotationX: 0.0,
      pelvisRotationZ: Math.sin(time * 1.2) * 0.01,
      leftThighRotX: 0.0,
      rightThighRotX: 0.0,
      leftCalfRotX: 0.0,
      rightCalfRotX: 0.0,
      leftArmRotX: Math.sin(time * 1.5) * 0.03,
      rightArmRotX: -Math.sin(time * 1.5) * 0.03,
      leftForearmRotX: -0.05,
      rightForearmRotX: -0.05,
      chestScaleY: 1.0 + breath * 0.4,
    };
  }

  public reset(): void {
    this.sitProgress = 0.0;
    this.fallProgress = 0.0;
  }
}

export const humanIKController = new HumanIKController();
