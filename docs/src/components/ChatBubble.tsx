import React, { useState, useRef, useEffect } from 'react';
import styles from './ChatBubble.module.css';

export default function ChatBubble(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const frameRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const startPosRef = useRef({ x: 0, y: 0, width: 0, height: 0 });

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    if (frameRef.current) {
      setIsDragging(true);
      document.body.style.cursor = 'nwse-resize';
      document.body.style.userSelect = 'none';
      if (iframeRef.current) {
        iframeRef.current.style.pointerEvents = 'none';
      }
      startPosRef.current = {
        x: e.clientX,
        y: e.clientY,
        width: frameRef.current.offsetWidth,
        height: frameRef.current.offsetHeight,
      };
    }
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging && frameRef.current) {
        const dx = e.clientX - startPosRef.current.x;
        const dy = e.clientY - startPosRef.current.y;
        const newWidth = Math.max(300, startPosRef.current.width - dx);
        const newHeight = Math.max(400, startPosRef.current.height - dy);
        frameRef.current.style.width = `${newWidth}px`;
        frameRef.current.style.height = `${newHeight}px`;
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (iframeRef.current) {
        iframeRef.current.style.pointerEvents = '';
      }
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      // Also handle the case where mouse leaves the window
      window.addEventListener('mouseleave', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      window.removeEventListener('mouseleave', handleMouseUp);
    };
  }, [isDragging]);

  return (
    <div className={styles.chatContainer}>
      {isOpen && (
        <div className={`${styles.chatFrame} ${isDragging ? styles.dragging : ''}`} ref={frameRef}>
          <div className={styles.resizeHandle} onMouseDown={handleMouseDown} />
          {isLoading && (
            <div className={styles.loadingContainer}>
              <div className={styles.spinner} />
              <div className={styles.loadingText}>Loading chat...</div>
            </div>
          )}
          <iframe
            ref={iframeRef}
            src="http://localhost:5173/chat"
            title="Chat"
            className={styles.iframe}
            onLoad={() => setIsLoading(false)}
          />
        </div>
      )}
      <button
        className={styles.chatButton}
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) setIsLoading(true);
        }}
        aria-label={isOpen ? "Close chat" : "Open chat"}
      >
        {isOpen ? (
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M18 6L6 18" />
            <path d="M6 6l12 12" />
          </svg>
        ) : (
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}
      </button>
    </div>
  );
} 