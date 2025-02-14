import {Box, Drawer, DrawerProps} from '@mui/material';
import React, {useCallback, useEffect, useState} from 'react';

interface ResizableDrawerProps
  extends Omit<DrawerProps, 'onClose' | 'anchor' | 'title'> {
  onClose: () => void;
  defaultWidth?: number;
  title?: React.ReactNode;
  headerContent?: React.ReactNode;
  setWidth?: (width: number) => void;
}

export const ResizableDrawer: React.FC<ResizableDrawerProps> = ({
  children,
  defaultWidth = 400,
  title,
  headerContent,
  onClose,
  setWidth: externalSetWidth,
  ...drawerProps
}) => {
  const [internalWidth, setInternalWidth] = useState(defaultWidth);
  const [isResizing, setIsResizing] = useState(false);
  // 73px = 57px sidebar + 16px padding
  const [maxAllowedWidth, setMaxAllowedWidth] = useState(
    window.innerWidth - 73
  );

  const setWidthValue = useCallback(
    (newWidth: number) => {
      setInternalWidth(newWidth);
      externalSetWidth?.(newWidth);
    },
    [externalSetWidth]
  );

  useEffect(() => {
    if (externalSetWidth) {
      setInternalWidth(defaultWidth);
    }
  }, [defaultWidth, externalSetWidth]);

  useEffect(() => {
    const handleResize = () => {
      const newMaxWidth = window.innerWidth - 73;
      setMaxAllowedWidth(newMaxWidth);
      if (internalWidth > newMaxWidth) {
        setWidthValue(newMaxWidth);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [internalWidth, setWidthValue]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsResizing(true);
    e.preventDefault();
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) {
        return;
      }

      const newWidth = window.innerWidth - e.clientX;
      if (newWidth >= 120 && newWidth <= maxAllowedWidth) {
        setWidthValue(newWidth);
      }
    },
    [isResizing, maxAllowedWidth, setWidthValue]
  );

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  return (
    <Drawer
      {...drawerProps}
      anchor="right"
      onClose={onClose}
      sx={{
        '& .MuiDrawer-paper': {
          mt: '60px',
          width: `${internalWidth}px`,
          position: 'fixed',
          maxWidth: `${maxAllowedWidth}px`,
          minWidth: '538px',
          maxHeight: 'calc(100vh - 60px)',
          height: 'calc(100vh - 60px)',
        },
      }}>
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          left: -4,
          width: 8,
          cursor: 'ew-resize',
          '&:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.1)',
          },
        }}
        onMouseDown={handleMouseDown}
      />
      {children}
    </Drawer>
  );
};
