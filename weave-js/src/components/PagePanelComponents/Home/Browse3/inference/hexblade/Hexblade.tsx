import {
  CameraControls,
  OrbitControls,
  OrthographicCamera,
  PerspectiveCamera,
} from '@react-three/drei';
import {Canvas} from '@react-three/fiber';
import {Bloom, EffectComposer, N8AO} from '@react-three/postprocessing';
import React, {useEffect, useRef, useState} from 'react';
import * as THREE from 'three';

import {Hexagon} from './Hexagon';

export type DataPoint = Record<string, any>;
export type Data = DataPoint[];

type HexbladeProps = {
  data: Data;
};

export const Hexblade = ({data}: HexbladeProps) => {
  // Move to prop
  const [cameraMode, setCameraMode] = useState<'p' | 'o'>('o');

  const refCameraP = useRef<THREE.PerspectiveCamera>(null!);
  const refCameraO = useRef<THREE.OrthographicCamera>(null!);
  const refCameraControl = useRef<CameraControls>(null!);
  const [canvasSize, setCanvasSize] = useState({width: 800, height: 600});
  const canvasContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateCanvasSize = () => {
      if (canvasContainerRef.current) {
        const rect = canvasContainerRef.current.getBoundingClientRect();
        setCanvasSize({width: rect.width, height: rect.height});
      }
    };

    updateCanvasSize();
    window.addEventListener('resize', updateCanvasSize);
    return () => window.removeEventListener('resize', updateCanvasSize);
  }, []);

  return (
    <div ref={canvasContainerRef} className="h-full w-full">
      <Canvas
        orthographic={cameraMode === 'o'}
        gl={{alpha: true, antialias: true}}
        style={{touchAction: 'none'}}>
        <color attach="background" args={['#f0f0f0']} />
        <Hexagon position={[0, 0, 0]} color="#4a90e2" />
        <Hexagon position={[10, 0, 0]} color="#FF0000" />
        <Hexagon position={[20, 0, 0]} color="#4a90e2" />
        <Hexagon position={[30, 0, 0]} color="#4a90e2" glowing={false} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        {/* <EffectComposer enableNormalPass={false}>
          <N8AO aoRadius={0.5} intensity={1} />
          <Bloom
            luminanceThreshold={0.1}
            intensity={2.5}
            levels={9}
            mipmapBlur
            radius={0.8}
          />
        </EffectComposer> */}
        <PerspectiveCamera
          ref={refCameraP}
          makeDefault={cameraMode === 'p'}
          fov={75}
          near={0.1}
          far={1000}
          position={[0, 0, 50]}
        />
        <OrthographicCamera
          ref={refCameraO}
          makeDefault={cameraMode === 'o'}
          near={0.1}
          far={1000}
          position={[0, 0, 50]}
          zoom={5}
        />
        {cameraMode === 'p' ? (
          <OrbitControls />
        ) : (
          <CameraControls
            ref={refCameraControl}
            dollySpeed={0.5}
            dollyToCursor={true}
            smoothTime={0.1}
            minDistance={10}
            maxDistance={1000}
            // mouseButtons={{
            //   left: 2,
            //   wheel: 16,
            // }}
          />
        )}
      </Canvas>
    </div>
  );
};
