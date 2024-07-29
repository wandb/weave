import classNames from 'classnames';
import _, {isEqual as _isEqual} from 'lodash';
import React, {CSSProperties, FC, memo, ReactNode, useContext} from 'react';

import {autoScrollWhenDragging} from '../../util/dom';
import {DragDropContext, DragDropState} from './DragDropContextProvider';
import {DragData, DragRef} from './types';

export type DragSourceProps = {
  children: ReactNode;
  partRef: DragRef;
  data?: DragData;
  className?: string;
  style?: CSSProperties;
  draggingStyle?: CSSProperties;
  callbackRef?: (el: HTMLDivElement) => void;
  onMouseUp?(event: React.MouseEvent<HTMLDivElement, MouseEvent>): void;
  onDragStart?(ctx: DragDropState, e: React.DragEvent): void;
  onDragEnd?(ctx: DragDropState, e: React.DragEvent): void;
};

const DragSourceComp: FC<DragSourceProps> = ({
  children,
  className,
  style,
  draggingStyle,
  partRef,
  data,
  callbackRef,
  onMouseUp,
  onDragStart,
  onDragEnd,
}) => {
  const context = useContext(DragDropContext);
  const {
    clientXY,
    dropRef,
    dragRef,
    dragStarted,
    dragging,
    shiftKey,
    setDragData,
    setDropRef,
    setDragStarted,
    setDragging,
    setShiftKey,
    setDropRefOnShift,
    setDropRefOnShiftRelease,
    setMouseEventOnShift,
    setMouseEventOnShiftRelease,
    setElementOnShiftRelease,
  } = context;
  const selectedForDrag = _isEqual(partRef, dragRef);

  return (
    <div
      className={classNames(className, 'drag-source', {
        'selected-for-drag': selectedForDrag,
        'drag-started': selectedForDrag && dragStarted,
        dragging: selectedForDrag && dragging,
      })}
      ref={callbackRef}
      style={{...style, ...(selectedForDrag ? draggingStyle : {})}}
      draggable={selectedForDrag}
      onMouseUp={onMouseUp}
      onDrag={e => {
        if (!dragging) {
          setDragging(true);
        }

        // Automatically scroll the window if you're dragging near the top or bottom of the page
        const clientYForAutoScroll = clientXY ? clientXY[1] : e.clientY;
        if (clientYForAutoScroll != null) {
          autoScrollWhenDragging(clientYForAutoScroll);
        }

        if (e.shiftKey !== shiftKey) {
          if (e.shiftKey) {
            // shift key pressed
            setDropRefOnShift(dropRef);
            setMouseEventOnShift(_.clone(e));
          } else {
            if (clientXY != null) {
              const [clientX, clientY] = clientXY;
              // shift key released
              setDropRefOnShiftRelease(dropRef);
              setMouseEventOnShiftRelease(_.clone(e));
              setElementOnShiftRelease(
                document.elementFromPoint(clientX, clientY)
              );
            }
          }
          setShiftKey(e.shiftKey);
        }
      }}
      onDragStart={e => {
        if (selectedForDrag) {
          setDragStarted(true);
          e.dataTransfer.setData('text', ''); // required for firefox
          if (data) {
            setDragData(data);
          }
          if (onDragStart) {
            onDragStart(context, e);
          }
        }
      }}
      onDragEnd={e => {
        e.stopPropagation();
        setDropRef(null);
        setDragData(null);
        setDragStarted(false);
        setDragging(false);
        setShiftKey(false);
        if (onDragEnd) {
          onDragEnd(context, e);
        }
      }}>
      {children}
    </div>
  );
};

export const DragSource = memo(DragSourceComp);
