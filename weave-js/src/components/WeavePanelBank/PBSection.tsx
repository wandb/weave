import './PanelBank.less';
import './PanelBankEditablePanel.less';

import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {
  DragDropProvider,
  DragHandle,
} from '@wandb/weave/common/containers/DragDropContainer';
import {produce} from 'immer';
import * as _ from 'lodash';
import React, {useRef, useState} from 'react';
import Measure from 'react-measure';

import {IdObj, PANEL_BANK_PADDING, PanelBankSectionConfig} from './panelbank';
import {PanelBankFlowSection} from './PanelBankFlowSection';
import {getNewGridItemLayout} from './panelbankGrid';
import {PanelBankGridSection} from './PanelBankGridSection';
import styled, {css} from 'styled-components';
import {
  BORDER_COLOR_FOCUSED,
  GRAY_25,
  GRAY_350,
  GRAY_400,
  GRAY_500,
  PANEL_HOVERED_SHADOW,
  SCROLLBAR_STYLES,
  WHITE,
} from '../../common/css/globals.styles';
import {
  IconAddNew as IconAddNewUnstyled,
  IconPencilEdit,
} from '../Panel2/Icons';
import {inJupyterCell} from '../PagePanelComponents/util';
import {useScrollbarVisibility} from '../../core/util/scrollbar';
import {Tooltip} from '../Tooltip';
import {IconButton} from '../IconButton';
import {WBButton} from '../../common/components/elements/WBButtonNew';
import {
  useGetPanelIsHoveredByGroupPath,
  useGetPanelIsHoveredInOutlineByGroupPath,
  useSelectedPath,
  useSetInspectingPanel,
  useSetPanelIsHovered,
} from '../Panel2/PanelInteractContext';

interface PBSectionProps {
  mode: 'grid' | 'flow';
  config: PanelBankSectionConfig;
  groupPath?: string[];
  enableAddPanel?: boolean;
  updateConfig2: (
    fn: (config: PanelBankSectionConfig) => PanelBankSectionConfig
  ) => void;
  renderPanel: (panelRef: IdObj) => React.ReactNode;
  handleAddPanel?: () => void;
}

export const PBSection: React.FC<PBSectionProps> = props => {
  const {config, groupPath, enableAddPanel, updateConfig2, handleAddPanel} =
    props;
  const selectedPath = useSelectedPath();
  const setInspectingPanel = useSetInspectingPanel();
  const getPanelIsHovered = useGetPanelIsHoveredByGroupPath(groupPath ?? []);
  const getPanelIsHoveredInOutline = useGetPanelIsHoveredInOutlineByGroupPath(
    groupPath ?? []
  );
  const setPanelIsHovered = useSetPanelIsHovered();
  const [panelBankWidth, setPanelBankWidth] = useState(0);
  const [panelBankHeight, setPanelBankHeight] = useState(0);
  const PanelBankSectionComponent =
    props.mode === 'grid' ? PanelBankGridSection : PanelBankFlowSection;
  const inJupyter = inJupyterCell();
  const {
    visible: sectionsScrollbarVisible,
    onScroll: onSectionsScroll,
    onMouseMove: onSectionsMouseMove,
  } = useScrollbarVisibility();
  const actionBarRef = useRef<HTMLDivElement | null>(null);
  const addPanelBarRef = useRef<HTMLDivElement | null>(null);
  return (
    <DragDropProvider>
      <div className="panel-bank" style={{height: '100%'}}>
        <Measure
          bounds
          onResize={contentRect => {
            setPanelBankWidth(
              contentRect.bounds
                ? contentRect.bounds.width - PANEL_BANK_PADDING * 2
                : 0
            );
            setPanelBankHeight(
              contentRect.bounds
                ? contentRect.bounds.height -
                    (actionBarRef.current?.offsetHeight ?? 0) -
                    (addPanelBarRef.current?.offsetHeight ?? 0)
                : 0
            );
          }}>
          {({measureRef}) => (
            <Sections
              className="panel-bank__sections"
              ref={measureRef}
              scrollbarVisible={sectionsScrollbarVisible}
              onScroll={onSectionsScroll}
              onMouseMove={onSectionsMouseMove}>
              <div className="panel-bank__section">
                {!inJupyter && groupPath != null && (
                  <ActionBar ref={actionBarRef}>
                    <Tooltip
                      position="bottom right"
                      trigger={
                        <IconButton
                          onClick={() => setInspectingPanel(groupPath)}>
                          <IconPencilEdit />
                        </IconButton>
                      }>
                      Open panel editor
                    </Tooltip>
                    {enableAddPanel && (
                      <WBButton onClick={handleAddPanel}>
                        <IconAddNew $marginRight={6} />
                        New panel
                      </WBButton>
                    )}
                  </ActionBar>
                )}
                <PanelBankSectionComponent
                  panelBankWidth={panelBankWidth}
                  panelBankHeight={panelBankHeight}
                  panelBankSectionConfigRef={config}
                  updateConfig={updateConfig2}
                  activePanelRefs={config.panels}
                  inactivePanelRefs={[]}
                  renderPanel={panelRef => {
                    const path =
                      groupPath != null ? [...groupPath, panelRef.id] : null;
                    const isSelected =
                      path != null && _.isEqual(path, selectedPath);
                    const isHovered =
                      groupPath != null && getPanelIsHovered(panelRef.id);
                    const isHoveredInOutline =
                      groupPath != null &&
                      getPanelIsHoveredInOutline(panelRef.id);
                    const isFocused = isSelected || isHoveredInOutline;

                    return (
                      <EditablePanel
                        isHovered={isHovered}
                        isFocused={isFocused}
                        className="editable-panel"
                        onMouseEnter={
                          path != null
                            ? () => {
                                setPanelIsHovered(path, true);
                              }
                            : undefined
                        }
                        onMouseLeave={
                          path != null
                            ? () => {
                                setPanelIsHovered(path, false);
                              }
                            : undefined
                        }>
                        {props.mode === 'grid' && (
                          <DragHandle
                            key={`draghandle-${panelRef.id}`}
                            className="draggable-handle"
                            partRef={panelRef}>
                            <LegacyWBIcon title="" name="handle" />
                          </DragHandle>
                        )}
                        {props.renderPanel(panelRef)}
                      </EditablePanel>
                    );
                  }}
                  movePanelBetweenSections={() => {
                    console.log('MOVE BETWEEN SECTIONS');
                  }}
                />
                {handleAddPanel != null && !inJupyter && (
                  <AddPanelBarContainer ref={addPanelBarRef}>
                    <AddPanelBar onClick={handleAddPanel}>
                      <IconAddNew />
                      New panel
                    </AddPanelBar>
                  </AddPanelBarContainer>
                )}
              </div>
            </Sections>
          )}
        </Measure>
      </div>
    </DragDropProvider>
  );
};

