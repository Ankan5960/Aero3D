import { useEffect, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Grid, OrbitControls } from '@react-three/drei';
import { Box3, Group, PerspectiveCamera, Vector3 } from 'three';
import type { ElementRef } from 'react';
import type { GestureController } from '../services/gestureController';
import { applyMotion, type MotionLimits } from '../services/cameraMotion';
import type { LoadedModel } from '../services/modelLoader';

interface ViewerProps {
  model: LoadedModel | null;
  controller: GestureController;
  /** Increment to restore the initial view. */
  resetToken: number;
  /** Increment to re-fit the model into view. */
  fitToken: number;
}

type ControlsImpl = ElementRef<typeof OrbitControls>;

interface ViewPose {
  position: Vector3;
  target: Vector3;
}

const VIEW_DIRECTION = new Vector3(1, 0.7, 1).normalize();

function ViewerScene({ model, controller, resetToken, fitToken }: ViewerProps) {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  const controlsRef = useRef<ControlsImpl>(null);
  const centerRef = useRef<Group>(null);
  const initialPose = useRef<ViewPose | null>(null);
  const limits = useRef<MotionLimits>({ minDistance: 0.1, maxDistance: 100 });

  // Fit the model (or demo mesh) in view whenever it changes or a re-fit is requested.
  useEffect(() => {
    const group = centerRef.current;
    const controls = controlsRef.current;
    if (!group || !controls) return;
    group.position.set(0, 0, 0);
    const box = new Box3().setFromObject(group);
    if (box.isEmpty()) return;
    const center = box.getCenter(new Vector3());
    group.position.sub(center);
    const radius = Math.max(box.getSize(new Vector3()).length() / 2, 1e-3);
    const dist = (radius / Math.sin((camera.fov * Math.PI) / 360)) * 1.15;
    camera.near = Math.max(radius / 100, 1e-4);
    camera.far = dist + radius * 100;
    camera.updateProjectionMatrix();
    camera.position.copy(VIEW_DIRECTION).multiplyScalar(dist);
    controls.target.set(0, 0, 0);
    controls.minDistance = radius * 0.05;
    controls.maxDistance = dist * 10;
    limits.current = { minDistance: controls.minDistance, maxDistance: controls.maxDistance };
    camera.lookAt(0, 0, 0);
    controls.update();
    initialPose.current = { position: camera.position.clone(), target: controls.target.clone() };
  }, [model, fitToken, camera]);

  // Restore the initial view.
  useEffect(() => {
    const pose = initialPose.current;
    const controls = controlsRef.current;
    if (resetToken === 0 || !pose || !controls) return;
    camera.position.copy(pose.position);
    controls.target.copy(pose.target);
    camera.lookAt(pose.target);
    controls.update();
  }, [resetToken, camera]);

  // High-frequency gesture motion is applied in the render loop, never through React state.
  useFrame(() => {
    const controls = controlsRef.current;
    const motion = controller.consume();
    if (!controls || !motion) return;
    applyMotion(camera, controls.target, motion, limits.current);
    controls.update();
  });

  return (
    <>
      <hemisphereLight args={['#bcd0ff', '#1a1030', 0.9]} />
      <directionalLight position={[5, 8, 6]} intensity={2.2} />
      <directionalLight position={[-6, -2, -4]} intensity={0.7} color="#8b5cf6" />
      <group ref={centerRef}>
        {model ? (
          <primitive object={model.object} />
        ) : (
          <mesh>
            <torusKnotGeometry args={[1, 0.34, 220, 36]} />
            <meshStandardMaterial color="#7dd3fc" metalness={0.55} roughness={0.25} />
          </mesh>
        )}
      </group>
      <Grid
        position={[0, -2.2, 0]}
        args={[40, 40]}
        cellSize={0.5}
        cellThickness={0.6}
        cellColor="#2a3358"
        sectionSize={2.5}
        sectionThickness={1.1}
        sectionColor="#39e1ff"
        fadeDistance={22}
        fadeStrength={1.6}
        infiniteGrid
      />
      <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.12} />
    </>
  );
}

export function ModelViewer(props: ViewerProps) {
  return (
    <Canvas
      className="viewer-canvas"
      camera={{ fov: 45, near: 0.01, far: 1000, position: [4, 3, 5] }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
      aria-label="3D model viewer. Drag to rotate, right-drag or two fingers to pan, scroll or pinch to zoom."
    >
      <ViewerScene {...props} />
    </Canvas>
  );
}
