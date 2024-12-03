/**
 * A simple multi-line text editor component that mimics code editor styling.
 * Features auto-sizing, manual resize handle, and code-like formatting.
 *
 * Inspired by: weave-js/src/components/Form/TextField.tsx
 */

import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {useCallback, useEffect, useRef, useState} from 'react';

export const TextAreaSizes = {
  Medium: 'medium',
  Large: 'large',
} as const;
export type TextAreaSize = (typeof TextAreaSizes)[keyof typeof TextAreaSizes];

type TextAreaProps = {
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  onKeyDown?: (
    key: string,
    e: React.KeyboardEvent<HTMLTextAreaElement>
  ) => void;
  onBlur?: (value: string) => void;
  autoFocus?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  errorState?: boolean;
  maxLength?: number;
  maxRows?: number;
  dataTest?: string;
};

export const SimpleCodeLikeTextArea = ({
  placeholder,
  value,
  onChange,
  onKeyDown,
  onBlur,
  autoFocus,
  disabled,
  ariaLabel,
  errorState,
  maxLength,
  maxRows = 8,
  dataTest,
}: TextAreaProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isManuallyResized, setIsManuallyResized] = useState(false);
  const isDraggingRef = useRef(false);
  const initialHeightRef = useRef<number>(0);
  const initialMouseYRef = useRef<number>(0);

  // Automatically adjust height based on content
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (!textarea || isManuallyResized) {
      return;
    }

    textarea.style.height = 'auto';
    const lineHeight = parseInt(
      getComputedStyle(textarea).lineHeight || '20',
      10
    );
    const maxHeight = lineHeight * maxRows;
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${newHeight}px`;
  };

  useEffect(() => {
    adjustHeight();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, isManuallyResized]);

  // Handle resize drag start
  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    if (disabled) {
      return;
    }

    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    isDraggingRef.current = true;
    setIsManuallyResized(true);
    initialHeightRef.current = textarea.offsetHeight;
    initialMouseYRef.current = e.clientY;

    // Add event listeners for drag and release
    document.addEventListener('mousemove', handleResizeMove);
    document.addEventListener('mouseup', handleResizeEnd);
  };

  // Handle resize drag movement
  const handleResizeMove = useCallback((e: MouseEvent) => {
    if (!isDraggingRef.current || !textareaRef.current) {
      return;
    }

    const deltaY = e.clientY - initialMouseYRef.current;
    const newHeight = Math.max(80, initialHeightRef.current + deltaY); // Min height of 80px
    textareaRef.current.style.height = `${newHeight}px`;
  }, []);

  // Handle resize drag end
  const handleResizeEnd = useCallback(() => {
    isDraggingRef.current = false;
    document.removeEventListener('mousemove', handleResizeMove);
    document.removeEventListener('mouseup', handleResizeEnd);
  }, [handleResizeMove]);

  // Cleanup event listeners
  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleResizeMove);
      document.removeEventListener('mouseup', handleResizeEnd);
    };
  }, [handleResizeEnd, handleResizeMove]);

  // Double click handler to reset to auto-size
  const handleResizeDoubleClick = () => {
    setIsManuallyResized(false);
    adjustHeight();
  };

  const handleChange = onChange
    ? (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        onChange(e.target.value);
      }
    : undefined;
  const handleKeyDown = onKeyDown
    ? (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        onKeyDown(e.key, e);
      }
    : undefined;
  const handleBlur = onBlur
    ? (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        onBlur?.(e.target.value);
      }
    : undefined;

  return (
    <Tailwind style={{width: '100%'}}>
      <div
        className={classNames(
          'night-aware',
          'relative rounded-sm',
          'bg-white dark:bg-moon-900',
          'text-moon-800 dark:text-moon-200',
          'outline outline-1 outline-moon-250 dark:outline-moon-700',
          {
            'hover:outline-2 [&:hover:not(:focus-within)]:outline-[#83E4EB] dark:[&:hover:not(:focus-within)]:outline-teal-650':
              !errorState,
            'focus-within:outline-2 focus-within:outline-teal-400 dark:focus-within:outline-teal-600':
              !errorState,
            'outline-2 outline-red-450 dark:outline-red-550': errorState,
            'pointer-events-none opacity-50': disabled,
          }
        )}>
        <div className="relative flex w-full items-start rounded-sm">
          <textarea
            ref={textareaRef}
            className={classNames(
              'w-full flex-1 rounded-sm bg-inherit px-8 py-8',
              'appearance-none border-none',
              'focus:outline-none',
              'placeholder-moon-500',
              'dark:selection:bg-moon-650 dark:selection:text-moon-200',
              'resize-none',
              'overflow-y-auto',
              'font-mono',
              'whitespace-pre-wrap',
              'break-words',
              'text-sm'
            )}
            placeholder={placeholder}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            autoFocus={autoFocus}
            disabled={disabled}
            aria-label={ariaLabel}
            maxLength={maxLength}
            data-test={dataTest}
            rows={1}
          />

          {/* Resize Handle */}
          <div
            className={classNames(
              'absolute bottom-0 right-0',
              'h-24 w-24 cursor-se-resize',
              'flex items-end justify-end',
              'select-none',
              {'cursor-default': disabled}
            )}
            onMouseDown={handleResizeStart}
            onDoubleClick={handleResizeDoubleClick}
            title="Drag to resize. Double-click to reset.">
            <div
              className={classNames(
                'h-0 w-0',
                'border-l-[10px] border-l-transparent',
                'border-b-[10px]',
                'border-b-moon-400 dark:border-b-moon-600',
                'mb-2 mr-2'
              )}
            />
          </div>
        </div>
      </div>
    </Tailwind>
  );
};
