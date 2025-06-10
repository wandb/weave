/**
 * A form multi-line text input.
 * Imported from core
 */

import {TailwindContents} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {TextareaHTMLAttributes} from 'react';

export const TextArea = ({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) => {
  return (
    <TailwindContents>
      <textarea
        className={classNames(
          'w-full flex-1',
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
    </TailwindContents>
  );
};
