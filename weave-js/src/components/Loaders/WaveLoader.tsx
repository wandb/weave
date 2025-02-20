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

export const WaveLoader = ({
  size,
  delayBeforeShow,
}: {
  size: 'small' | 'huge';
  delayBeforeShow?: number;
}) => {
  const [okToShow, setOkToShow] = React.useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setOkToShow(true);
    }, delayBeforeShow);
    return () => clearTimeout(timer);
  }, [delayBeforeShow]);

  return (
    <TailwindContents>
      <div
        className="flex items-center gap-x-4"
        data-test={`wave-loader-${size}`}>
        {okToShow && (
          <>
            <Dot size={size} />
            <Dot delay=".3s" size={size} />
            <Dot delay=".6s" size={size} />
          </>
        )}
      </div>
    </TailwindContents>
  );
};
