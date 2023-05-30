import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {
  DragDropContext,
  DragDropState,
  DragSource,
  DropTarget,
} from '@wandb/weave/common/containers/DragDropContainer';
import classNames from 'classnames';
import produce from 'immer';
import _ from 'lodash';
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {Resizable, ResizeCallbackData} from 'react-resizable';
import {Button} from 'semantic-ui-react';

import {
  DEFAULT_PANEL_SIZE,
  isDraggingWithinSection,
  isPanel,
  PanelBankFlowSectionConfig,
  PanelBankSectionComponentSharedProps,
  PanelBankSectionConfig,
} from './panelbank';
import EmptyPanelBankSectionWatermark from './PanelBankEmptySectionWatermark';
import {
  getBoxDimensions,
  getColumnWidth,
  getPagingParams,
  isMobile,
  panelOnActivePage,
} from './panelbankFlow';
import {isFirefox, skipTransition} from './panelbankUtil';

type AllPanelBankFlowSectionProps = PanelBankSectionComponentSharedProps & {
  flowConfig: PanelBankFlowSectionConfig;
  currentPage: number;
  setCurrentPage: (newCurrentPage: number) => void;
  updateFlowConfig: (
    newFlowConfig: Partial<PanelBankFlowSectionConfig>
  ) => void;
};

