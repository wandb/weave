import React, {Suspense, useEffect, useMemo, useRef, useState} from 'react';

// import {Canvas, useFrame} from '@react-three/fiber';
// import {OrbitControls} from '@react-three/drei';
// import * as THREE from 'three';
// Import the models data
import modelsData from './modelsFinal.json';

interface Model {
  id: string;
  label: string;
  provider?: string;
  parameterCountTotal?: number;
  modalities?: string[];
}

interface HexagonProps {
  position: [number, number, number];
  color: string;
  label: string;
  index: number;
  size?: number;
}

/**
 * Custom hexagon geometry for 3D visualization.
 */
const HexagonGeometry = ({size = 1}: {size?: number}) => {
  const geometry = useMemo(() => {
    // Use any to bypass the type issue temporarily
    const THREE_any = THREE as any;
    const geo = new THREE_any.BufferGeometry();
    const vertices = [];
    const indices = [];

    // Create hexagon shape
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3;
      const x = Math.cos(angle) * size;
      const y = Math.sin(angle) * size;
      vertices.push(x, y, 0);
    }

    // Create faces
    for (let i = 1; i < 5; i++) {
      indices.push(0, i, i + 1);
    }

    geo.setAttribute(
      'position',
      new THREE_any.Float32BufferAttribute(vertices, 3)
    );
    geo.setIndex(indices);
    geo.computeVertexNormals();

    return geo;
  }, [size]);

  return geometry;
};

/**
 * Individual hexagon component with glow effect and animation.
 */
const Hexagon = ({position, color, label, index, size = 1}: HexagonProps) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometry = HexagonGeometry({size});

  useFrame(state => {
    if (meshRef.current) {
      // Gentle floating animation
      meshRef.current.position.y =
        position[1] + Math.sin(state.clock.elapsedTime + index) * 0.2;
      // Gentle rotation
      meshRef.current.rotation.z = state.clock.elapsedTime * 0.1 + index * 0.3;
    }
  });

  return (
    <group position={position}>
      {/* Outer glow effect */}
      <mesh>
        <primitive object={geometry} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.2}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Middle glow */}
      <mesh scale={0.8}>
        <primitive object={geometry} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.4}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Main hexagon */}
      <mesh ref={meshRef} scale={0.6}>
        <primitive object={geometry} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.9}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
};

/**
 * Main 3D scene component that arranges hexagons in a spiral pattern.
 */
const Scene = ({models}: {models: Model[]}) => {
  const colors = useMemo(
    () => [
      '#00ff88', // Green
      '#0088ff', // Blue
      '#ff0088', // Pink
      '#ff8800', // Orange
      '#8800ff', // Purple
      '#ffff00', // Yellow
      '#00ffff', // Cyan
      '#ff00ff', // Magenta
      '#88ff00', // Lime
      '#ff8800', // Orange
    ],
    []
  );

  const hexagonPositions = useMemo(() => {
    const positions: [number, number, number][] = [];
    const radius = 12;
    const heightVariation = 3;

    // Arrange hexagons in a spiral pattern
    models.forEach((model, index) => {
      const angle = (index * 2 * Math.PI) / Math.max(models.length / 2, 1);
      const spiralRadius = radius + index * 0.5; // Gradually increase radius
      const x = Math.cos(angle) * spiralRadius;
      const z = Math.sin(angle) * spiralRadius;
      const y = Math.sin(index * 0.7) * heightVariation; // Vary height for visual interest
      positions.push([x, y, z]);
    });

    return positions;
  }, [models]);

  return (
    <>
      {/* Ambient light for overall illumination */}
      <ambientLight intensity={0.3} />

      {/* Point lights for each hexagon */}
      {hexagonPositions.map((position, index) => (
        <pointLight
          key={`light-${index}`}
          position={position}
          color={colors[index % colors.length]}
          intensity={1.2}
          distance={4}
        />
      ))}

      {/* Hexagons */}
      {models.map((model, index) => {
        const size = model.parameterCountTotal
          ? Math.min(Math.max(model.parameterCountTotal / 1000000000, 0.5), 2) // Scale by parameter count
          : 1;

        return (
          <Hexagon
            key={model.id}
            position={hexagonPositions[index]}
            color={colors[index % colors.length]}
            label={model.label || model.id}
            index={index}
            size={size}
          />
        );
      })}

      {/* Camera controls */}
      {/* <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        autoRotate={true}
        autoRotateSpeed={0.3}
        minDistance={10}
        maxDistance={50}
        maxPolarAngle={Math.PI / 1.5}
      /> */}
    </>
  );
};

/**
 * Three.js visualization component with error boundary.
 */
const ThreeJSVisualization = ({models}: {models: Model[]}) => {
  return (
    <div className="h-96 w-full">
      {/* <Canvas
        camera={{position: [0, 10, 25], fov: 60}}
        style={{background: 'transparent'}}
        gl={{antialias: true, alpha: true}}>
        <Scene models={models} />
      </Canvas> */}
    </div>
  );
};

/**
 * A 3D visualization of models as glowing hexagons using Three.js.
 * Falls back to 2D visualization if Three.js is not available.
 *
 * @returns JSX element containing the 3D visualization
 *
 * @example
 * ```tsx
 * <ModelVisualization />
 * ```
 */
export const ModelVisualization = () => {
  //   const [use3D, setUse3D] = useState(true);
  //   const [threeJSLoaded, setThreeJSLoaded] = useState(false);

  //   useEffect(() => {
  //     // Check if Three.js is available
  //     const checkThreeJS = async () => {
  //       try {
  //         await import('three');
  //         setThreeJSLoaded(true);
  //       } catch (error) {
  //         console.warn('Three.js not available, using 2D fallback');
  //         setUse3D(false);
  //       }
  //     };

  //     checkThreeJS();
  //   }, []);

  //   // Extract models from the JSON data
  //   const models = modelsData.models || [];

  //   // Generate colors for models
  //   const colors = [
  //     '#00ff88', // Green
  //     '#0088ff', // Blue
  //     '#ff0088', // Pink
  //     '#ff8800', // Orange
  //     '#8800ff', // Purple
  //     '#ffff00', // Yellow
  //     '#00ffff', // Cyan
  //     '#ff00ff', // Magenta
  //     '#88ff00', // Lime
  //     '#ff8800', // Orange
  //   ];

  //   if (use3D && threeJSLoaded) {
  //     return (
  //       <div className="bg-black h-96 w-full overflow-hidden rounded-lg p-4">
  //         <div className="mb-4 text-center text-white">
  //           <h3 className="text-xl font-semibold">3D Model Visualization</h3>
  //           <p className="text-gray-400 text-sm">
  //             {models.length} models available
  //           </p>
  //         </div>

  //         <Suspense
  //           fallback={
  //             <div className="flex h-80 items-center justify-center">
  //               <div className="text-center text-white">
  //                 <div className="mb-2">Loading 3D visualization...</div>
  //                 <div className="text-gray-400 text-sm">
  //                   This may take a moment
  //                 </div>
  //               </div>
  //             </div>
  //           }>
  //           <ThreeJSVisualization models={models} />
  //         </Suspense>

  //         <div className="text-gray-400 mt-4 text-center text-sm">
  //           <p>
  //             Click and drag to rotate • Scroll to zoom • Click on a hexagon to
  //             view model details
  //           </p>
  //         </div>
  //       </div>
  //     );
  //   }

  // 2D Fallback
  return (
    <div className="bg-black h-96 w-full overflow-hidden rounded-lg p-4">
      Hi
    </div>
  );
};
