import {
  CSSProperties,
  MutableRefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';

import {useStateWithRef} from '../../../hookUtils';

const SCALE_DELTA_MULTIPLIER = 0.001;

type TimelineZoomAndPanParams = {
  onHittingMinZoom?: () => void;
};

type TimelineZoomAndPan = {
  timelineRef: MutableRefObject<HTMLDivElement | null>;
  timelineStyle: CSSProperties;
  scale: number;
};

export function useTimelineZoomAndPan({
  onHittingMinZoom,
}: TimelineZoomAndPanParams): TimelineZoomAndPan {
  const [scale, setScale, scaleRef] = useStateWithRef(1);
  const {cursor, updateCursor} = useTimelineCursor();

  const timelineRef = useRef<HTMLDivElement | null>(null);
  const zoomScrollToRef = useRef<number | null>(null);

  useEffect(() => {
    const el = timelineRef.current;
    if (el == null) {
      return;
    }

    let dragging = false;

    function onWheel(e: WheelEvent): void {
      const {deltaX, deltaY} = e;

      // Allow horizontal scrolling
      if (Math.abs(deltaX) > Math.abs(deltaY)) {
        return;
      }

      e.preventDefault();

      // We have to allow only one zoom per render to
      // allow the mouse scroll position to catch up
      if (zoomScrollToRef.current != null) {
        return;
      }

      const scaleMult = 1 - deltaY * SCALE_DELTA_MULTIPLIER;

      if (scaleMult < 1 && scaleRef.current === 1) {
        // We're already at minimum zoom
        onHittingMinZoom?.();
        return;
      }

      const newScale = Math.max(scaleRef.current * scaleMult, 1);

      calculateZoomScrollTo();
      setScale(newScale);

      function calculateZoomScrollTo(): void {
        if (el == null || newScale === scaleRef.current) {
          return;
        }

        // Calculate current "focused" X coordinate
        // relative to the beginning of the timeline
        const mouseX = e.clientX - el.getBoundingClientRect().x;
        const currentX = el.scrollLeft + mouseX;

        // Calculate post-zoom "focused" X coordinate
        // relative to the beginning of the timeline
        const newScaleRatio = newScale / scaleRef.current;
        const nextX = currentX * newScaleRatio;

        zoomScrollToRef.current = nextX - mouseX;
      }
    }

    function onMouseDown(): void {
      dragging = true;
      updateCursor(dragging);
    }

    function onMouseUp(): void {
      dragging = false;
      updateCursor(dragging);
    }

    function onMouseMove(e: MouseEvent): void {
      if (!dragging) {
        return;
      }
      el?.scrollBy(-e.movementX, -e.movementY);
    }

    el.addEventListener(`wheel`, onWheel, {passive: false});
    el.addEventListener(`mousedown`, onMouseDown);
    document.addEventListener(`mouseup`, onMouseUp);
    document.addEventListener(`mousemove`, onMouseMove);
    return () => {
      el.removeEventListener(`wheel`, onWheel);
      el.removeEventListener(`mousedown`, onMouseDown);
      document.removeEventListener(`mouseup`, onMouseUp);
      document.removeEventListener(`mousemove`, onMouseMove);
    };
  }, [setScale, scaleRef, updateCursor, onHittingMinZoom]);

  // Scroll to "focused" X coordinate after zoom
  useLayoutEffect(() => {
    if (zoomScrollToRef.current == null) {
      return;
    }
    timelineRef.current?.scrollTo({left: zoomScrollToRef.current});
    zoomScrollToRef.current = null;
  }, [scale]);

  return {
    timelineRef,
    timelineStyle: {userSelect: `none`, cursor},
    scale,
  };
}

type TimelineCursor = `grab` | `grabbing`;

type UseTimelineCursorResult = {
  cursor: TimelineCursor;
  updateCursor: (dragging: boolean) => void;
};

function useTimelineCursor(): UseTimelineCursorResult {
  const [cursor, setCursor] = useState<TimelineCursor>(`grab`);

  const updateCursor = useCallback((dragging: boolean) => {
    setCursor(dragging ? `grabbing` : `grab`);
  }, []);

  return {cursor, updateCursor};
}