const PanelBankFlowSectionInnerComp: React.FC<AllPanelBankFlowSectionProps> = ({
  panelBankSectionConfigRef,
  panelBankWidth,
  panelBankHeight,
  activePanelRefs,
  inactivePanelRefs,
  movePanelBetweenSections: movePanel,
  updateFlowConfig,
  renderPanel,
  flowConfig,
  currentPage,
  setCurrentPage,
}: AllPanelBankFlowSectionProps) => {
  const {dragRef, dragging, dropRef, dragData, setDragData} =
    useContext(DragDropContext);
  const [resizingRefId, setResizingRefId] = useState<string | null>(null);

  const [resizingSectionHeight, setResizingSectionHeight] = useState<
    number | null
  >(null);

  const {rowsPerPage, gutterWidth} = flowConfig;
  const dragIndex = _.isEqual(
    dragData?.fromSectionRef,
    panelBankSectionConfigRef
  )
    ? dragData?.dragIndex
    : undefined;
  const dropIndex = _.isEqual(dropRef, panelBankSectionConfigRef)
    ? dragData?.dropIndex
    : undefined;
  const mobile = isMobile();
  const {boxWidth, boxHeight} = getBoxDimensions(
    panelBankWidth,
    panelBankHeight,
    flowConfig
  );

  const [resizingSize, setResizingSize] = useState<{
    width: number;
    height: number;
  }>({width: boxWidth, height: boxHeight});

  const panelCount = activePanelRefs.length;
  const {panelsPerPage, panelsPerRow, maxPage} = getPagingParams({
    panelBankWidth,
    panelBankHeight,
    panelCount,
    flowConfig,
  });
  const paginationHeight = maxPage > 0 ? 32 : 0;
  const pageHeight = resizingSectionHeight
    ? resizingSectionHeight
    : panelCount === 0 && dragData?.dropIndex == null
    ? 0
    : (panelCount <= panelsPerRow ? 1 : rowsPerPage) *
      (gutterWidth + boxHeight);

  const startPanelIndex = currentPage * panelsPerPage;

  // renderPanels is the same length as activePanels, but non-visible panels are set to false
  // This is so panels maintain the same index -- otherwise, panels get unnecessarily re-rerendered
  const renderPanelRefs = activePanelRefs.map((pr, i) =>
    panelOnActivePage(i, currentPage, panelsPerPage) ? pr : false
  );

  // Returns [x,y] px position for a box at the given index
  const getBoxPosition = useCallback(
    (boxPositionIndex: number) => {
      return [
        gutterWidth +
          (boxPositionIndex % panelsPerRow) * (boxWidth + gutterWidth),
        Math.floor(boxPositionIndex / panelsPerRow) * (boxHeight + gutterWidth),
      ];
    },
    [boxHeight, boxWidth, gutterWidth, panelsPerRow]
  );

  const dropPreviewPosition = dropIndex != null && getBoxPosition(dropIndex);
  const draggingWithinSection = isDraggingWithinSection(
    panelBankSectionConfigRef,
    dragData
  );

  const noPanels = activePanelRefs.length + inactivePanelRefs.length === 0;

  // Returns the panel index of the current drop target
  const getDropIndex = useCallback(
    (xPx: number, yPx: number) => {
      const x = Math.floor(xPx / (boxWidth + gutterWidth));
      const y = Math.floor(yPx / (boxHeight + gutterWidth));
      return x + y * panelsPerRow;
    },
    [boxHeight, boxWidth, gutterWidth, panelsPerRow]
  );

  const onDragOver = useCallback(
    (ctx: DragDropState, e: React.DragEvent) => {
      const sectionBounds = e.currentTarget.getBoundingClientRect();
      const mousePosition = {
        xPx: e.clientX - sectionBounds.left,
        yPx: currentPage * pageHeight + e.clientY - sectionBounds.top,
      };
      const newDropBoxIndex = Math.min(
        getDropIndex(mousePosition.xPx, Math.max(0, mousePosition.yPx)),
        isDraggingWithinSection(panelBankSectionConfigRef, dragData) &&
          panelCount > 0
          ? panelCount - 1
          : panelCount
      );
      if (newDropBoxIndex !== dragData?.dropIndex) {
        setDragData({
          ...(dragData ?? {}),
          dropIndex: newDropBoxIndex,
        });
      }
    },
    [
      currentPage,
      dragData,
      getDropIndex,
      pageHeight,
      panelBankSectionConfigRef,
      panelCount,
      setDragData,
    ]
  );

  const getThisColumnWidth = useCallback(
    (columnCount?: number) =>
      getColumnWidth(panelBankWidth, flowConfig, columnCount),
    [panelBankWidth, flowConfig]
  );

  // Given a px width, returns the closest number of columns to accomodate that width.
  // (Enables 'snap to columns' behavior when resizing panels.)
  const getClosestColumnCount = useCallback(
    (pxWidth: number) => {
      const snapWidths = [1, 2, 3, 4, 5, 6, 7, 8].map(getThisColumnWidth);
      let closestIndex = 0;
      snapWidths.forEach((columnWidth, i) => {
        if (
          Math.abs(pxWidth - columnWidth) <
          Math.abs(pxWidth - snapWidths[closestIndex])
        ) {
          closestIndex = i;
        }
      });
      return closestIndex + 1;
    },
    [getThisColumnWidth]
  );

  // If panelbank config changes, dispatch Event('resize') to trigger panel width recalculation
  const prevFlowConfigRef = useRef(flowConfig);
  useEffect(() => {
    const prevFlowConfig = prevFlowConfigRef.current;
    prevFlowConfigRef.current = flowConfig;
    if (_.isEqual(prevFlowConfig, flowConfig)) {
      return;
    }
    setTimeout(() => window.dispatchEvent(new Event('resize')), 1);
  }, [flowConfig]);

  // If you're on, say, page 3, and then you filter panels but there's only 1 page of results,
  // currentPage will be greater than maxPage, so we clamp it here
  useEffect(() => {
    if (currentPage > maxPage) {
      setCurrentPage(maxPage);
    }
  }, [currentPage, maxPage, setCurrentPage]);

  const getSnappedWidth = useCallback(
    (w: number) => {
      if (flowConfig.snapToColumns == null) {
        return w;
      }
      const newColumnCount = getClosestColumnCount(w);
      return getThisColumnWidth(newColumnCount);
    },
    [flowConfig.snapToColumns, getClosestColumnCount, getThisColumnWidth]
  );

  const onPanelResizeStop = useCallback(
    (e, data) => {
      const newColumnCount = getClosestColumnCount(data.size.width);
      const newWidth = getSnappedWidth(data.size.width);
      const newHeight = data.size.height;
      updateFlowConfig({
        columnsPerPage: newColumnCount,
        boxWidth: newWidth,
        boxHeight: newHeight,
      });
      setResizingSize({width: newWidth, height: newHeight});
      setResizingRefId(null);
    },
    [getClosestColumnCount, getSnappedWidth, updateFlowConfig]
  );

  const onPanelResize = useCallback(
    (e: React.SyntheticEvent<Element, Event>, data: ResizeCallbackData) => {
      setResizingSize({
        width: data.size.width,
        height: data.size.height,
      });
    },
    []
  );

  const panelResizePreviewStyle = useMemo(() => {
    if (mobile || resizingRefId == null) {
      return {display: 'none'};
    }
    const panelResizePreviewPosition = getBoxPosition(
      _.findIndex(renderPanelRefs, {id: resizingRefId}) % panelsPerPage
    );
    return {
      height: resizingSize.height,
      width: getSnappedWidth(resizingSize.width),
      transform:
        panelResizePreviewPosition == null
          ? undefined
          : `translate(${panelResizePreviewPosition[0] + gutterWidth}px, ${
              panelResizePreviewPosition[1]
            }px) `,
    };
  }, [
    getBoxPosition,
    getSnappedWidth,
    gutterWidth,
    mobile,
    panelsPerPage,
    renderPanelRefs,
    resizingRefId,
    resizingSize.height,
    resizingSize.width,
  ]);

  return (
    <>
      <div className="resize-preview" style={panelResizePreviewStyle} />
      <Resizable
        width={NaN}
        height={noPanels ? DEFAULT_PANEL_SIZE : pageHeight}
        axis="y"
        onResize={(e, data) => {
          const maxRows = Math.ceil(panelCount / panelsPerRow);
          updateFlowConfig({
            rowsPerPage: Math.max(
              1,
              Math.min(
                maxRows,
                Math.round(pageHeight / (boxHeight + gutterWidth))
              )
            ),
          });
          setResizingSectionHeight(data.size.height);
        }}
        onResizeStop={() => {
          const maxRows = Math.ceil(panelCount / panelsPerRow);
          const firstVisiblePanelIndex = panelsPerPage * currentPage;
          const newRowsPerPage = Math.max(
            1,
            Math.min(
              maxRows,
              Math.round(pageHeight / (boxHeight + gutterWidth))
            )
          );
          const newCurrentPage = Math.floor(
            firstVisiblePanelIndex / (newRowsPerPage * panelsPerRow)
          );
          updateFlowConfig({rowsPerPage: newRowsPerPage});
          setCurrentPage(newCurrentPage);
          setResizingSectionHeight(null);
        }}
      >
        <div
          className={`flow-section ${
            resizingSectionHeight != null ? 'resizing-section' : ''
          } ${resizingRefId != null ? 'resizing-panel' : ''}
          ${mobile ? 'mobile' : ''}`}
          style={{
            height: noPanels
              ? DEFAULT_PANEL_SIZE
              : pageHeight + paginationHeight,
          }}
        >
          <DropTarget
            className="flow-section__page"
            style={{
              // HAX: While dragging, we extend the drop target to overlap the section title so that
              // rearranging panels still works when the panel is dropped in the title area.
              // This assumes that the height of the section title area is 48px.
              height: noPanels
                ? DEFAULT_PANEL_SIZE
                : pageHeight + (dragging ? 48 : 0),
              paddingTop: dragging ? 48 : 0,
              top: -(dragging ? 48 : 0),
            }}
            partRef={panelBankSectionConfigRef}
            isValidDropTarget={ctx => isPanel(ctx.dragRef)}
            onDragOver={onDragOver}
            onDrop={() => {
              if (
                movePanel != null &&
                dragRef &&
                dragData &&
                dropIndex != null
              ) {
                // Unfortunately movePanel is optional because of the way panelbank is reused
                // in reports. But it's always passed for PanelBankFlowSection, which is
                // only used in workspaces.
                movePanel(
                  dragRef,
                  dragData.fromSectionRef,
                  panelBankSectionConfigRef,
                  dropIndex,
                  new Set(inactivePanelRefs.map(r => r.id))
                );
              }
            }}
          >
            {noPanels ? (
              <EmptyPanelBankSectionWatermark />
            ) : (
              <div
                style={{
                  height: (maxPage + 1) * pageHeight,
                  position: 'relative',
                  transform: `translateY(-${currentPage * pageHeight}px)`,
                  transition: 'transform 0.5s',
                }}
              >
                {dropPreviewPosition && (
                  <div
                    key="drop-preview"
                    className="drop-preview"
                    style={{
                      width: boxWidth,
                      height: boxHeight,
                      transform: `translate(${dropPreviewPosition[0]}px, ${dropPreviewPosition[1]}px) `,
                    }}
                  />
                )}
                {renderPanelRefs.map(panelRef => {
                  if (!panelRef) {
                    return null;
                  }
                  const panelRefId = panelRef.id;
                  const isResizing = resizingRefId === panelRefId;
                  const selectedForDrag =
                    dragRef && _.isEqual(dragRef, panelRef);

                  let boxPositionIndex = _.findIndex(renderPanelRefs, {
                    id: panelRefId,
                  });
                  // Slide panels to make room during drag+drop
                  if (dropIndex != null) {
                    if (selectedForDrag) {
                      boxPositionIndex = Math.min(
                        dropIndex,
                        renderPanelRefs.length - 1
                      );
                    } else if (draggingWithinSection) {
                      // dragging a panel from the same section to a lower index
                      if (
                        boxPositionIndex >= dropIndex &&
                        dragIndex != null &&
                        boxPositionIndex <= dragIndex
                      ) {
                        boxPositionIndex = boxPositionIndex + 1;
                      } else if (
                        // dragging a panel from the same section to a higher index
                        boxPositionIndex <= dropIndex &&
                        dragIndex != null &&
                        boxPositionIndex > dragIndex
                      ) {
                        boxPositionIndex = boxPositionIndex - 1;
                      }
                    } else if (
                      // dragging a panel from a different section
                      !draggingWithinSection &&
                      boxPositionIndex >= dropIndex
                    ) {
                      boxPositionIndex = boxPositionIndex + 1;
                    }
                  }
                  const boxPosition = getBoxPosition(boxPositionIndex);
                  return (
                    <React.Fragment key={panelRefId}>
                      <Resizable
                        key={panelRefId}
                        className={classNames('panel-bank__panel', {
                          // 300 so the draggable handle does not overlap with action icons
                          'panel-bank__panel-small': boxWidth < 300,
                          resizing: isResizing,
                          dragging: selectedForDrag && dragging,
                        })}
                        axis={mobile ? undefined : 'both'}
                        width={resizingSize.width}
                        height={resizingSize.height}
                        minConstraints={[
                          DEFAULT_PANEL_SIZE,
                          DEFAULT_PANEL_SIZE,
                        ]}
                        maxConstraints={[
                          panelBankWidth - 2 * gutterWidth,
                          panelBankWidth,
                        ]}
                        onResize={onPanelResize}
                        onResizeStop={onPanelResizeStop}
                        onResizeStart={() => setResizingRefId(panelRefId)}
                      >
                        <DragSource
                          key={panelRefId}
                          partRef={panelRef}
                          data={{
                            fromSectionRef: panelBankSectionConfigRef,
                            dragIndex: boxPositionIndex,
                          }}
                          onMouseUp={e => {
                            skipTransition(e.currentTarget, 50);
                          }}
                          style={{
                            width: boxWidth,
                            height: boxHeight,
                            ...((selectedForDrag && !dragging) || isFirefox
                              ? {
                                  left: boxPosition[0],
                                  top: boxPosition[1],
                                }
                              : {
                                  transform: `translate(${boxPosition[0]}px, ${boxPosition[1]}px)`,
                                }),
                          }}
                        >
                          {renderPanel(panelRef)}
                        </DragSource>
                      </Resizable>
                    </React.Fragment>
                  );
                })}
              </div>
            )}
          </DropTarget>
          {maxPage > 0 && (
            <div className="flow-section__pagination">
              <div className="pagination-controls">
                <div className="pagination-count">
                  {startPanelIndex + 1}-
                  {Math.min(startPanelIndex + panelsPerPage, panelCount)} of{' '}
                  {panelCount}
                </div>
                <Button.Group className="pagination-buttons">
                  <Button
                    disabled={currentPage === 0}
                    className="page-up wb-icon-button"
                    size="tiny"
                    onClick={() => setCurrentPage(currentPage - 1)}
                  >
                    <DropTarget
                      partRef={panelBankSectionConfigRef}
                      isValidDropTarget={ctx => isPanel(ctx.dragRef)}
                      onDragEnter={() => {
                        setCurrentPage(currentPage - 1);
                      }}
                    >
                      <LegacyWBIcon name="previous" />
                    </DropTarget>
                  </Button>
                  <Button
                    disabled={currentPage === maxPage}
                    className="page-down wb-icon-button"
                    size="tiny"
                    onClick={() => setCurrentPage(currentPage + 1)}
                  >
                    <DropTarget
                      partRef={panelBankSectionConfigRef}
                      isValidDropTarget={ctx => isPanel(ctx.dragRef)}
                      onDragEnter={() => {
                        setCurrentPage(currentPage + 1);
                      }}
                    >
                      <LegacyWBIcon name="next" />
                    </DropTarget>
                  </Button>
                </Button.Group>
              </div>
            </div>
          )}
        </div>
      </Resizable>
    </>
  );
};

