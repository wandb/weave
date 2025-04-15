import classNames from 'classnames';
import React from 'react';

type TailwindProps = {
  style?: React.CSSProperties;
  className?: string;
};

// Simple wrapper component that has the tw-style class,
// meaning that all elements inside of this wrapper will have
// Tailwind's preflight CSS reset applied.
//
// How to use:
// Put this wrapper around components when you want them to use
// tailwind css for styling.
//
// DO NOT apply this as a wrapper around existing parts of the site unless
// you are able to test that all the components/pages/etc still appear
// correctly.
//
// There's nothing bad about using this Tailwind wrapper around
// existing elements, as long as you can test that they still look good.
export const Tailwind: React.FC<TailwindProps> = ({
  style,
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={classNames('tw-style', className)}
      data-testid="tailwind-wrapper"
      style={style}
      {...props}>
      {children}
    </div>
  );
};

/**
 * A tailwind wrapper with display: contents so that it doesn't affect document flow
 */
export const TailwindContents: React.FC<TailwindProps> = ({
  children,
  className,
  style,
  ...props
}) => {
  const styles = React.useMemo(
    () => ({
      ...style,
      display: 'contents',
    }),
    [style]
  );

  return (
    <Tailwind style={styles} className={className} {...props}>
      {children}
    </Tailwind>
  );
};
