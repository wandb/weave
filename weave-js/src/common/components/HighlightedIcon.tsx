import classNames from 'classnames';
import React, {FC} from 'react';

interface HighlightedIconProps {
  className?: string;
  onClick?(e: React.MouseEvent): void;
  onMouseEnter?(e: React.MouseEvent): void;
  onMouseLeave?(e: React.MouseEvent): void;
}

const HighlightedIcon: FC<HighlightedIconProps> = React.memo(
  ({className, onClick, onMouseEnter, onMouseLeave, children}) => {
    return (
      <div
        className={classNames('wb-highlighted-icon', className)}
        onClick={onClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}>
        {children}
      </div>
    );
  }
);

export default HighlightedIcon;