const PanelBankFlowSectionInner = PanelBankFlowSectionInnerComp;

export function actionSetFlowConfig(
  sectionConfig: PanelBankSectionConfig,
  newFlowConfig: Partial<PanelBankFlowSectionConfig>
): PanelBankSectionConfig {
  return produce(sectionConfig, draft => {
    draft.flowConfig = {
      ...sectionConfig.flowConfig,
      ...newFlowConfig,
    };
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

const PanelBankFlowSectionComp = (
  props: {
    updateConfig: (
      fn: (config: PanelBankSectionConfig) => PanelBankSectionConfig
    ) => void;
  } & PanelBankSectionComponentSharedProps
) => {
  const {panelBankSectionConfigRef, updateConfig} = props;
  const {flowConfig} = panelBankSectionConfigRef;
  // const {flowConfig} = ViewHooks.usePart(panelBankSectionConfigRef);
  const updateFlowConfig = useAction(updateConfig, actionSetFlowConfig);

  const [currentPage, setCurrentPage] = useState(0);
  // const currentPage =
  //   currentPageBySectionRefID[panelBankSectionConfigRef.id] ?? 0;
  // const setCurrentPage = useCallback(
  //   (newCurrentPage: number) => {
  //     setCurrentPageForSectionRefID(
  //       panelBankSectionConfigRef.id,
  //       newCurrentPage
  //     );
  //   },

  return (
    <PanelBankFlowSectionInner
      {...props}
      currentPage={currentPage}
      setCurrentPage={setCurrentPage}
      flowConfig={flowConfig}
      updateFlowConfig={updateFlowConfig}
    />
  );
};

export const PanelBankFlowSection = PanelBankFlowSectionComp;
