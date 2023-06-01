import {PanelBankFlowSectionConfig} from './panelbank';

export interface CurrentPageBySectionRefID {
  [sectionRefID: string]: number;
}

export function panelOnActivePage(
  panelIndex: number,
  currentPage: number,
  panelsPerPage: number
): boolean {
  const startPanelIndex = currentPage * panelsPerPage;
  return (
    panelIndex >= startPanelIndex &&
    panelIndex < (currentPage + 1) * panelsPerPage
  );
}

export interface GetPagingParamsParams {
  containerWidth: number;
  containerHeight: number;
  panelCount: number;
  flowConfig: PanelBankFlowSectionConfig;
}

export interface PagingParams {
  panelsPerRow: number;
  panelsPerPage: number;
  maxPage: number;
}

export function getPagingParams({
  containerWidth,
  containerHeight,
  panelCount,
  flowConfig,
}: GetPagingParamsParams): PagingParams {
  const {gutterWidth, rowsPerPage} = flowConfig;
  const {boxWidth} = getBoxDimensions({
    containerWidth,
    containerHeight,
    flowConfig,
  });
  const panelsPerRow = Math.max(
    1,
    Math.floor(containerWidth / (boxWidth + gutterWidth))
  );
  const panelsPerPage = panelsPerRow * rowsPerPage;
  const maxPage = Math.max(0, Math.ceil(panelCount / panelsPerPage) - 1);
  return {
    panelsPerRow,
    panelsPerPage,
    maxPage,
  };
}

export interface BoxDimensions {
  boxWidth: number;
  boxHeight: number;
}

// Returns a standard size if on mobile, custom size if not
export function getBoxDimensions({
  containerWidth,
  containerHeight,
  flowConfig,
}: {
  containerWidth: number;
  containerHeight: number;
  flowConfig: PanelBankFlowSectionConfig;
}): BoxDimensions {
  const {gutterWidth, columnsPerPage, rowsPerPage, snapToColumns, boxWidth} =
    flowConfig;

  const boxHeight = getBoxDimension({
    containerPx: containerHeight,
    gutterPx: gutterWidth,
    boxesPerDimension: rowsPerPage,
  });

  if (isMobile()) {
    return {boxWidth: containerWidth - 2 * gutterWidth, boxHeight};
  }
  if (!snapToColumns) {
    return {boxWidth, boxHeight};
  }
  return {
    boxWidth: getBoxDimension({
      containerPx: containerWidth,
      gutterPx: gutterWidth,
      boxesPerDimension: columnsPerPage,
    }),
    boxHeight,
  };
}

export function getBoxDimension({
  containerPx,
  gutterPx,
  boxesPerDimension,
}: {
  containerPx: number;
  gutterPx: number;
  boxesPerDimension: number; // columnsPerPage or rowsPerPage
}) {
  return Math.floor(
    (containerPx - gutterPx * (boxesPerDimension + 1)) / boxesPerDimension
  );
}

export const getSnappedItemCount = ({
  unsnappedPx,
  gutterPx,
  containerPx,
}: {
  unsnappedPx: number;
  gutterPx: number;
  containerPx: number;
}) => {
  const snapWidths = [...Array(12).keys()].map(colCount =>
    getBoxDimension({containerPx, gutterPx, boxesPerDimension: colCount + 1})
  );
  let closestIndex = 0;
  snapWidths.forEach((columnWidth, i) => {
    if (
      Math.abs(unsnappedPx - columnWidth) <
      Math.abs(unsnappedPx - snapWidths[closestIndex])
    ) {
      closestIndex = i;
    }
  });
  return closestIndex + 1;
};

export const getSnappedDimension = ({
  unsnappedPx,
  containerPx,
  gutterPx,
}: {
  unsnappedPx: number;
  containerPx: number;
  gutterPx: number;
}) => {
  const newItemCount = getSnappedItemCount({
    unsnappedPx,
    containerPx,
    gutterPx,
  });
  return getBoxDimension({
    containerPx,
    gutterPx,
    boxesPerDimension: newItemCount,
  });
};

// TODO: we should have a standard isMobile check somewhere else
export function isMobile(): boolean {
  return window.innerWidth <= 852;
}
