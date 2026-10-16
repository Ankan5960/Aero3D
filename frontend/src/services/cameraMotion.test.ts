import { describe, expect, it } from 'vitest';
import { PerspectiveCamera, Vector3 } from 'three';
import { applyMotion } from './cameraMotion';

const limits = { minDistance: 1, maxDistance: 50 };
const motion = (over: Partial<Parameters<typeof applyMotion>[2]>) => ({
  rotateX: 0, rotateY: 0, panX: 0, panY: 0, zoom: 1, ...over,
});
function setup() {
  const camera = new PerspectiveCamera(45, 1.5, 0.1, 100);
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  camera.updateMatrixWorld();
  return { camera, target: new Vector3() };
}

describe('applyMotion', () => {
  it('rotating right drags the model right (camera azimuth decreases, distance preserved)', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ rotateX: 0.05 }), limits);
    expect(camera.position.x).toBeLessThan(0);
    expect(camera.position.distanceTo(target)).toBeCloseTo(10);
  });

  it('rotating down tilts the camera up', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ rotateY: 0.05 }), limits);
    expect(camera.position.y).toBeGreaterThan(0);
  });

  it('clamps polar angle (no flip over the pole)', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ rotateY: -5 }), limits);
    expect(camera.position.y).toBeLessThan(10.0001);
    expect(Number.isFinite(camera.position.x)).toBe(true);
  });

  it('zoom > 1 moves closer and respects distance limits', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ zoom: 2 }), limits);
    expect(camera.position.distanceTo(target)).toBeCloseTo(5);
    applyMotion(camera, target, motion({ zoom: 1000 }), limits);
    expect(camera.position.distanceTo(target)).toBeCloseTo(1);
    applyMotion(camera, target, motion({ zoom: 0.0001 }), limits);
    expect(camera.position.distanceTo(target)).toBeCloseTo(50);
  });

  it('ignores invalid zoom factors', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ zoom: Number.NaN }), limits);
    applyMotion(camera, target, motion({ zoom: -1 }), limits);
    expect(camera.position.distanceTo(target)).toBeCloseTo(10);
  });

  it('pan moves camera and target together, preserving distance', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({ panX: 0.1, panY: 0.1 }), limits);
    expect(target.x).toBeLessThan(0); // drag right => view shifts so scene moves right
    expect(target.y).toBeGreaterThan(0);
    expect(camera.position.distanceTo(target)).toBeCloseTo(10);
  });

  it('zero motion is a no-op', () => {
    const { camera, target } = setup();
    applyMotion(camera, target, motion({}), limits);
    expect(camera.position.toArray()).toEqual([0, 0, 10]);
  });
});
