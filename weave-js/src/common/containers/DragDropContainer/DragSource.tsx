import classNames from 'classnames';
import _, {isEqual as _isEqual} from 'lodash';
import React, {
  CSSProperties,
  FC,
  memo,
  ReactNode,
  useCallback,
  useContext,
} from 'react';

import {isFirefox} from '../../../components/WeavePanelBank/panelbankUtil';
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

  const handleOnDrag = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (!dragging) {
        setDragging(true);
      }

      // Firefox sets clientX and clientY on drag events to 0.
      // This is a 16 year old bug that they still haven't addressed https://bugzilla.mozilla.org/show_bug.cgi?id=505521
      // The workaround is to add a dragoverhandler and keep track of the clientXY instead.
      // Note: please be careful when changing this especially when if considering using ?? because 0 is not null or undefined.
      const clientYForAutoScroll = isFirefox ? clientXY?.[1] : e.clientY;

      if (clientYForAutoScroll != null) {
        // Automatically scroll the window if you're dragging near the top or bottom of the page
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
    },
    [
      clientXY,
      dragging,
      dropRef,
      setDragging,
      setDropRefOnShift,
      setDropRefOnShiftRelease,
      setElementOnShiftRelease,
      setMouseEventOnShift,
      setMouseEventOnShiftRelease,
      setShiftKey,
      shiftKey,
    ]
  );

  const handleOnDragStart = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
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
    },
    [context, data, onDragStart, selectedForDrag, setDragData, setDragStarted]
  );

  const handleOnDragEnd = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.stopPropagation();
      setDropRef(null);
      setDragData(null);
      setDragStarted(false);
      setDragging(false);
      setShiftKey(false);
      if (onDragEnd) {
        onDragEnd(context, e);
      }
    },
    [
      context,
      onDragEnd,
      setDragData,
      setDragStarted,
      setDragging,
      setDropRef,
      setShiftKey,
    ]
  );

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
      onDrag={handleOnDrag}
      onDragStart={handleOnDragStart}
      onDragEnd={handleOnDragEnd}>
      {children}
    </div>
  );
};

export const DragSource = memo(DragSourceComp);
