/**
 * A form multi-line text input.
 */
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {forwardRef} from 'react';

type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  autoGrow?: boolean;
  maxHeight?: string | number;
  startHeight?: string | number;
  reset?: boolean;
  rows?: number;
};

export const StyledTextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({className, autoGrow, maxHeight, startHeight, reset, ...props}, ref) => {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    React.useEffect(() => {
      if (!autoGrow || !textareaRef.current) {
        return;
      }

      const adjustHeight = () => {
        const textareaElement = textareaRef.current;
        if (!textareaElement) {
          return;
        }

        // Only disable resize when autoGrow is true
        textareaElement.style.resize = autoGrow ? 'none' : 'vertical';

        // Set initial height if provided
        if (startHeight && textareaElement.value === '') {
          textareaElement.style.height =
            typeof startHeight === 'number' ? `${startHeight}px` : startHeight;
          return;
        }

        if (reset || textareaElement.value === '') {
          textareaElement.style.height = startHeight
            ? typeof startHeight === 'number'
              ? `${startHeight}px`
              : startHeight
            : 'auto';
          return;
        }

        // Reset height to allow shrinking
        textareaElement.style.height = 'auto';
        const newHeight = textareaElement.scrollHeight;

        // Apply max height if specified
        if (maxHeight) {
          textareaElement.style.height = `${Math.min(
            newHeight,
            typeof maxHeight === 'string' ? parseInt(maxHeight, 10) : maxHeight
          )}px`;
          textareaElement.style.overflowY =
            newHeight >
            (typeof maxHeight === 'string'
              ? parseInt(maxHeight, 10)
              : maxHeight)
              ? 'auto'
              : 'hidden';
        } else {
          textareaElement.style.height = `${newHeight}px`;
          textareaElement.style.overflowY = 'hidden';
        }
      };

      const textareaRefElement = textareaRef.current;
      textareaRefElement.addEventListener('input', adjustHeight);
      adjustHeight(); // Initial adjustment

      return () =>
        textareaRefElement.removeEventListener('input', adjustHeight);
    }, [autoGrow, maxHeight, reset, startHeight]);

    return (
      <Tailwind style={{display: 'contents'}}>
        <textarea
          rows={props.rows}
          ref={element => {
            if (typeof ref === 'function') {
              ref(element);
            } else if (ref) {
              (
                ref as React.MutableRefObject<HTMLTextAreaElement | null>
              ).current = element;
            }
            (
              textareaRef as React.MutableRefObject<HTMLTextAreaElement | null>
            ).current = element;
          }}
          className={classNames(
            'h-full w-full',
            'p-8 leading-6',
            'focus:outline-none',
            'relative bottom-0 top-0 items-center rounded-sm',
            'outline outline-1 outline-moon-250',
            !autoGrow && 'resize-y',
            props.disabled
              ? 'opacity-50'
              : 'hover:outline hover:outline-2 hover:outline-teal-500/40 focus:outline-2',
            'outline outline-1 outline-moon-250 hover:outline-teal-500/40 focus:outline-teal-500/40',
            'appearance-none border-none',
            'placeholder-moon-500 dark:placeholder-moon-600',
            className
          )}
          style={{
            height: startHeight
              ? typeof startHeight === 'number'
                ? `${startHeight}px`
                : startHeight
              : undefined,
            ...props.style,
          }}
          {...props}
        />
      </Tailwind>
    );
  }
);

StyledTextArea.displayName = 'StyledTextArea';
