import './PanelBank.less';
import './PanelBankEditablePanel.less';

import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {
  DragDropProvider,
  DragHandle,
} from '@wandb/weave/common/containers/DragDropContainer';
import {produce} from 'immer';
import * as _ from 'lodash';
import React, {useState} from 'react';
import Measure from 'react-measure';
import styled, {css} from 'styled-components';

import {
  BORDER_COLOR_FOCUSED,
  GRAY_350,
  GRAY_400,
  PANEL_HOVERED_SHADOW,
  SCROLLBAR_STYLES,
  WHITE,
} from '../../common/css/globals.styles';
import {useScrollbarVisibility} from '../../core/util/scrollbar';
import {IconAddNew as IconAddNewUnstyled} from '../Panel2/Icons';
import {
  useGetPanelIsHoveredByGroupPath,
  useGetPanelIsHoveredInOutlineByGroupPath,
  useSelectedPath,
  useSetPanelIsHovered,
} from '../Panel2/PanelInteractContext';
import {IdObj, PANEL_BANK_PADDING, PanelBankSectionConfig} from './panelbank';
import {PanelBankFlowSection} from './PanelBankFlowSection';
import {getNewGridItemLayout} from './panelbankGrid';
import {PanelBankGridSection} from './PanelBankGridSection';

interface PBSectionProps {
  mode: 'grid' | 'flow';
  config: PanelBankSectionConfig;
  groupPath?: string[];
  updateConfig2: (
    fn: (config: PanelBankSectionConfig) => PanelBankSectionConfig
  ) => void;
  renderPanel: (panelRef: IdObj) => React.ReactNode;
}

export const PBSection: React.FC<PBSectionProps> = props => {
  const {config, groupPath, updateConfig2} = props;
  const selectedPath = useSelectedPath();
  const getPanelIsHovered = useGetPanelIsHoveredByGroupPath(groupPath ?? []);
  const getPanelIsHoveredInOutline = useGetPanelIsHoveredInOutlineByGroupPath(
    groupPath ?? []
  );
  const setPanelIsHovered = useSetPanelIsHovered();
  const [panelBankWidth, setPanelBankWidth] = useState(0);
  const [panelBankHeight, setPanelBankHeight] = useState(0);
  const PanelBankSectionComponent =
    props.mode === 'grid' ? PanelBankGridSection : PanelBankFlowSection;
  const {
    visible: sectionsScrollbarVisible,
    onScroll: onSectionsScroll,
    onMouseMove: onSectionsMouseMove,
  } = useScrollbarVisibility();
  // On add panel, scroll to the new panel

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
                ? contentRect.bounds.height - PANEL_BANK_PADDING * 2
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
        layout: getNewGridItemLayout(draft.panels.map(p => p.layout)),
      });
    });
  });
};

const Sections = styled.div`
  ${SCROLLBAR_STYLES}
`;
Sections.displayName = 'S.Sections';

const ActionBar = styled.div`
  height: 48px;
  padding: 0 32px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
`;
ActionBar.displayName = 'S.ActionBar';

const IconAddNew = styled(IconAddNewUnstyled)<{$marginRight?: number}>`
  width: 18px;
  height: 18px;
  margin-right: ${p => p.$marginRight ?? 8}px;
`;
IconAddNew.displayName = 'S.IconAddNew';

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
EditablePanel.displayName = 'S.EditablePanel';
