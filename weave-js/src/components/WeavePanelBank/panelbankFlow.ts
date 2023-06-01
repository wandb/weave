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
  panelBankWidth: number;
  panelBankHeight: number;
  panelCount: number;
  flowConfig: PanelBankFlowSectionConfig;
}

export interface PagingParams {
  panelsPerRow: number;
  panelsPerPage: number;
  maxPage: number;
}

export function getPagingParams({
  panelBankWidth,
  panelBankHeight,
  panelCount,
  flowConfig,
}: GetPagingParamsParams): PagingParams {
  const {gutterWidth, rowsPerPage} = flowConfig;
  const {boxWidth} = getBoxDimensions(
    panelBankWidth,
    panelBankHeight,
    flowConfig
  );
  const panelsPerRow = Math.max(
    1,
    Math.floor(panelBankWidth / (boxWidth + gutterWidth))
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
export function getBoxDimensions(
  panelBankWidth: number,
  panelBankHeight: number,
  flowConfig: PanelBankFlowSectionConfig
): BoxDimensions {
  const {gutterWidth} = flowConfig;
  const mobile = isMobile();
  const boxWidth = mobile
    ? panelBankWidth - 2 * gutterWidth
    : flowConfig.snapToColumns
    ? getColumnWidth(panelBankWidth, flowConfig)
    : flowConfig.boxWidth;
  // Subtract for footer
  const boxHeight = (panelBankHeight - 32) / flowConfig.rowsPerPage;
  return {boxWidth, boxHeight};
}

export function getColumnWidth(
  panelBankWidth: number,
  flowConfig: PanelBankFlowSectionConfig,
  columnCount?: number
): number {
  const {gutterWidth} = flowConfig;
  columnCount = columnCount || flowConfig.columnsPerPage;
  return Math.floor(
    (panelBankWidth - gutterWidth * (columnCount + 1)) / columnCount
  );
}

export function isMobile(): boolean {
  return window.innerWidth <= 852;
}
