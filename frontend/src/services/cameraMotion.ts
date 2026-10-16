import { PerspectiveCamera, Spherical, Vector3 } from 'three';
import type { PendingMotion } from './gestureController';

export interface MotionLimits {
  minDistance: number;
  maxDistance: number;
}

const ROTATE_GAIN = Math.PI * 2; // a full-width hand sweep = one revolution (at sensitivity 1)
const EPS = 1e-4;
const _offset = new Vector3();
const _right = new Vector3();
const _up = new Vector3();
const _spherical = new Spherical();

/**
 * Apply gesture motion to a perspective camera orbiting `target` (mutates both).
 * Semantics mimic dragging the model: moving the hand right turns/pans the model to the right.
 */
export function applyMotion(
  camera: PerspectiveCamera,
  target: Vector3,
  motion: PendingMotion,
  limits: MotionLimits,
): void {
  _offset.copy(camera.position).sub(target);

  if (motion.rotateX !== 0 || motion.rotateY !== 0) {
    _spherical.setFromVector3(_offset);
    _spherical.theta -= motion.rotateX * ROTATE_GAIN;
    _spherical.phi = Math.min(Math.PI - EPS, Math.max(EPS, _spherical.phi - motion.rotateY * ROTATE_GAIN));
    _offset.setFromSpherical(_spherical);
  }

  if (motion.zoom !== 1 && Number.isFinite(motion.zoom) && motion.zoom > 0) {
    const dist = Math.min(limits.maxDistance, Math.max(limits.minDistance, _offset.length() / motion.zoom));
    _offset.setLength(dist);
  }

  camera.position.copy(target).add(_offset);
  camera.lookAt(target);
  camera.updateMatrixWorld();

  if (motion.panX !== 0 || motion.panY !== 0) {
    const dist = _offset.length();
    const visibleHeight = 2 * dist * Math.tan((camera.fov * Math.PI) / 360);
    const visibleWidth = visibleHeight * camera.aspect;
    _right.setFromMatrixColumn(camera.matrix, 0);
    _up.setFromMatrixColumn(camera.matrix, 1);
    // Dragging right moves the scene right => camera moves left; dragging down => camera moves up.
    const move = _right.multiplyScalar(-motion.panX * visibleWidth).addScaledVector(_up, motion.panY * visibleHeight);
    camera.position.add(move);
    target.add(move);
  }
}
