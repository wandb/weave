import React, {useCallback, useEffect, useState} from 'react';

interface ResizableDrawerProps {
  children: React.ReactNode;
  onClose: () => void;
  defaultWidth?: number;
  title?: React.ReactNode;
  headerContent?: React.ReactNode;
  setWidth?: (width: number) => void;
  marginTop?: number;
  open?: boolean;
  [key: string]: any; // For additional props like data-testid
}

export const ResizableDrawer: React.FC<ResizableDrawerProps> = ({
  children,
  defaultWidth = 400,
  headerContent,
  onClose,
  setWidth: externalSetWidth,
  marginTop = 60,
  open,
  ...otherProps
}) => {
  const [internalWidth, setInternalWidth] = useState(defaultWidth);
  const [isResizing, setIsResizing] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);
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

  // Handle open/close animations
  useEffect(() => {
    if (open) {
      setShouldRender(true);
      // Use requestAnimationFrame to ensure the DOM has updated
      requestAnimationFrame(() => {
        setIsVisible(true);
      });
    } else {
      setIsVisible(false);
      // Wait for animation to complete before unmounting
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, 300); // Match transition duration
      return () => clearTimeout(timer);
    }
  }, [open]);

  if (!shouldRender) {
    return null;
  }

  const drawerStyle: React.CSSProperties = {
    top: `${marginTop}px`,
    width: `${internalWidth}px`,
    maxWidth: `${maxAllowedWidth}px`,
    height: `calc(100vh - ${marginTop}px)`,
    maxHeight: `calc(100vh - ${marginTop}px)`,
    minWidth: '500px',
  };

  return (
    <div className="tw-style fixed inset-0 z-[1200]" {...otherProps}>
      <div
        className={`fixed inset-0 bg-moon-950 transition-opacity duration-300 ${
          isVisible ? 'opacity-50' : 'opacity-0'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={`fixed right-0 bg-white dark:bg-moon-950 shadow-deep overflow-hidden flex flex-col transition-transform duration-300 ease-out ${
          isVisible ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={drawerStyle}
        role="dialog"
        aria-modal="true">
        <div
          className="absolute top-0 bottom-0 -left-4 w-8 cursor-ew-resize hover:bg-moon-950 hover:bg-opacity-10 dark:hover:bg-moon-50 dark:hover:bg-opacity-10"
          onMouseDown={handleMouseDown}
          role="separator"
          aria-orientation="vertical"
        />
        {headerContent}
        {children}
      </div>
    </div>
  );
};
