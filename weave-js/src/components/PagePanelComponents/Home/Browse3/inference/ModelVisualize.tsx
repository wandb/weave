import {
  CameraControls,
  OrbitControls,
  OrthographicCamera,
  PerspectiveCamera,
  Text,
} from '@react-three/drei';
import {Canvas, ThreeElements, useFrame} from '@react-three/fiber';
import React, {useEffect, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';
import * as THREE from 'three';

import {Button} from '../../../../Button';
import {Hexblade} from './hexblade/Hexblade';
import {MODEL_INFO} from './modelInfo';

type ModelVisualizeProps = {
  modelIds: string[];
  propertyIds: string[];
};

// function ModelMark(
//   props: ThreeElements['mesh'] & {size?: number; cameraMode?: 'p' | 'o'}
// ) {
//   const meshRef = useRef<THREE.Mesh>(null!);
//   const [hovered, setHover] = useState(false);
//   const [active, setActive] = useState(false);
//   // useFrame((state, delta) => (meshRef.current.rotation.x += delta));

//   // Calculate scale based on size and camera mode
//   const baseScale = active ? 1.5 : 1;
//   const sizeScale = props.size
//     ? props.cameraMode === 'o'
//       ? Math.sqrt(props.size)
//       : Math.cbrt(props.size)
//     : 1;
//   const finalScale = baseScale * sizeScale;

//   return (
//     <mesh
//       {...props}
//       ref={meshRef}
//       scale={finalScale}
//       onClick={event => setActive(!active)}
//       onPointerOver={event => setHover(true)}
//       onPointerOut={event => setHover(false)}>
//       <sphereGeometry args={[1, 32, 32]} />
//       <meshStandardMaterial
//         color={hovered ? 'hotpink' : '#2f74c0'}
//         emissive={hovered ? '#ff69b4' : '#2f74c0'}
//         emissiveIntensity={0.1}
//         transparent
//         opacity={0.8}
//         depthWrite={true}
//         depthTest={true}
//         roughness={0.3}
//         metalness={0.1}
//         side={THREE.DoubleSide}
//       />
//     </mesh>
//   );
// }

// function Axes({
//   xLabel,
//   yLabel,
//   zLabel,
//   maxX,
//   maxY,
//   maxZ,
// }: {
//   xLabel: string;
//   yLabel: string;
//   zLabel: string;
//   maxX: number;
//   maxY: number;
//   maxZ: number;
// }) {
//   const xLabelRef = useRef<THREE.Group>(null!);
//   const yLabelRef = useRef<THREE.Group>(null!);
//   const zLabelRef = useRef<THREE.Group>(null!);

//   // Format labels for better readability
//   const formatLabel = (label: string) => {
//     return label
//       .replace(/([A-Z])/g, ' $1') // Add space before capital letters
//       .replace(/^./, str => str.toUpperCase()) // Capitalize first letter
//       .replace(/\s+/g, ' ') // Remove extra spaces
//       .trim();
//   };

//   // Generate tick values at reasonable intervals
//   const generateTicks = (maxValue: number) => {
//     if (maxValue <= 0) return [0];

//     const power = Math.floor(Math.log10(maxValue));
//     const base = Math.pow(10, power);
//     const step = base / 5; // Aim for ~5 ticks

//     const ticks = [];
//     for (let i = 0; i <= maxValue; i += step) {
//       if (i <= maxValue) {
//         ticks.push(Math.round(i));
//       }
//     }

//     // Always include the max value
//     if (!ticks.includes(maxValue)) {
//       ticks.push(maxValue);
//     }

//     return ticks.sort((a, b) => a - b);
//   };

//   const xTicks = generateTicks(maxX);
//   const yTicks = generateTicks(maxY);
//   const zTicks = generateTicks(maxZ);

//   // Scale factors to map data values to visual space
//   const scaleFactor = 1000; // Map data values to visual coordinates
//   const xScale = scaleFactor / maxX;
//   const yScale = scaleFactor / maxY;
//   const zScale = scaleFactor / maxZ;

//   // Make labels always face the camera
//   useFrame(state => {
//     if (xLabelRef.current) {
//       xLabelRef.current.lookAt(state.camera.position);
//     }
//     if (yLabelRef.current) {
//       yLabelRef.current.lookAt(state.camera.position);
//     }
//     if (zLabelRef.current) {
//       zLabelRef.current.lookAt(state.camera.position);
//     }
//   });

//   return (
//     <group>
//       {/* X-axis (red) - horizontal line */}
//       <line>
//         <bufferGeometry>
//           <bufferAttribute
//             attach="attributes-position"
//             count={2}
//             array={new Float32Array([0, 0, 0, scaleFactor, 0, 0])}
//             itemSize={3}
//           />
//         </bufferGeometry>
//         <lineBasicMaterial color="#ff4444" linewidth={3} />
//       </line>
//       <group ref={xLabelRef} position={[scaleFactor + 20, 0, 0]}>
//         <Text
//           fontSize={12}
//           color="#ff4444"
//           anchorX="left"
//           anchorY="middle"
//           maxWidth={120}>
//           {formatLabel(xLabel)}
//         </Text>
//       </group>

//       {/* Y-axis (green) - vertical line */}
//       <line>
//         <bufferGeometry>
//           <bufferAttribute
//             attach="attributes-position"
//             count={2}
//             array={new Float32Array([0, 0, 0, 0, scaleFactor, 0])}
//             itemSize={3}
//           />
//         </bufferGeometry>
//         <lineBasicMaterial color="#44ff44" linewidth={3} />
//       </line>
//       <group ref={yLabelRef} position={[0, scaleFactor + 20, 0]}>
//         <Text
//           fontSize={12}
//           color="#44ff44"
//           anchorX="center"
//           anchorY="bottom"
//           maxWidth={120}>
//           {formatLabel(yLabel)}
//         </Text>
//       </group>

//       {/* Z-axis (blue) - depth line */}
//       <line>
//         <bufferGeometry>
//           <bufferAttribute
//             attach="attributes-position"
//             count={2}
//             array={new Float32Array([0, 0, 0, 0, 0, scaleFactor])}
//             itemSize={3}
//           />
//         </bufferGeometry>
//         <lineBasicMaterial color="#4444ff" linewidth={3} />
//       </line>
//       <group ref={zLabelRef} position={[0, 0, scaleFactor + 20]}>
//         <Text
//           fontSize={12}
//           color="#4444ff"
//           anchorX="center"
//           anchorY="middle"
//           maxWidth={120}>
//           {formatLabel(zLabel)}
//         </Text>
//       </group>

//       {/* Origin point */}
//       <mesh position={[0, 0, 0]}>
//         <sphereGeometry args={[3, 16, 16]} />
//         <meshStandardMaterial color="#ffffff" />
//       </mesh>

//       {/* X-axis tick marks with labels */}
//       {xTicks.map(tick => {
//         const visualPos = tick * xScale;
//         return (
//           <group key={`x-tick-${tick}`}>
//             <line>
//               <bufferGeometry>
//                 <bufferAttribute
//                   attach="attributes-position"
//                   count={2}
//                   array={new Float32Array([visualPos, -5, 0, visualPos, 5, 0])}
//                   itemSize={3}
//                 />
//               </bufferGeometry>
//               <lineBasicMaterial color="#ff4444" linewidth={1} />
//             </line>
//             <group position={[visualPos, -15, 0]}>
//               <Text fontSize={8} color="#ff4444" anchorX="center" anchorY="top">
//                 {tick.toLocaleString()}
//               </Text>
//             </group>
//           </group>
//         );
//       })}

//       {/* Y-axis tick marks with labels */}
//       {yTicks.map(tick => {
//         const visualPos = tick * yScale;
//         return (
//           <group key={`y-tick-${tick}`}>
//             <line>
//               <bufferGeometry>
//                 <bufferAttribute
//                   attach="attributes-position"
//                   count={2}
//                   array={new Float32Array([-5, visualPos, 0, 5, visualPos, 0])}
//                   itemSize={3}
//                 />
//               </bufferGeometry>
//               <lineBasicMaterial color="#44ff44" linewidth={1} />
//             </line>
//             <group position={[-15, visualPos, 0]}>
//               <Text
//                 fontSize={8}
//                 color="#44ff44"
//                 anchorX="right"
//                 anchorY="middle">
//                 {tick.toLocaleString()}
//               </Text>
//             </group>
//           </group>
//         );
//       })}

//       {/* Z-axis tick marks with labels */}
//       {zTicks.map(tick => {
//         const visualPos = tick * zScale;
//         return (
//           <group key={`z-tick-${tick}`}>
//             <line>
//               <bufferGeometry>
//                 <bufferAttribute
//                   attach="attributes-position"
//                   count={2}
//                   array={new Float32Array([-5, 0, visualPos, 5, 0, visualPos])}
//                   itemSize={3}
//                 />
//               </bufferGeometry>
//               <lineBasicMaterial color="#4444ff" linewidth={1} />
//             </line>
//             <group position={[0, -15, visualPos]}>
//               <Text fontSize={8} color="#4444ff" anchorX="center" anchorY="top">
//                 {tick.toLocaleString()}
//               </Text>
//             </group>
//           </group>
//         );
//       })}
//     </group>
//   );
// }

// type Slot = {};

// const SLOTS: Slot[] = [
//   {
//     id: 'chartType',
//     label: 'Chart Type',
//   },
//   {
//     id: 'x',
//     label: 'X',
//   },
//   {
//     id: 'y',
//     label: 'Y',
//   },
//   {
//     id: 'z',
//     label: 'Z',
//   },
//   {
//     id: 'color',
//     label: 'Color',
//   },
//   {
//     id: 'opacity',
//     label: 'Opacity',
//   },
//   {
//     id: 'size',
//     label: 'Size',
//   },
//   {
//     id: 'sort',
//     label: 'Sort',
//   },
//   {
//     id: 'sortOrder',
//     label: 'Sort Order',
//   },
// ];

export const ModelVisualize = ({
  modelIds,
  propertyIds,
}: ModelVisualizeProps) => {
  const history = useHistory();

  // const [cameraMode, setCameraMode] = useState<'p' | 'o'>('p');
  // const refCameraP = useRef<THREE.PerspectiveCamera>(null!);
  // const refCameraO = useRef<THREE.OrthographicCamera>(null!);
  // const refCameraControl = useRef<CameraControls>(null!);
  // const [canvasSize, setCanvasSize] = useState({width: 800, height: 600});
  // const canvasContainerRef = useRef<HTMLDivElement>(null);

  // Track canvas size changes
  // useEffect(() => {
  //   const updateCanvasSize = () => {
  //     if (canvasContainerRef.current) {
  //       const rect = canvasContainerRef.current.getBoundingClientRect();
  //       setCanvasSize({width: rect.width, height: rect.height});
  //     }
  //   };

  //   updateCanvasSize();
  //   window.addEventListener('resize', updateCanvasSize);
  //   return () => window.removeEventListener('resize', updateCanvasSize);
  // }, []);

  // const propX = 'priceCentsPerBillionTokensInput';
  // const propY = 'priceCentsPerBillionTokensOutput';
  // const propZ = 'priceCentsPerBillionTokensInput';
  // const propSize = 'priceCentsPerBillionTokensOutput';

  // // Calculate the range of input prices, output prices, and context windows for scaling
  // const xValues = MODEL_INFO.models.map(m => m[propX] ?? 0);
  // const yValues = MODEL_INFO.models.map(m => m[propY] ?? 0);
  // const zValues = MODEL_INFO.models.map(m => m[propZ] ?? 0);

  // const minValueX = Math.min(...xValues);
  // const maxValueX = Math.max(...xValues);
  // const minValueY = Math.min(...yValues);
  // const maxValueY = Math.max(...yValues);
  // const minValueZ = Math.min(...zValues);
  // const maxValueZ = Math.max(...zValues);

  // // Debug: Log the ranges to understand the data distribution
  // console.log('X property range:', {min: minValueX, max: maxValueX});
  // console.log('Y property range:', {
  //   min: minValueY,
  //   max: maxValueY,
  // });
  // console.log('Z property range:', {
  //   min: minValueZ,
  //   max: maxValueZ,
  // });

  // // Scale factors to map the data to a reasonable visualization range
  // // Use a larger range to spread cubes out more and prevent disappearing when zooming
  // const xScale = 1000 / (maxValueX - minValueX || 1);
  // const yScale = 1000 / (maxValueY - minValueY || 1);
  // const zScale = 1000 / (maxValueZ - minValueZ || 1);

  // // Calculate offsets to center the visualization
  // const xOffset = 0; // Center around origin
  // const yOffset = 0; // Center around origin
  // const zOffset = 0; // Center around origin

  // // Debug: Log canvas size and scaling
  // console.log('Canvas size:', canvasSize);
  // console.log('Scaling factors:', {xScale, yScale, zScale});
  // console.log('Offsets:', {xOffset, yOffset, zOffset});

  const data = MODEL_INFO.models;

  return (
    <div className="m-16 flex flex-col" style={{height: 'calc(100vh - 90px)'}}>
      <div className="mb-8 flex items-center justify-between">
        <div className="flex-1 text-xl font-semibold text-moon-800">
          Visualize models
        </div>
        <div className="flex gap-8">
          <Button
            size="large"
            icon="table"
            onClick={() => {
              history.push({
                pathname: '/inference-compare',
                search: window.location.search,
              });
            }}>
            Compare selected
          </Button>
        </div>
      </div>
      <div className="flex flex-1" style={{border: '1px solid red'}}>
        <Hexblade data={data} />
      </div>
    </div>
  );
};
