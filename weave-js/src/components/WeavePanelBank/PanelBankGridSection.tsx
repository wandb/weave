import './PanelBank.less';
import './PanelBankEditablePanel.less';

import {
  DragDropContext,
  DragDropState,
  DragSource,
  DropTarget,
} from '@wandb/weave/common/containers/DragDropContainer';
import classNames from 'classnames';
import {produce} from 'immer';
import * as _ from 'lodash';
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {Resizable} from 'react-resizable';

import {
  isPanel,
  PanelBankSectionComponentSharedProps,
  PanelBankSectionConfig,
} from './panelbank';
import EmptyPanelBankSectionWatermark from './PanelBankEmptySectionWatermark';
import {
  bottom,
  compact,
  getLayoutItem,
  getNewGridItemLayout,
  GRID_COLUMN_COUNT,
  GRID_CONTAINER_PADDING,
  GRID_ITEM_DEFAULT_HEIGHT,
  GRID_ITEM_DEFAULT_WIDTH,
  GRID_ITEM_MARGIN,
  GRID_ROW_HEIGHT,
  GridLayout,
  GridLayoutItem,
} from './panelbankGrid';
import {isFirefox, skipTransition} from './panelbankUtil';

export function actionSetGridLayout(
  sectionConfig: PanelBankSectionConfig,
  newGridLayout: GridLayout
): PanelBankSectionConfig {
  return produce(sectionConfig, draft => {
    for (const panel of newGridLayout) {
      const panelIndex = sectionConfig.panels.findIndex(
        item => item.id === panel.id
      );
      if (panelIndex > -1) {
        draft.panels[panelIndex].layout = {
          x: panel.x,
          y: panel.y,
          w: panel.w,
          h: panel.h,
        };
      }
    }
  });
}

function useAction<T, Rest extends any[]>(
  updateConfig: (fn: (config: T) => T) => void,
  action: (obj: T, ...args: Rest) => T
) {
  return useCallback(
    (...args: Rest) => {
      updateConfig(config => {
        return action(config, ...args);
      });
    },
    [action, updateConfig]
  );
}

export const PanelBankGridSection: React.FC<
  {
    gridItemMargin?: number[];
    gridRowHeight?: number;
    gridContainerPadding?: number[];
    showGridDots?: boolean;
    hideEmptyWatermark?: boolean;
    updateConfig: (
      fn: (config: PanelBankSectionConfig) => PanelBankSectionConfig
    ) => void;
    onClickGrid?(): void;
  } & PanelBankSectionComponentSharedProps
