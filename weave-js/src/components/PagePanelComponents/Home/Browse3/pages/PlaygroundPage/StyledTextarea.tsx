/**
 * A form multi-line text input.
 */
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {forwardRef} from 'react';

type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  autoGrow?: boolean;
  maxHeight?: string | number;
  reset?: boolean;
};

export const StyledTextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({className, autoGrow, maxHeight, reset, ...props}, ref) => {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    React.useEffect(() => {
      if (!autoGrow || !textareaRef.current) return;

      const adjustHeight = () => {
        const textarea = textareaRef.current;
        if (!textarea) return;
        
        // Disable resize when autoGrow is true
        textarea.style.resize = 'none';
        
        if (reset || textarea.value === '') {
          textarea.style.height = 'auto';
          return;
        }
        
        // Reset height to allow shrinking
        textarea.style.height = 'auto';
        const newHeight = textarea.scrollHeight;
        
        // Apply max height if specified
        if (maxHeight) {
          textarea.style.height = `${Math.min(newHeight, typeof maxHeight === 'string' ? parseInt(maxHeight) : maxHeight)}px`;
          textarea.style.overflowY = newHeight > (typeof maxHeight === 'string' ? parseInt(maxHeight) : maxHeight) ? 'auto' : 'hidden';
        } else {
          textarea.style.height = `${newHeight}px`;
          textarea.style.overflowY = 'hidden';
        }
      };

      const textarea = textareaRef.current;
      textarea.addEventListener('input', adjustHeight);
      adjustHeight(); // Initial adjustment

      return () => textarea.removeEventListener('input', adjustHeight);
    }, [autoGrow, maxHeight, reset]);

    return (
      <Tailwind style={{display: 'contents'}}>
        <textarea
          ref={(element) => {
            if (typeof ref === 'function') {
              ref(element);
            } else if (ref) {
              ref.current = element;
            }
            textareaRef.current = element;
          }}
          className={classNames(
            'h-full w-full',
            'p-8 leading-6',
            'focus:outline-none',
            'relative bottom-0 top-0 items-center rounded-sm',
            'outline outline-1 outline-moon-250',
            props.disabled
              ? 'opacity-50'
              : 'hover:outline hover:outline-2 hover:outline-teal-500/40 focus:outline-2',
            'outline outline-1 outline-moon-250 hover:outline-teal-500/40 focus:outline-teal-500/40',
            'appearance-none border-none',
            'placeholder-moon-500 dark:placeholder-moon-600',
            className
          )}
          {...props}
        />
      </Tailwind>
    );
  }
);

StyledTextArea.displayName = 'StyledTextArea';
