/*
  useChartZoom.ts

  This file contains the hook for zooming the charts. Because react-vis doesn't
  provide a zoom hook, we need to implement our own. The zoom hook will clamp the mouse
  coordinates to the plot area, and then use the screen-to-data converter to convert
  the mouse coordinates to data coordinates.

  LinePlot, ScatterPlot, and BarChart use this hook, with different behavior.
  - ScatterPlot zooms in 2D when a rectangle is drawn on the chart.
  - BarChart zooms in the x-axis only when a rectangle is drawn on the chart.
  - LinePlot zoom in 2D or 1D, depending on the height of the rectangle.
*/
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {ChartMargins, createChartMargins} from './styling';

export type SelectionState = {
  isSelecting: boolean;
  startX: number;
  startY: number;
  endX: number;
  endY: number;
};

export type UseFlexibleChartZoomOptions = {
  xDomain: [number, number];
  yDomain: [number, number];
  originalXDomain: [number, number];
  originalYDomain: [number, number] | undefined;
  onDomainChange?: (
    xDomain: [number, number],
    yDomain: [number, number] | undefined
  ) => void;
  isFullscreen?: boolean;
  onMouseMove?: (event: React.MouseEvent, selection: SelectionState) => void;
  xAxisZoomOnly?: boolean;
  smartZoom?: boolean;
};

/**
 * Creates a coordinate clamping function for FlexibleXYPlot
 * @param containerElement The chart container element
 * @param margins The chart margins
 * @returns A function that clamps coordinates to the plot area
 */
const createFlexibleCoordinateClamp = (
  containerElement: HTMLElement,
  margins: ChartMargins
) => {
  return (x: number, y: number) => {
    const rect = containerElement.getBoundingClientRect();
    const plotLeft = margins.left;
    const plotRight = rect.width - margins.right;
    const plotTop = margins.top;
    const plotBottom = rect.height - margins.bottom;

    const clampedX = Math.max(plotLeft, Math.min(x, plotRight));
    const clampedY = Math.max(plotTop, Math.min(y, plotBottom));

    return {x: clampedX, y: clampedY};
  };
};

/**
 * Creates a screen-to-data coordinate converter for FlexibleXYPlot
 * @param containerElement The chart container element
 * @param margins The chart margins
 * @param xDomain The current X-axis domain
 * @param yDomain The current Y-axis domain
 * @returns A function that converts screen coordinates to data coordinates
 */
const createFlexibleScreenToDataConverter = (
  containerElement: HTMLElement,
  margins: ChartMargins,
  xDomain: [number, number],
  yDomain: [number, number]
) => {
  return (screenX: number, screenY: number) => {
    const rect = containerElement.getBoundingClientRect();
    const plotWidth = rect.width - margins.left - margins.right;
    const plotHeight = rect.height - margins.top - margins.bottom;

    const xRatio = (screenX - margins.left) / plotWidth;
    const yRatio = (plotHeight - (screenY - margins.top)) / plotHeight;

    const dataX = xDomain[0] + xRatio * (xDomain[1] - xDomain[0]);
    const dataY = yDomain[0] + yRatio * (yDomain[1] - yDomain[0]);

    return {dataX, dataY};
  };
};

