import _ from 'lodash';
import React, {
  createContext,
  FC,
  memo,
  ReactElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {DragData, DragRef} from './types';

export interface DragDropState {
  mouseDownEvent: React.MouseEvent | null;
  dragData: DragData | null;
  dropRef: DragRef | null;
  dragRef: DragRef | null;
  dragStarted: boolean;
  dragging: boolean;

  // Firefox doesn't give you clientX and clientY on drag events (wtf)
  // So we add an event handler to document.dragover and store the result in the context
  clientXY: number[] | null;

  /* capture mouse position and mouse-overed element on shift and
       shift release to enable fancy shift-key based modifiers */
  shiftKey: boolean;
  mouseEventOnShift: React.MouseEvent | null;
  mouseEventOnShiftRelease: React.MouseEvent | null;
  dropRefOnShift: DragRef | null;
  dropRefOnShiftRelease: DragRef | null;
  elementOnShiftRelease: Element | null;

  setMouseDownEvent(e: React.MouseEvent | null): void;
  setDragData(data: DragData | null): void;
  setDropRef(ref: DragRef | null): void;
  setDragRef(ref: DragRef | null): void;
  setDragStarted(dragStarted: boolean): void;
  setDragging(dragStarted: boolean): void;

  /* shift key stuff */
  setShiftKey(shiftKey: boolean): void;
  setDropRefOnShift(ref: DragRef | null): void;
  setDropRefOnShiftRelease(ref: DragRef | null): void;
  setMouseEventOnShift(e: React.MouseEvent | null): void;
  setMouseEventOnShiftRelease(e: React.MouseEvent | null): void;
  setElementOnShiftRelease(e: Element | null): void;
}

export const DragDropContext = createContext<DragDropState>({
  mouseDownEvent: null,
  dragData: null,
  dragRef: null,
  dropRef: null,
  dragStarted: false,
  dragging: false,

  clientXY: null,

  shiftKey: false,
  dropRefOnShift: null,
  dropRefOnShiftRelease: null,
  mouseEventOnShift: null,
  mouseEventOnShiftRelease: null,
  elementOnShiftRelease: null,

  // tslint:disable-next-line:no-empty
  setMouseDownEvent: () => {},
  // tslint:disable-next-line:no-empty
  setDragData: () => {},
  // tslint:disable-next-line:no-empty
  setDropRef: () => {},
  // tslint:disable-next-line:no-empty
  setDragRef: () => {},
  // tslint:disable-next-line:no-empty
  setDragStarted: () => {},
  // tslint:disable-next-line:no-empty
  setDragging: () => {},

  // tslint:disable-next-line:no-empty
  setShiftKey: () => {},
  // tslint:disable-next-line:no-empty
  setDropRefOnShift: () => {},
  // tslint:disable-next-line:no-empty
  setDropRefOnShiftRelease: () => {},
  // tslint:disable-next-line:no-empty
  setMouseEventOnShift: () => {},
  // tslint:disable-next-line:no-empty
  setMouseEventOnShiftRelease: () => {},
  // tslint:disable-next-line:no-empty
  setElementOnShiftRelease: () => {},
});
DragDropContext.displayName = 'DragDropContext';

interface DragDropProviderProps {
  children: ReactElement;
  onDocumentDragOver?(ctx: DragDropState, e: DragEvent): void;
}

const DragDropProviderComp: FC<DragDropProviderProps> = ({
  onDocumentDragOver,
  children,
}) => {
  const [mouseDownEvent, setMouseDownEvent] = useState<React.MouseEvent | null>(
    null
  );
  const [dragData, setDragData] = useState<DragData | null>(null);
  const [dropRef, setDropRef] = useState<DragRef | null>(null);
  const [dragRef, setDragRef] = useState<DragRef | null>(null);
  const [dragStarted, setDragStarted] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [clientXY, setClientXY] = useState<number[] | null>(null);
  const [shiftKey, setShiftKey] = useState(false);
  const [dropRefOnShift, setDropRefOnShift] = useState<DragRef | null>(null);
  const [dropRefOnShiftRelease, setDropRefOnShiftRelease] =
    useState<DragRef | null>(null);
  const [mouseEventOnShift, setMouseEventOnShift] =
    useState<React.MouseEvent | null>(null);
  const [mouseEventOnShiftRelease, setMouseEventOnShiftRelease] =
    useState<React.MouseEvent | null>(null);
  const [elementOnShiftRelease, setElementOnShiftRelease] =
    useState<Element | null>(null);

  const contextVal: DragDropState = useMemo(
    () => ({
      mouseDownEvent,
      setMouseDownEvent,
      dragData,
      setDragData,
      dropRef,
      setDropRef,
      dragRef,
      setDragRef,
      dragStarted,
      setDragStarted,
      dragging,
      setDragging,
      clientXY,
      shiftKey,
      setShiftKey,
      dropRefOnShift,
      setDropRefOnShift,
      dropRefOnShiftRelease,
      setDropRefOnShiftRelease,
      mouseEventOnShift,
      setMouseEventOnShift,
      mouseEventOnShiftRelease,
      setMouseEventOnShiftRelease,
      elementOnShiftRelease,
      setElementOnShiftRelease,
    }),
    [
      mouseDownEvent,
      dragData,
      dropRef,
      dragRef,
      dragStarted,
      dragging,
      clientXY,
      shiftKey,
      dropRefOnShift,
      dropRefOnShiftRelease,
      mouseEventOnShift,
      mouseEventOnShiftRelease,
      elementOnShiftRelease,
    ]
  );
  const contextValRef = useRef(contextVal);
  contextValRef.current = contextVal;

  const setClientXYFromEvent = useMemo(
    () =>
      _.throttle((e: MouseEvent) => {
        setClientXY([e.clientX, e.clientY]);
      }, 500),
    []
  );

  const clearDragRef = useCallback(
    (e: any) => {
      // This null check is important.
      // If you call e.preventDefault on all window.mouseup events, it breaks range slider inputs in Safari+Firefox
      if (dragRef != null) {
        e.preventDefault();
        e.stopPropagation();
        setDragRef(null);
      }
    },
    [dragRef]
  );

  useEffect(() => {
    window.addEventListener('mouseup', clearDragRef);
    return () => {
      window.removeEventListener('mouseup', clearDragRef);
    };
  }, [clearDragRef]);

  useEffect(() => {
    // Firefox doesn't give you clientX and clientY on drag events (wtf)
    // So we add an event handler to document.dragover and store the result in the context
    function mousemoveHandler(e: MouseEvent) {
      setClientXYFromEvent(e);
    }

    function dragstartHandler() {
      document.addEventListener('mousemove', mousemoveHandler);
    }

    function dragendHandler() {
      document.removeEventListener('mousemove', mousemoveHandler);
    }

    function dragoverHandler(e: DragEvent) {
      onDocumentDragOver?.(contextValRef.current, e);
    }

    document.addEventListener('dragstart', dragstartHandler);
    document.addEventListener('dragend', dragendHandler);
    document.addEventListener('dragover', dragoverHandler);
    return () => {
      document.removeEventListener('mousemove', mousemoveHandler);
      document.removeEventListener('dragover', dragoverHandler);
      document.removeEventListener('dragstart', dragstartHandler);
      document.removeEventListener('dragend', dragstartHandler);
    };
  }, [setClientXYFromEvent, onDocumentDragOver]);

  return (
    <DragDropContext.Provider value={contextVal}>
      {children}
    </DragDropContext.Provider>
  );
};

export const DragDropProvider = memo(DragDropProviderComp);

export function useDragDropContext() {
  return useContext(DragDropContext);
}
