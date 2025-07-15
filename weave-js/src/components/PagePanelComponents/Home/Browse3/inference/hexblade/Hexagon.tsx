import React from 'react';
import {useEffect, useRef} from 'react';
import * as THREE from 'three';

type HexagonProps = {
  position: [number, number, number];
  color: string;
  glowing?: boolean;
};

// Hexagon component that creates a 2D hexagon at the origin
export const Hexagon = ({position, color, glowing = true}: HexagonProps) => {
  const meshRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    if (meshRef.current) {
      // Create hexagon geometry
      const geometry = new THREE.BufferGeometry();
      const vertices = [];
      const indices = [];

      // Create hexagon vertices (6 points around a circle)
      //   const size = 5.77; // Make hexagon width 10 units (5.77 * 2 * cos(30°) = 10)
      const size = 5.7; // Make hexagon width 10 units (5.77 * 2 * cos(30°) = 10)
      for (let i = 0; i < 6; i++) {
        const angle = (i * Math.PI) / 3;
        const x = Math.cos(angle) * size;
        const y = Math.sin(angle) * size;
        vertices.push(x, y, 0);
      }

      // Create triangles (fan triangulation)
      for (let i = 1; i < 5; i++) {
        indices.push(0, i, i + 1);
      }
      indices.push(0, 5, 1); // Close the fan

      geometry.setAttribute(
        'position',
        new THREE.Float32BufferAttribute(vertices, 3)
      );
      geometry.setIndex(indices);
      geometry.computeVertexNormals();

      meshRef.current.geometry = geometry;
    }
  }, []);

  return (
    <mesh ref={meshRef} position={position} rotation={[0, 0, Math.PI / 2]}>
      {/* {glowing ? (
        <meshStandardMaterial
          color="#4a90e2"
          flatShading={true}
          emissive="#4a90e2"
          emissiveIntensity={0.3}
        />
      ) : (
      )} */}
      <meshBasicMaterial color={color} />
    </mesh>
  );
};
