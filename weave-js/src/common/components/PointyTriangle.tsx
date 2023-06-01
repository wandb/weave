import React from 'react';
import ReactDOM from 'react-dom';
import styled from 'styled-components';

export type PointyTriangleDirection = 'top' | 'bottom' | 'left' | 'right';

function opposite(direction: PointyTriangleDirection) {
  switch (direction) {
    case 'top':
      return 'bottom';
    case 'bottom':
      return 'top';
    case 'left':
      return 'right';
    case 'right':
      return 'left';
  }
}

const PointyTriangleWrapper = styled.div<{
  direction: PointyTriangleDirection;
  size: number;
  left: number;
  top: number;
  color?: string;
}>`
  position: fixed;
  z-index: 999;
  top: ${props => props.top}px;
  left: ${props => props.left}px;
  border: ${props => props.size}px solid transparent;
  ${props => 'border-' + opposite(props.direction)}: none;
  ${props => 'border-' + props.direction}: ${props => props.size}px solid
    ${props => (props.color ? props.color : 'rgb(34, 34, 34)')};
`;

interface PointyTriangleProps {
  x: number;
  y: number;
  size: number;
  // This actually the opposite of the direction the triangle is pointing;
  // it's the direction it's positioned relative to its anchor.
  direction: PointyTriangleDirection;
  color?: string;
  noPortal?: boolean;
}

const PointyTriangle: React.FC<PointyTriangleProps> = props => {
  let left = Math.min(Math.max(props.x, 0), window.innerWidth);
  let top = Math.min(Math.max(props.y, 0), window.innerHeight);
  switch (props.direction) {
    case 'top':
      left -= props.size;
      top -= props.size;
      break;
    case 'bottom':
      left -= props.size;
      break;
    case 'left':
      left -= props.size;
      top -= props.size;
      break;
    case 'right':
      top -= props.size;
      break;
  }

  const content = (
    <PointyTriangleWrapper
      left={left}
      top={top}
      size={props.size}
      direction={props.direction}
      color={props.color}
    />
  );

  return props.noPortal
    ? content
    : ReactDOM.createPortal({content}, document.body);
};

export default PointyTriangle;
