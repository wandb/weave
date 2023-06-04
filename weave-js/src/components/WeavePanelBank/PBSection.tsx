import './PanelBank.less';
import './PanelBankEditablePanel.less';

import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {
  DragDropProvider,
  DragHandle,
} from '@wandb/weave/common/containers/DragDropContainer';
import produce from 'immer';
import * as _ from 'lodash';
import React, {useState} from 'react';
import Measure from 'react-measure';

import {IdObj, PANEL_BANK_PADDING, PanelBankSectionConfig} from './panelbank';
import {PanelBankFlowSection} from './PanelBankFlowSection';
import {getNewGridItemLayout} from './panelbankGrid';
import {PanelBankGridSection} from './PanelBankGridSection';
import styled from 'styled-components';
import {GRAY_25, GRAY_500} from '../../common/css/globals.styles';
import {IconAddNew as IconAddNewUnstyled} from '../Panel2/Icons';

interface PBSectionProps {
  mode: 'grid' | 'flow';
  config: PanelBankSectionConfig;
  updateConfig2: (
    fn: (config: PanelBankSectionConfig) => PanelBankSectionConfig
  ) => void;
  renderPanel: (panelRef: IdObj) => React.ReactNode;
  handleAddPanel?: () => void;
}

export const PBSection: React.FC<PBSectionProps> = props => {
  const {config, updateConfig2, handleAddPanel} = props;
  const [panelBankWidth, setPanelBankWidth] = useState(0);
  const [panelBankHeight, setPanelBankHeight] = useState(0);
  const PanelBankSectionComponent =
    props.mode === 'grid' ? PanelBankGridSection : PanelBankFlowSection;
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
              contentRect.bounds ? contentRect.bounds.height : 0
            );
          }}>
          {({measureRef}) => (
            <div className="panel-bank__sections" ref={measureRef}>
              <div className="panel-bank__section">
                <PanelBankSectionComponent
                  panelBankWidth={panelBankWidth}
                  panelBankHeight={panelBankHeight}
                  panelBankSectionConfigRef={config}
                  updateConfig={updateConfig2}
                  activePanelRefs={config.panels}
                  inactivePanelRefs={[]}
                  renderPanel={panelRef => (
                    <div
                      style={{
                        backgroundColor: '#fff',
                        width: '100%',
                        height: '100%',
                      }}
                      className="editable-panel">
                      {props.mode === 'grid' && (
                        <DragHandle
                          key={`draghandle-${panelRef.id}`}
                          className="draggable-handle"
                          partRef={panelRef}>
                          <LegacyWBIcon title="" name="handle" />
                        </DragHandle>
                      )}
                      {props.renderPanel(panelRef)}
                    </div>
                  )}
                  movePanelBetweenSections={() => {
                    console.log('MOVE BETWEEN SECTIONS');
                  }}
                />
                {handleAddPanel != null && (
                  <AddPanelBarContainer>
                    <AddPanelBar onClick={handleAddPanel}>
                      <IconAddNew />
                      New panel
                    </AddPanelBar>
                  </AddPanelBarContainer>
                )}
              </div>
            </div>
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
          gridConfig.panels.map(p => p.layout),
          false
        ),
      });
    });
  });
};

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

const IconAddNew = styled(IconAddNewUnstyled)`
  width: 18px;
  height: 18px;
  margin-right: 8px;
`;
