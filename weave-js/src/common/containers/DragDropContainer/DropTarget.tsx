import {isEqual as _isEqual} from 'lodash';
import React, {
  CSSProperties,
  FC,
  memo,
  ReactNode,
  useCallback,
  useContext,
} from 'react';

import {DragDropContext, DragDropState} from './DragDropContextProvider';
import {DragRef} from './types';

export type DropTargetProps = {
  children?: ReactNode;
  partRef: DragRef;
  className?: string;
  style?: CSSProperties;
  isValidDropTarget?(ctx: DragDropState): boolean; // default is () => true
  onDragOver?(ctx: DragDropState, e: React.DragEvent): void;
  onDragStart?(e: React.DragEvent): void;
  onDragEnter?(ctx: DragDropState, e: React.DragEvent): void;
  onDragLeave?(ctx: DragDropState, e: React.DragEvent): void;
  onDrop?(ctx: DragDropState, e: React.DragEvent): void;
  getClassName?(ctx: DragDropState): string | undefined; // function to dynamically generate class name based on context
  onClick?(e: React.MouseEvent): void;
  onMouseDown?(e: React.MouseEvent): void;
  onMouseUp?(e: React.MouseEvent): void;
};

const DropTargetComp: FC<DropTargetProps> = ({
  children,
  className,
  getClassName,
  style,
  partRef,
  onDragOver,
  onDragStart,
  onDragEnter,
  onDragLeave,
  onDrop,
  isValidDropTarget,
  onClick,
  onMouseDown,
  onMouseUp,
}) => {
  const context = useContext(DragDropContext);
  const {
    clientXY,
    dragRef,
    dropRef,
    setDragRef,
    setDragData,
    setDragStarted,
    setDragging,
    setDropRef,
    setShiftKey,
  } = context;
  const validDropTarget = useCallback(
    (ctx: DragDropState) =>
      isValidDropTarget != null ? isValidDropTarget(ctx) : true,
    [isValidDropTarget]
  );

  const handleOnDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (dragRef != null && validDropTarget(context)) {
        if (dropRef == null || !_isEqual(partRef, dropRef)) {
          setDropRef(partRef);
        }
        if (onDragOver) {
          onDragOver(context, e);
        }
      }
    },
    [
      context,
      dragRef,
      dropRef,
      onDragOver,
      partRef,
      setDropRef,
      validDropTarget,
    ]
  );

  const handleOnDragStart = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      onDragStart?.(e);
    },
    [onDragStart]
  );

  const handleOnDragEnter = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (onDragEnter && dragRef && validDropTarget(context)) {
        onDragEnter(context, e);
      }
    },
    [context, dragRef, onDragEnter, validDropTarget]
  );

  const handleOnDragLeave = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.stopPropagation();
      e.preventDefault();
      if (
        onDragLeave &&
        dragRef &&
        clientXY != null &&
        validDropTarget(context)
      ) {
        // Dragging over the target's children can trigger onDragLeave
        // So we use the target bounds to decide if we should actually trigger it
        // (We could also set pointer-events: none on children, but sometimes that causes other problems)
        const targetBounds = e.currentTarget.getBoundingClientRect();
        const [clientX, clientY] = clientXY;
        if (
          clientY < targetBounds.top ||
          clientY > targetBounds.bottom ||
          clientX < targetBounds.left ||
          clientX > targetBounds.right
        ) {
          onDragLeave(context, e);
        }
      }
    },
    [context, dragRef, clientXY, onDragLeave, validDropTarget]
  );

  const handleOnDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      if (onDrop && dragRef && validDropTarget(context)) {
        e.stopPropagation();
        e.preventDefault();
        onDrop(context, e);
      }
      setDropRef(null);
      setDragData(null);
      setDragStarted(false);
      setDragging(false);
      setDragRef(null);
      setShiftKey(false);
    },
    [
      context,
      dragRef,
      onDrop,
      setDragData,
      setDragRef,
      setDragStarted,
      setDragging,
      setDropRef,
      setShiftKey,
      validDropTarget,
    ]
  );

  return (
    <div
      style={style || undefined}
      className={getClassName ? getClassName(context) : className || undefined}
      onClick={onClick}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      onDragOver={handleOnDragOver}
      onDragStart={handleOnDragStart}
      onDragEnter={handleOnDragEnter}
      onDragLeave={handleOnDragLeave}
      onDrop={handleOnDrop}>
      {children}
    </div>
  );
};

export const DropTarget = memo(DropTargetComp);
