import {TailwindContents} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {useMemo} from 'react';

const Dot = React.memo(
  ({delay, size}: {delay?: string; size: 'small' | 'huge'}) => {
    const style = useMemo(
      () => ({
        animationDelay: delay,
      }),
      [delay]
    );

    const classes = classNames(
      'rounded-full bg-moon-350 dark:bg-moon-650 animate-wave',
      {
        'h-8 w-8': size === 'huge',
        'h-6 w-6': size === 'small',
      }
    );
    return <div className={classes} style={style} />;
  }
);

export const WaveLoader = ({size}: {size: 'small' | 'huge'}) => {
  return (
    <TailwindContents>
      <div className="flex items-center gap-x-4">
        <Dot size={size} />
        <Dot delay=".3s" size={size} />
        <Dot delay=".6s" size={size} />
      </div>
    </TailwindContents>
  );
};
