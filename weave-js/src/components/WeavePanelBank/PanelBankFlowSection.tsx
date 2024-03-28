import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {DropTarget} from '@wandb/weave/common/containers/DragDropContainer';
import classNames from 'classnames';
import {produce} from 'immer';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Resizable, ResizeCallbackData} from 'react-resizable';
import {Button} from 'semantic-ui-react';

import {
  DEFAULT_PANEL_SIZE,
  isPanel,
  PanelBankFlowSectionConfig,
  PanelBankSectionComponentSharedProps,
  PanelBankSectionConfig,
} from './panelbank';
import EmptyPanelBankSectionWatermark from './PanelBankEmptySectionWatermark';
import {
  getBoxDimensions,
  getPagingParams,
  getSnappedDimension,
  getSnappedItemCount,
  isMobile,
  panelOnActivePage,
} from './panelbankFlow';
import {isFirefox} from './panelbankUtil';

type AllPanelBankFlowSectionProps = PanelBankSectionComponentSharedProps & {
  panelBankSectionConfigRef: Required<PanelBankSectionConfig>;
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
  // movePanelBetweenSections: movePanel,
  updateFlowConfig,
  renderPanel,
  flowConfig,
  currentPage,
  setCurrentPage,
}: AllPanelBankFlowSectionProps) => {
  const [resizingRefId, setResizingRefId] = useState<string | null>(null);

  const {snapToColumns, gutterWidth, columnsPerPage, rowsPerPage} = flowConfig;

  const panelCount = activePanelRefs.length;
  const {panelsPerPage, panelsPerRow, maxPage} = getPagingParams({
    containerWidth: panelBankWidth,
    containerHeight: panelBankHeight,
    panelCount,
    flowConfig,
  });
  const paginationHeight = maxPage > 0 ? 32 : 0;
  const pageHeight = panelBankHeight - paginationHeight;

  // If you're on, say, page 3, and then you filter panels but there's only 1 page of results,
  // currentPage will be greater than maxPage, so we clamp it here
  useEffect(() => {
    if (currentPage > maxPage) {
      setCurrentPage(maxPage);
    }
  }, [currentPage, maxPage, setCurrentPage]);

  const startPanelIndex = currentPage * panelsPerPage;

  const mobile = isMobile();
  const {boxWidth, boxHeight} = getBoxDimensions({
    containerWidth: panelBankWidth,
    containerHeight: pageHeight,
    flowConfig,
  });

  const [resizingPanelSize, setResizingPanelSize] = useState<{
    width: number;
    height: number;
  }>({width: boxWidth, height: boxHeight});

  // TODO: do we still need this? probably not
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

  const noPanels = activePanelRefs.length + inactivePanelRefs.length === 0;

  const getClosestColumnCount = useCallback(
    (pxWidth: number) => {
      return getSnappedItemCount({
        unsnappedPx: pxWidth,
        gutterPx: gutterWidth,
        containerPx: panelBankWidth,
      });
    },
    [gutterWidth, panelBankWidth]
  );

  const getClosestRowCount = useCallback(
    (pxHeight: number) => {
      return getSnappedItemCount({
        unsnappedPx: pxHeight,
        gutterPx: gutterWidth,
        containerPx: pageHeight,
      });
    },
    [gutterWidth, pageHeight]
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

  const getSnappedWidth = useCallback(
    ({unsnappedWidth}: {unsnappedWidth: number}) => {
      if (snapToColumns == null) {
        return unsnappedWidth;
      }
      return getSnappedDimension({
        unsnappedPx: unsnappedWidth,
        containerPx: panelBankWidth,
        gutterPx: gutterWidth,
      });
    },
    [gutterWidth, panelBankWidth, snapToColumns]
  );

  const getSnappedHeight = useCallback(
    ({unsnappedHeight}: {unsnappedHeight: number}) => {
      if (snapToColumns == null) {
        return unsnappedHeight;
      }
      return getSnappedDimension({
        unsnappedPx: unsnappedHeight,
        containerPx: pageHeight,
        // containerPx: panelBankHeight,
        gutterPx: gutterWidth,
      });
    },
    [gutterWidth, pageHeight, snapToColumns]
  );

  const onPanelResizeStop = useCallback(
    (e, data) => {
      const newFlowConfig = {
        columnsPerPage: getClosestColumnCount(data.size.width),
        rowsPerPage: getClosestRowCount(data.size.height),
        boxWidth: getSnappedWidth({unsnappedWidth: data.size.width}),
        boxHeight: getSnappedHeight({unsnappedHeight: data.size.height}),
      };
      updateFlowConfig(newFlowConfig);

      setResizingPanelSize({
        width: newFlowConfig.boxWidth,
        height: newFlowConfig.boxHeight,
      });
      setResizingRefId(null);
    },
    [
      getClosestColumnCount,
      getClosestRowCount,
      getSnappedHeight,
      getSnappedWidth,
      updateFlowConfig,
    ]
  );

  // This state stores [rowsPerPage, columnsPerPage].
  // Updates dynamically onPanelResize, to show the '3x4' text overlay indicating the new grid size
  const [resizingGridSize, setResizingGridSize] = useState([
    columnsPerPage,
    rowsPerPage,
  ]);

  const onPanelResize = useCallback(
    (e: React.SyntheticEvent<Element, Event>, data: ResizeCallbackData) => {
      setResizingPanelSize({
        width: data.size.width,
        height: data.size.height,
      });
      setResizingGridSize([
        getClosestColumnCount(data.size.width),
        getClosestRowCount(data.size.height),
      ]);
    },
    [getClosestColumnCount, getClosestRowCount]
  );

  const panelResizePreviewStyle = useMemo(() => {
    if (mobile || resizingRefId == null) {
      return {display: 'none'};
    }
    const panelResizePreviewPosition = getBoxPosition(
      _.findIndex(renderPanelRefs, {id: resizingRefId}) % panelsPerPage
    );
    return {
      height: getSnappedHeight({unsnappedHeight: resizingPanelSize.height}),
      width: getSnappedWidth({unsnappedWidth: resizingPanelSize.width}),
      transform:
        panelResizePreviewPosition == null
          ? undefined
          : `translate(${panelResizePreviewPosition[0] + gutterWidth}px, ${
              panelResizePreviewPosition[1]
            }px) `,
    };
  }, [
    getBoxPosition,
    getSnappedHeight,
    getSnappedWidth,
    gutterWidth,
    mobile,
    panelsPerPage,
    renderPanelRefs,
    resizingRefId,
    resizingPanelSize.height,
    resizingPanelSize.width,
  ]);

  return (
    <>
      <div className="resize-preview" style={panelResizePreviewStyle}>
        <div className="resize-preview-message">
          <h2>{`${resizingGridSize[0]} x ${resizingGridSize[1]}`}</h2>
        </div>
      </div>
      <div
        className={`flow-section ${
          resizingRefId != null ? 'resizing-panel' : ''
        }
          ${mobile ? 'mobile' : ''}`}
        style={{
          height: DEFAULT_PANEL_SIZE,
        }}>
        <div
          // TODO: do we even still need this div?
          className="flow-section__page"
          style={{
            height: noPanels ? DEFAULT_PANEL_SIZE : pageHeight, // + (dragging ? 48 : 0),
          }}>
          {noPanels ? (
            <EmptyPanelBankSectionWatermark />
          ) : (
            <div
              style={{
                height: (maxPage + 1) * pageHeight,
                position: 'relative',
                transform: `translateY(-${
                  currentPage * pageHeight - currentPage * gutterWidth
                }px)`,
                transition: 'transform 0.5s',
              }}>
              {renderPanelRefs.map(panelRef => {
                if (!panelRef) {
                  return null;
                }
                const panelRefId = panelRef.id;
                const isResizing = resizingRefId === panelRefId;
                const boxPositionIndex = _.findIndex(renderPanelRefs, {
                  id: panelRefId,
                });
                const boxPosition = getBoxPosition(boxPositionIndex);
                return (
                  <React.Fragment key={panelRefId}>
                    <Resizable
                      key={panelRefId}
                      className={classNames('panel-bank__panel', {
                        // 300 so the draggable handle does not overlap with action icons
                        'panel-bank__panel-small': boxWidth < 300,
                        resizing: isResizing,
                      })}
                      axis={mobile ? undefined : 'both'}
                      width={resizingPanelSize.width}
                      height={resizingPanelSize.height}
                      minConstraints={[DEFAULT_PANEL_SIZE, DEFAULT_PANEL_SIZE]}
                      maxConstraints={[
                        panelBankWidth - 2 * gutterWidth,
                        panelBankWidth,
                      ]}
                      onResize={onPanelResize}
                      onResizeStop={onPanelResizeStop}
                      onResizeStart={() => setResizingRefId(panelRefId)}>
                      <div
                        key={panelRefId}
                        style={{
                          width: boxWidth,
                          height: boxHeight,
                          ...(isFirefox
                            ? {
                                left: boxPosition[0],
                                top: boxPosition[1],
                              }
                            : {
                                transform: `translate(${boxPosition[0]}px, ${boxPosition[1]}px)`,
                              }),
                        }}>
                        {renderPanel(panelRef)}
                      </div>
                    </Resizable>
                  </React.Fragment>
                );
              })}
            </div>
          )}
        </div>
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
                  onClick={() => setCurrentPage(currentPage - 1)}>
                  <DropTarget
                    partRef={panelBankSectionConfigRef}
                    isValidDropTarget={ctx => isPanel(ctx.dragRef)}
                    onDragEnter={() => {
                      setCurrentPage(currentPage - 1);
                    }}>
                    <LegacyWBIcon name="previous" />
                  </DropTarget>
                </Button>
                <Button
                  disabled={currentPage === maxPage}
                  className="page-down wb-icon-button"
                  size="tiny"
                  onClick={() => setCurrentPage(currentPage + 1)}>
                  <DropTarget
                    partRef={panelBankSectionConfigRef}
                    isValidDropTarget={ctx => isPanel(ctx.dragRef)}
                    onDragEnter={() => {
                      setCurrentPage(currentPage + 1);
                    }}>
                    <LegacyWBIcon name="next" />
                  </DropTarget>
                </Button>
              </Button.Group>
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export function actionSetFlowConfig(
  sectionConfig: PanelBankSectionConfig,
  newFlowConfig: Partial<PanelBankFlowSectionConfig>
): PanelBankSectionConfig {
  return produce(sectionConfig, draft => {
    draft.flowConfig = {
      ...sectionConfig.flowConfig!,
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
  const {updateConfig} = props;
  const panelBankSectionConfigRef =
    props.panelBankSectionConfigRef as Required<PanelBankSectionConfig>;
  const {flowConfig} = panelBankSectionConfigRef;

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
  if (props.panelBankHeight === 0) {
    // TODO: better loading state?
    return <></>;
  }

  return (
    <PanelBankFlowSectionInnerComp
      {...props}
      panelBankSectionConfigRef={panelBankSectionConfigRef}
      currentPage={currentPage}
      setCurrentPage={setCurrentPage}
      flowConfig={flowConfig}
      updateFlowConfig={updateFlowConfig}
    />
  );
};

export const PanelBankFlowSection = PanelBankFlowSectionComp;
