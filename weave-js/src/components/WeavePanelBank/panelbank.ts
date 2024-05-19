import {
  DragData,
  DragRef,
} from '@wandb/weave/common/containers/DragDropContainer';
import * as _ from 'lodash';
import {ReactElement} from 'react';

export const PANEL_BANK_PADDING = 0;
export const DEFAULT_PANEL_SIZE = 64;

export interface LayoutCoords {
  x: number;
  y: number;
}

export interface LayoutDimensions {
  w: number;
  h: number;
}

export type LayoutParameters = LayoutCoords & LayoutDimensions;

export interface LayedOutItem {
  layout: LayoutParameters;
}

export type IdObj = {id: string};

export type LayedOutPanel = LayedOutItem & IdObj;

export interface PanelBankFlowSectionConfig {
  snapToColumns: boolean;
  columnsPerPage: number;
  rowsPerPage: number;
  gutterWidth: number;
  boxWidth: number;
  boxHeight: number;
}

export enum SectionPanelSorting {
  None,
  Manual,
  Alphabetical,
}

export interface PanelBankSectionConfig {
  id: string;
  name?: string;
  panels: LayedOutPanel[];
  isOpen?: boolean;
  flowConfig?: PanelBankFlowSectionConfig;
  type?: 'grid' | 'flow';
  sorted?: SectionPanelSorting;
}

// These are shared by PanelBankFlowSection and PanelBankGridSection
export interface PanelBankSectionComponentSharedProps {
  readOnly?: boolean;
  panelBankWidth: number;
  panelBankHeight: number;
  panelBankSectionConfigRef: PanelBankSectionConfig;
  activePanelRefs: ReadonlyArray<IdObj>;
  inactivePanelRefs: ReadonlyArray<IdObj>;
  addVisButton?: ReactElement;
  renderPanel(
    panelRef: IdObj,
    onContentHeightChange?: (h: number) => void
  ): JSX.Element;
  movePanelBetweenSections(
    panelRef: IdObj,
    fromSectionRef: PanelBankSectionConfig,
    toSectionRef: PanelBankSectionConfig,
    toIndex?: number,
    inactivePanelRefIDs?: Set<string>
  ): void;
}

export function isPanel(ref: DragRef | null): ref is LayedOutPanel {
  return ref != null && ref.type === 'panel';
}

export function isDraggingWithinSection(
  panelBankSectionConfigRef: PanelBankSectionConfig,
  dragData: DragData | null
) {
  return (
    dragData != null &&
    _.isEqual(dragData.fromSectionRef, panelBankSectionConfigRef)
  );
}
