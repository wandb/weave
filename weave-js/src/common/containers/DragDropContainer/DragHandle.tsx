import React, {CSSProperties, FC, memo, ReactNode, useContext} from 'react';

import {DragDropContext} from './DragDropContextProvider';
import {DragRef} from './types';

interface DragHandleProps {
  partRef: DragRef;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onMouseDown?(e: React.MouseEvent): void;
}

const DragHandleComp: FC<DragHandleProps> = ({
  children,
  className,
  style,
  partRef,
}) => {
  const context = useContext(DragDropContext);
  const {setDragRef, setMouseDownEvent} = context;
  return (
    <div
      className={'drag-drop-handle ' + (className || '')}
      style={style}
      onMouseDown={e => {
        setDragRef(partRef);
        setMouseDownEvent(e);
      }}>
      {children}
    </div>
  );
};

export const DragHandle = memo(DragHandleComp);
