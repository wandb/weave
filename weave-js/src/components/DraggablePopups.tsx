/**
 * Support for a preview tooltip combined with a draggable popup on click.
 */

import Grow from '@mui/material/Grow';
import Tooltip, {tooltipClasses, TooltipProps} from '@mui/material/Tooltip';
import * as Colors from '@wandb/weave/common/css/color.styles';
import React, {useCallback, useState} from 'react';
import Draggable from 'react-draggable';
import styled from 'styled-components';

export const Popped = styled.div`
  border-radius: 4px;
  word-wrap: break-word;
  background-color: #fff;
  color: ${Colors.MOON_700};
  border: 1px solid ${Colors.MOON_300};
`;
Popped.displayName = 'S.Popped';

export const PoppedBody = styled.div`
  width: 600px;
  max-height: 60vh;
  overflow: auto;
`;
PoppedBody.displayName = 'S.PoppedBody';

export const StyledTooltip = styled(
  ({className, padding, ...props}: TooltipProps & {padding?: number}) => (
    <Tooltip {...props} classes={{popper: className}} />
  )
)(({theme, padding}) => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: '#fff',
    color: Colors.MOON_700,
    border: `1px solid ${Colors.MOON_300}`,
    maxWidth: 600,
    padding,
  },
}));

export const TooltipHint = styled.div`
  color: ${Colors.MOON_500};
  text-align: center;
  font-size: 0.8em;
`;
TooltipHint.displayName = 'S.TooltipHint';

export const DraggableWrapper = ({children, ...other}: any) => {
  return (
    <Draggable handle=".handle">
      {React.cloneElement(children, {...other})}
    </Draggable>
  );
};

export const DraggableGrow = React.forwardRef(
  ({children, ...other}: any, ref) => {
    return (
      <Grow ref={ref} {...other} timeout={0}>
        <div>
          <DraggableWrapper>{children}</DraggableWrapper>
        </div>
      </Grow>
    );
  }
);

type DraggableHandleProps = {
  children: React.ReactNode;
};

export const DraggableHandle = ({children}: DraggableHandleProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const onMouseDown = useCallback(() => setIsDragging(true), [setIsDragging]);
  const onMouseUp = useCallback(() => setIsDragging(false), [setIsDragging]);
  const style: React.CSSProperties = {
    cursor: isDragging ? 'grabbing' : 'grab',
  };

  return (
    <div
      className="handle"
      style={style}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}>
      {children}
    </div>
  );
};