export const useChartZoom = ({
  xDomain,
  yDomain,
  originalXDomain,
  originalYDomain,
  onDomainChange,
  isFullscreen,
  onMouseMove,
  xAxisZoomOnly,
  smartZoom,
}: UseFlexibleChartZoomOptions) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const [selection, setSelection] = useState<SelectionState>({
    isSelecting: false,
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
  });

  // State for smart zoom behavior
  const [smartZoomState, setSmartZoomState] = useState<{
    use2D: boolean;
    verticalThreshold: number;
  }>({
    use2D: false,
    verticalThreshold: 8, // pixels - threshold for switching to 2D mode
  });

  // Chart margins for coordinate calculations
  const chartMargins = useMemo(
    () => createChartMargins(isFullscreen),
    [isFullscreen]
  );

  // Create coordinate utilities when we have a container
  const getCoordinateUtilities = useCallback(() => {
    if (!containerRef.current) return null;

    const clampToPlotArea = createFlexibleCoordinateClamp(
      containerRef.current,
      chartMargins
    );

    const screenToData = createFlexibleScreenToDataConverter(
      containerRef.current,
      chartMargins,
      xDomain,
      yDomain
    );

    return {clampToPlotArea, screenToData};
  }, [chartMargins, xDomain, yDomain]);

  const handleMouseDown = useCallback(
    (event: React.MouseEvent) => {
      if (!containerRef.current) return;

      const utilities = getCoordinateUtilities();
      if (!utilities) return;

      const rect = containerRef.current.getBoundingClientRect();
      const rawX = event.clientX - rect.left;
      const rawY = event.clientY - rect.top;
      const {x, y} = utilities.clampToPlotArea(rawX, rawY);

      setSelection({
        isSelecting: true,
        startX: x,
        startY: y,
        endX: x,
        endY: y,
      });

      // Reset smart zoom state for new selection
      if (smartZoom) {
        setSmartZoomState(prev => ({
          ...prev,
          use2D: false,
        }));
      }

      event.preventDefault();
    },
    [getCoordinateUtilities, smartZoom]
  );

  const handleMouseMoveInternal = useCallback(
    (event: React.MouseEvent) => {
      // Always call custom mouse move handler if provided (for crosshair functionality)
      if (onMouseMove) {
        onMouseMove(event, selection);
      }

      // Handle zoom selection logic only when actively selecting
      if (!selection.isSelecting || !containerRef.current) return;

      const utilities = getCoordinateUtilities();
      if (!utilities) return;

      const rect = containerRef.current.getBoundingClientRect();
      const rawX = event.clientX - rect.left;
      const rawY = event.clientY - rect.top;
      const {x, y} = utilities.clampToPlotArea(rawX, rawY);

      // Check for smart zoom behavior - switch to 2D if vertical movement exceeds threshold
      if (smartZoom && !smartZoomState.use2D) {
        const verticalMovement = Math.abs(y - selection.startY);
        if (verticalMovement > smartZoomState.verticalThreshold) {
          setSmartZoomState(prev => ({
            ...prev,
            use2D: true,
          }));
        }
      }

      const newSelection = {
        ...selection,
        endX: x,
        endY: y,
      };

      setSelection(newSelection);
    },
    [selection, getCoordinateUtilities, onMouseMove, smartZoom, smartZoomState]
  );

  const handleMouseUp = useCallback(
    (event: React.MouseEvent) => {
      if (!selection.isSelecting || !containerRef.current || !onDomainChange)
        return;

      const utilities = getCoordinateUtilities();
      if (!utilities) return;

      const rect = containerRef.current.getBoundingClientRect();
      const rawEndX = event.clientX - rect.left;
      const rawEndY = event.clientY - rect.top;
      const {x: endX, y: endY} = utilities.clampToPlotArea(rawEndX, rawEndY);

      const minSelectionSize = 10;
      const horizontalMovement = Math.abs(endX - selection.startX);
      const verticalMovement = Math.abs(endY - selection.startY);

      // Determine if we should use x-axis only based on smart zoom state or explicit setting
      const shouldUseXAxisOnly = smartZoom
        ? !smartZoomState.use2D
        : xAxisZoomOnly;

      const isValidSelection = shouldUseXAxisOnly
        ? horizontalMovement > minSelectionSize
        : horizontalMovement > minSelectionSize &&
          verticalMovement > minSelectionSize;

      if (isValidSelection) {
        const startData = utilities.screenToData(
          selection.startX,
          selection.startY
        );
        const endData = utilities.screenToData(endX, endY);

        const newXDomain: [number, number] = [
          Math.min(startData.dataX, endData.dataX),
          Math.max(startData.dataX, endData.dataX),
        ];

        if (shouldUseXAxisOnly) {
          onDomainChange(newXDomain, yDomain);
        } else {
          const newYDomain: [number, number] = [
            Math.min(startData.dataY, endData.dataY),
            Math.max(startData.dataY, endData.dataY),
          ];

          onDomainChange(newXDomain, newYDomain);
        }
      }

      setSelection({
        isSelecting: false,
        startX: 0,
        startY: 0,
        endX: 0,
        endY: 0,
      });
    },
    [
      selection,
      onDomainChange,
      getCoordinateUtilities,
      xAxisZoomOnly,
      smartZoom,
      smartZoomState,
      yDomain,
    ]
  );

  const handleDoubleClick = useCallback(() => {
    if (onDomainChange) {
      onDomainChange(originalXDomain, originalYDomain);
    }
  }, [onDomainChange, originalXDomain, originalYDomain]);

  // Selection rectangle style
  const selectionStyle = useMemo(() => {
    if (!selection.isSelecting) return null;

    const left = Math.min(selection.startX, selection.endX);
    const width = Math.abs(selection.endX - selection.startX);

    let top: number;
    let height: number;

    // Determine if we should show x-axis only selection based on smart zoom state or explicit setting
    const shouldShowXAxisOnly = smartZoom
      ? !smartZoomState.use2D
      : xAxisZoomOnly;

    if (shouldShowXAxisOnly) {
      // For x-axis only zoom, span the entire vertical chart area
      top = chartMargins.top;
      height =
        (containerRef.current?.getBoundingClientRect().height || 400) -
        chartMargins.top -
        chartMargins.bottom;
    } else {
      // For normal zoom, use the actual selection area
      top = Math.min(selection.startY, selection.endY);
      height = Math.abs(selection.endY - selection.startY);
    }

    return {
      position: 'absolute' as const,
      left,
      top,
      width,
      height,
      border: '1px dashed #007acc',
      backgroundColor: 'rgba(0, 122, 204, 0.1)',
      pointerEvents: 'none' as const,
      zIndex: 10,
    };
  }, [selection, xAxisZoomOnly, smartZoom, smartZoomState, chartMargins]);

  return {
    containerRef,
    selection,
    selectionStyle,
    handleMouseDown,
    handleMouseMove: handleMouseMoveInternal,
    handleMouseUp,
    handleDoubleClick,
  };
};
