import React, {useCallback, useEffect, useState} from 'react';

interface ResizableHandleProps {
  containerRef: React.RefObject<HTMLElement>;
  onWidthChange: (widthPx: number) => void;
  minWidth?: number;
  maxWidthOffset?: number; // How much space to leave on the right
  className?: string;
  style?: React.CSSProperties;
}

export const ResizableHandle: React.FC<ResizableHandleProps> = ({
  containerRef,
  onWidthChange,
  minWidth = 300,
  maxWidthOffset = 200,
  className = '',
  style = {},
}) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    e.preventDefault();
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;

      const container = containerRef.current;
      if (!container) return;

      const containerRect = container.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;

      // Set min and max width constraints
      const maxWidth = containerRect.width - maxWidthOffset;
      const constrainedWidth = Math.max(minWidth, Math.min(newWidth, maxWidth));

      // Pass the pixel width directly
      onWidthChange(constrainedWidth);
    },
    [isDragging, containerRef, minWidth, maxWidthOffset, onWidthChange]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
    return () => {};
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const defaultStyle: React.CSSProperties = {
    width: '3px',
    cursor: 'col-resize',
    position: 'relative',
    background: '#e5e7eb',
    ...style,
  };

  return (
    <div
      className={className}
      style={defaultStyle}
      onMouseDown={handleMouseDown}></div>
  );
};