export const getSectionConfig = (
  panelIds: string[],
  currentConfig: PanelBankSectionConfig | undefined
): PanelBankSectionConfig => {
  const gridConfig: PanelBankSectionConfig = currentConfig ?? {
    id: 'grid0',
    name: 'Section 0',
    panels: [],
    isOpen: true,
    flowConfig: {
      snapToColumns: true,
      columnsPerPage: 2,
      rowsPerPage: 1,
      gutterWidth: 0,
      boxWidth: 64,
      boxHeight: 64,
    },
    type: 'grid' as const,
    sorted: 0,
  };
  return produce(gridConfig, draft => {
    _.forEach(panelIds, name => {
      // Very bad! We use the variable name as the ID!
      if (gridConfig.panels.findIndex(p => p.id === name) !== -1) {
        return;
      }
      draft.panels.push({
        id: name,
        layout: getNewGridItemLayout(
          draft.panels.map(p => p.layout),
          false
        ),
      });
    });
  });
};

const Sections = styled.div`
  ${SCROLLBAR_STYLES}
`;

const ActionBar = styled.div`
  height: 48px;
  padding: 0 32px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
`;

const AddPanelBar = styled.div`
  height: 48px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  border-radius: 6px;
  background-color: ${GRAY_25};
  font-weight: 600;
  color: ${GRAY_500};
`;

const AddPanelBarContainer = styled.div`
  padding: 8px 32px 16px;

  transition: opacity 0.3s;
  &:not(:hover) {
    opacity: 0;
  }
`;

const IconAddNew = styled(IconAddNewUnstyled)<{$marginRight?: number}>`
  width: 18px;
  height: 18px;
  margin-right: ${p => p.$marginRight ?? 8}px;
`;

const EditablePanel = styled.div<{isFocused: boolean; isHovered: boolean}>`
  &&&&& {
    background-color: ${WHITE};
    width: 100%;
    height: 100%;

    padding: 8px;
    border: 1px solid ${GRAY_350};
    ${p =>
      p.isHovered &&
      css`
        border-color: ${GRAY_400};
        box-shadow: ${PANEL_HOVERED_SHADOW};
      `}
    ${p =>
      p.isFocused &&
      css`
        padding: 7px;
        border-width: 2px;
        border-color: ${BORDER_COLOR_FOCUSED};
      `}
  }
`;
