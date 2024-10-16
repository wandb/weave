import React, {memo} from 'react';
import {Icon, Ref} from 'semantic-ui-react';

// Copied from semantic since the type isn't exported
// https://github.com/Semantic-Org/Semantic-UI-React/blob/4bcdbea000a19c8796b1bb9493e3b60a93bd43a9/src/elements/Icon/Icon.d.ts#L6
type IconSizeProp =
  | 'mini'
  | 'tiny'
  | 'small'
  | 'large'
  | 'big'
  | 'huge'
  | 'massive';

export interface LegacyWBIconProps {
  name: string;
  title?: string;
  size?: IconSizeProp;
  rotated?: 'clockwise' | 'counterclockwise';
  link?: boolean;
  className?: string;
  onClick?: any;
  onMouseDown?: any;
  onMouseEnter?: any;
  onMouseLeave?: any;
  style?: any;

  'data-test'?: any;

  role?: string;
  ariaHidden?: string;
  ariaLabel?: string;
}

const LegacyWBIconComp = React.forwardRef<HTMLElement, LegacyWBIconProps>(
  (
    {
      name,
      size,
      rotated,
      link,
      className: propsClassName,
      onClick,
      onMouseDown,
      onMouseEnter,
      onMouseLeave,
      style,
      'data-test': dataTest,
      role,
      title,
      ariaHidden,
      ariaLabel,
    },
    ref
  ) => {
    let className = `wbic-ic-${name}`;
    if (propsClassName) {
      className += ' ' + propsClassName;
    }
    const passProps = {
      size,
      rotated,
      link,
      onClick,
      onMouseDown,
      onMouseEnter,
      onMouseLeave,
      style,
      'data-test': dataTest,
      role,
      title,
      'aria-hidden': ariaHidden,
      'aria-label': ariaLabel,
    };
    if (ref == null) {
      return <Icon {...passProps} className={className} />;
    }
    return (
      <Ref innerRef={ref}>
        <Icon {...passProps} className={className} />
      </Ref>
    );
  }
);

export const LegacyWBIcon = memo(LegacyWBIconComp);
