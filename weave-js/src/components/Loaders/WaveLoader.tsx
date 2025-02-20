import {TailwindContents} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {useMemo} from 'react';
import {CSSTransition} from 'react-transition-group';

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
  return (
    <TailwindContents>
      {/**
        CSSTransition from react-transition-group controls how the child element 
        (the <div> with dots) appears and disappears.

        - in={true}
          Forces the transition to run in "appear" or "enter" states immediately 
          on mount (since it's already "in").
        
        - appear
          Enables a special "appear" phase on the initial mount, as opposed to 
          jumping straight to the "entered" state.

        - mountOnEnter
          Does not mount the child DOM node until the transition is ready to 
          start (i.e., the "appear" or "enter" phase).

        - timeout={delayBeforeShow ?? 0}
          Defines how long the "appear" phase lasts, in milliseconds. If 
          delayBeforeShow is undefined, it defaults to 0 (no wait). 
          After this timeout, the component transitions from the appear classes 
          to the enter classes.

        - classNames: An object mapping transition states to class names:
            * appear/appearActive
              Applied during the "appear" phase. Here we use 'opacity-0' to keep 
              the component completely invisible for the entire duration of appear.
            
            * enter/enterActive
              Applied when we leave the "appear" phase and fully enter the component. 
              In this case, 'opacity-100' is used, so it instantly becomes fully visible.
            
          Because there are no actual "transition-opacity" or "duration-..." 
          classes, the element will flip from invisible to visible with no fade.
      */}
      <CSSTransition
        in={true}
        appear
        mountOnEnter
        timeout={delayBeforeShow ?? 0}
        classNames={{
          appear: 'opacity-0',
          appearActive: 'opacity-0',
          enter: 'opacity-100',
          enterActive: 'opacity-100',
        }}>
        <div
          className="flex items-center gap-x-4 "
          data-test={`wave-loader-${size}`}>
          <Dot size={size} />
          <Dot delay=".3s" size={size} />
          <Dot delay=".6s" size={size} />
        </div>
      </CSSTransition>
    </TailwindContents>
  );
};
