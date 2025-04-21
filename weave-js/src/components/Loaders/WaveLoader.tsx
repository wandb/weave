import {useTimeout} from '@wandb/weave/common/util/hooks';
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

/**
 * WaveLoader displays a row of Dot elements after an optional delay,
 * instantly switching from completely hidden to visible.
 *
 * @param {Object} props
 * @param {'small' | 'huge'} props.size - The size variant for each Dot.
 * @param {number} [props.delayBeforeShow] - Time in ms to wait before showing the dots.
 */
export const WaveLoader = ({
  size,
  delayBeforeShow,
}: {
  size: 'small' | 'huge';
  delayBeforeShow?: number;
}) => {
  const isReady = useTimeout(delayBeforeShow ?? 0);
  return (
    <TailwindContents>
      <div
        className={classNames(
          'flex items-center gap-x-4',
          isReady ? 'opacity-100' : 'opacity-0'
        )}
        data-test={`wave-loader-${size}`}>
        <Dot size={size} />
        <Dot delay=".3s" size={size} />
        <Dot delay=".6s" size={size} />
      </div>
    </TailwindContents>
  );
};