> = props => {
  const {updateConfig} = props;

  const gridItemMargin = props.gridItemMargin || GRID_ITEM_MARGIN;
  const gridContainerPadding =
    props.gridContainerPadding || GRID_CONTAINER_PADDING;
  // a hack to make read-only report panels not shrink due to lack of margin
  const gridRowHeight = props.gridRowHeight || GRID_ROW_HEIGHT;
  const panelRefs = props.panelBankSectionConfigRef.panels;
  // Note: not using useWholeMapped below because, with it, section.panels is stale if you delete a panel
  const section = props.panelBankSectionConfigRef;
  const serverGridLayout: GridLayout = [];
  section.panels.forEach((p, i) => {
    serverGridLayout.push({
      ...(p.layout || getNewGridItemLayout(serverGridLayout)), // Add layout to panels that don't have it
      id: panelRefs[i].id,
    });
  });
  const setGridLayout = useAction(updateConfig, actionSetGridLayout);

  const [contentHeightByPanelRefID, setContentHeightByPanelRefID] = useState<{
    [id: string]: number;
  }>({});

  const {dragRef, dropRef, dragData, dragging} = useContext(DragDropContext);
  const [resizingRefId, setResizingRefId] = React.useState<string | null>(null);
  const [resizingPixelWidth, setResizingPixelWidth] = useState<number | null>(
    null
  );
  const [resizingPixelHeight, setResizingPixelHeight] = useState<number | null>(
    null
  );

  const columnWidth = useMemo(
    () =>
      (props.panelBankWidth -
        gridItemMargin[0] * (GRID_COLUMN_COUNT - 1) -
        gridContainerPadding[0] * 2) /
      GRID_COLUMN_COUNT,
    [gridContainerPadding, gridItemMargin, props.panelBankWidth]
  );

  const getGridBottom = useCallback(
    (layout: GridLayout) => {
      if (props.showGridDots) {
        return Math.max(bottom(layout), 6);
      }
      return bottom(layout);
    },
    [props.showGridDots]
  );

  const getLayoutHeight = useCallback(
    (layout: GridLayout) => {
      const bottomY = getGridBottom(layout);
      const minHeight = props.hideEmptyWatermark ? 0 : 150;
      return Math.max(
        bottomY * gridRowHeight +
          (bottomY - 1) * gridItemMargin[1] +
          gridContainerPadding[1] * 2,
        minHeight
      );
    },
    [
      getGridBottom,
      gridContainerPadding,
      gridItemMargin,
      gridRowHeight,
      props.hideEmptyWatermark,
    ]
  );

  // Get nearest grid coordinates for the given pixel values
  const convertToGridCoords = useCallback(
    (xPx: number, yPx: number) => {
      return {
        x: Math.max(
          Math.round(
            (xPx - gridItemMargin[0]) / (columnWidth + gridItemMargin[0])
          ),
          0
        ),
        y: Math.round(
          (yPx - gridItemMargin[1]) / (gridRowHeight + gridItemMargin[1])
        ),
      };
    },
    [columnWidth, gridItemMargin, gridRowHeight]
  );

  const convertToGridWidth = useCallback(
    (w: number, round = true) => {
      const gridWidth =
        (w + gridItemMargin[0]) / (columnWidth + gridItemMargin[0]);
      return round ? Math.round(gridWidth) : gridWidth;
    },
    [columnWidth, gridItemMargin]
  );
  const convertToGridHeight = useCallback(
    (h: number, round = true) => {
      const gridHeight =
        (h + gridItemMargin[1]) / (gridRowHeight + gridItemMargin[1]);
      return round ? Math.round(gridHeight) : gridHeight;
    },
    [gridItemMargin, gridRowHeight]
  );

  // Get grid width and height for the given pixel values
  const convertToGridSize = useCallback(
    (size: {height: number; width: number}): {w: number; h: number} => ({
      w: convertToGridWidth(size.width),
      h: convertToGridHeight(size.height),
    }),
    [convertToGridHeight, convertToGridWidth]
  );

  const convertToPixelCoords = useCallback(
    (x: number, y: number) => {
      return {
        x: Math.round(
          (columnWidth + gridItemMargin[0]) * x + gridContainerPadding[0]
        ),
        y: Math.round(
          (gridRowHeight + gridItemMargin[1]) * y + gridContainerPadding[1]
        ),
      };
    },
    [columnWidth, gridContainerPadding, gridItemMargin, gridRowHeight]
  );

  const convertToPixelSize = useCallback(
    (size: {w: number; h: number}) => {
      return {
        w: Math.round(
          columnWidth * size.w + Math.max(0, size.w - 1) * gridItemMargin[0]
        ),
        h: Math.round(
          gridRowHeight * size.h + Math.max(0, size.h - 1) * gridItemMargin[1]
        ),
      };
    },
    [columnWidth, gridItemMargin, gridRowHeight]
  );

  const getStyleFromLayout = useCallback(
    (layout: GridLayoutItem, useTransform = true) => {
      const {x: left, y: top} = convertToPixelCoords(layout.x, layout.y);
      const size = convertToPixelSize({w: layout.w, h: layout.h});
      return {
        width: size.w,
        height: size.h,
        ...(useTransform
          ? {
              transform: `translate(${left}px, ${top}px)`,
            }
          : {
              left,
              top,
            }),
      } as {
        width: number;
        height: number;
        transform?: string;
        left?: number;
        top?: number;
      };
    },
    [convertToPixelCoords, convertToPixelSize]
  );

  const forceResize = () => {
    setTimeout(() => window.dispatchEvent(new Event('resize')));
  };

  const getPanelSizeFromDragData = (data: any) => ({
    w: (data && data.size && data.size.w) || GRID_ITEM_DEFAULT_WIDTH,
    h: (data && data.size && data.size.h) || GRID_ITEM_DEFAULT_HEIGHT,
  });

  const updateDragoverMouseCoords = (
    ctx: DragDropState,
    e: React.DragEvent<Element>
  ) => {
    const sectionBounds = e.currentTarget.getBoundingClientRect();
    const draggingPanelSize = getPanelSizeFromDragData(dragData);
    const draggingPanelSizePixels = convertToPixelSize(draggingPanelSize);
    const coords = convertToGridCoords(
      e.clientX - sectionBounds.left - draggingPanelSizePixels.w / 2,
      e.clientY - sectionBounds.top - 60
    );
    if (!_.isEqual(coords, dragData && dragData.dragoverMouseCoords)) {
      ctx.setDragData({
        ...dragData,
        dragoverMouseCoords: coords,
      });
    }
  };

  const serverGridLayoutWithoutDragging = produce(serverGridLayout, draft => {
    if (
      dragRef != null &&
      dragging &&
      dragData != null &&
      dragData.dragoverMouseCoords != null
    ) {
      const draggingItemIndex = _.findIndex(draft, {id: dragRef.id});
      if (draggingItemIndex !== -1) {
        draft.splice(draggingItemIndex, 1);
      }
    }
  });

  const draggingOverSection =
    dragData != null && _.isEqual(dropRef, props.panelBankSectionConfigRef);

  const getResizingSize = useCallback(
    (layoutX: number = 0) => {
      if (resizingPixelWidth == null || resizingPixelHeight == null) {
        return null;
      }
      const size = convertToGridSize({
        width: resizingPixelWidth,
        height: resizingPixelHeight,
      });
      size.w = Math.min(
        size.w,
        GRID_COLUMN_COUNT - layoutX // (layout?.x || 0)
      );
      return {w: Math.max(size.w, 1), h: Math.max(size.h, 2)};
    },
    [convertToGridSize, resizingPixelHeight, resizingPixelWidth]
  );

  let derivedGridLayout = produce(serverGridLayoutWithoutDragging, draft => {
    if (resizingRefId != null) {
      const resizingItemIndex = _.findIndex(draft, {id: resizingRefId});
      if (resizingItemIndex !== -1) {
        const resizingItem = draft[resizingItemIndex];
        const resizingSize = getResizingSize(resizingItem?.x);
        if (resizingSize != null) {
          draft[resizingItemIndex].w = resizingSize.w;
          draft[resizingItemIndex].h = resizingSize.h;
        }
      }
    }
    if (
      dragRef != null &&
      dragging &&
      draggingOverSection &&
      dragData != null &&
      dragData.dragoverMouseCoords != null
    ) {
      const size = getPanelSizeFromDragData(dragData);
      draft.push({
        x: Math.min(dragData.dragoverMouseCoords.x, GRID_COLUMN_COUNT - size.w),
        y: dragData.dragoverMouseCoords.y,
        ...size,
        id: 'drop-preview',
      });
    }
  });

  // Stack vertically on mobile
  if (props.panelBankWidth <= 768 && props.readOnly) {
    derivedGridLayout = produce(derivedGridLayout, draft => {
      draft.forEach(layout => {
        layout.w = GRID_COLUMN_COUNT;
        layout.x = 0;
      });
    });
  }

  derivedGridLayout = compact(derivedGridLayout, GRID_COLUMN_COUNT);

  let dropPreview = null;
  const dropPreviewLayout = getLayoutItem(derivedGridLayout, 'drop-preview');
  if (dropPreviewLayout) {
    const style = getStyleFromLayout(dropPreviewLayout, false);
    dropPreview = (
      <div
        key="drop-preview"
        className="drop-preview"
        style={{
          ...style,
        }}
      />
    );
  }

  // This is sum hilarious hax to automatically resize a markdown panel to its content's height
  // It's only active when props.readOnly === true
  derivedGridLayout.forEach(l => {
    const contentHeight = contentHeightByPanelRefID[l.id];
    if (contentHeight == null) {
      return;
    }

    // Abort if there are other panels in the same row
    if (
      derivedGridLayout.find(
        otherL => l !== otherL && heightsIntersect(l, otherL)
      ) != null
    ) {
      return;
    }

    const oldH = l.h;
    // These magic numbers correspond to the padding/border of the elements between here and the content
    l.h = Math.ceil(convertToGridHeight(contentHeight + 32 + 6, false));

    // Shift panels below this one accordingly
    derivedGridLayout.forEach(otherL => {
      if (l !== otherL && otherL.y > l.y) {
        otherL.y += l.h - oldH;
      }
    });
  });

  const lowest = getGridBottom(derivedGridLayout);
  const dots = [];
  if (props.showGridDots) {
    for (let i = 0; i <= lowest / 2; i++) {
      for (let j = 0; j < 13; j++) {
        dots.push([
          (props.panelBankWidth / 12) * j,
          i * (gridRowHeight - 1) * 2,
        ]);
      }
    }
  }

  const empty =
    props.activePanelRefs.length + props.inactivePanelRefs.length === 0;

  // unused
  const highlightIds: string[] = [];

  const activePanelIds = props.activePanelRefs.map(r => r.id);

  const [clickingGrid, setClickingGrid] = useState(false);
  useEffect(() => {
    function onMouseUp() {
      setClickingGrid(false);
    }
    window.addEventListener('mouseup', onMouseUp);
    return () => window.removeEventListener('mouseup', onMouseUp);
  }, []);

  return (
    <div
      className={classNames('grid-section', {
        'resizing-panel': resizingRefId != null,
        empty,
      })}>
      <DropTarget
        partRef={props.panelBankSectionConfigRef}
        style={{
          position: 'relative',
          height: getLayoutHeight(derivedGridLayout),
        }}
        onMouseDown={e => {
          if (e.target === e.currentTarget) {
            setClickingGrid(true);
          }
        }}
        onMouseUp={e => {
          if (clickingGrid && e.target === e.currentTarget) {
            props.onClickGrid?.();
          }
        }}
        onDragEnter={(ctx, e) => {
          updateDragoverMouseCoords(ctx, e);
        }}
        onDragOver={updateDragoverMouseCoords}
        onDrop={() => {
          console.log('ON DROP', dragData, dragRef);
          if (!dragData || !dragRef) {
            return;
          }
          if (
            !_.isEqual(dragData.fromSectionRef, props.panelBankSectionConfigRef)
          ) {
            props.movePanelBetweenSections(
              dragRef,
              dragData.fromSectionRef,
              props.panelBankSectionConfigRef
            );
          }
          const dropPreviewItem = getLayoutItem(
            derivedGridLayout,
            'drop-preview'
          );
          if (dropPreviewItem) {
            dropPreviewItem.id = dragRef.id;
          }
          setGridLayout(derivedGridLayout);
        }}>
        {dropPreview}
        {empty && !props.hideEmptyWatermark ? (
          <EmptyPanelBankSectionWatermark />
        ) : (
          <>
            {dots.map((dot, i) => (
              <div
                className="grid-dot"
                key={`dot-${i}`}
                style={{left: dot[0], top: dot[1]}}
              />
            ))}
            {props.activePanelRefs.map((panelRef, i) => {
              const panelId = activePanelIds[i];

              let layout = getLayoutItem(derivedGridLayout, panelRef.id);
              if (layout == null) {
                // If it's not in the layout, it's probably being dragged,
                // in which case we still need to render it for its drag events to fire,
                // but we want it to be invisible.
                layout = {w: 0, h: 0, x: 0, y: 0, id: ''};
              }
              const selectedForDrag =
                isPanel(dragRef) && _.isEqual(dragRef, panelRef);
              const panelLayoutStyle = getStyleFromLayout(
                layout,
                !isFirefox && (!selectedForDrag || dragging)
              );

              // This is sum hilarious hax to automatically resize a markdown panel to its content's height
              // It's only active when props.readOnly === true
              const onContentHeightChanged = props.readOnly
                ? (h: number) =>
                    setContentHeightByPanelRefID(old => ({
                      ...old,
                      [panelRef.id]: h,
                    }))
                : undefined;

              const resizingSize = getResizingSize(layout?.x);

              const isResizing =
                resizingRefId != null &&
                resizingSize != null &&
                resizingRefId === panelRef.id;

              const panelPixelSize = isResizing
                ? {w: resizingPixelWidth, h: resizingPixelHeight}
                : {w: panelLayoutStyle.width, h: panelLayoutStyle.height};

              return (
                <Resizable
                  className={classNames(
                    'panel-bank__panel',
                    `col-${layout.w}`,
                    {
                      [`panel-bank__panel-id__${panelId}`]: panelId != null,
                      // 300 so the draggable handle does not overlap with action icons
                      'panel-bank__panel-small': panelLayoutStyle.width < 300,
                      resizing: isResizing,
                      dragging: selectedForDrag && dragging,
                      'panel-highlight':
                        panelId != null && highlightIds.includes(panelId),
                    }
                  )}
                  key={panelRef.id}
                  width={panelPixelSize?.w ?? 0}
                  height={panelPixelSize?.h ?? 0}
                  minConstraints={[columnWidth, gridRowHeight]}
                  onResize={(e, data) => {
                    setResizingPixelWidth(data.size.width);
                    setResizingPixelHeight(data.size.height);
                    forceResize();
                  }}
                  onResizeStart={() => {
                    setResizingRefId(panelRef.id);
                  }}
                  onResizeStop={() => {
                    // Must be in a timeout otherwise we hit an issue related to a race
                    // condition inside an on layout hook inside of Slate
                    setTimeout(() => {
                      setResizingRefId(null);
                      setResizingPixelHeight(null);
                      setResizingPixelWidth(null);
                      setGridLayout(derivedGridLayout);
                    }, 1);
                  }}>
                  <DragSource
                    style={panelLayoutStyle}
                    partRef={panelRef}
                    onMouseUp={e => {
                      skipTransition(e.currentTarget, 50);
                    }}
                    data={{
                      fromSectionRef: props.panelBankSectionConfigRef,
                      size: {w: layout.w, h: layout.h},
                    }}>
                    {props.renderPanel(panelRef, onContentHeightChanged)}
                  </DragSource>
                </Resizable>
              );
            })}
          </>
        )}
      </DropTarget>
    </div>
  );
};

function heightsIntersect(l1: GridLayoutItem, l2: GridLayoutItem) {
  const higher = l2.y < l1.y ? l2 : l1;
  const lower = higher === l1 ? l2 : l1;
  return lower.y < higher.y + higher.h;
}
