import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {useCallback} from 'react';
import styled, {css} from 'styled-components';

import {ChildPanel, ChildPanelConfig, ChildPanelConfigComp} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import {usePanelContext} from './PanelContext';

interface PanelLabeledItemConfig {
  label: string; // This should be allowed to be a constant or an expression
  height?: number;

  // Can either be an constant, or an expression, or a panel
  item?: ChildPanelConfig;
}

const PANEL_LABELED_ITEM_DEFAULT_CONFIG: PanelLabeledItemConfig = {
  label: '',
};

// Doesn't take an input
const inputType = 'invalid';

type PanelLabeledItemProps = Panel2.PanelProps<
  typeof inputType,
  PanelLabeledItemConfig
>;

export const LabeledItem = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
`;

export const LabeledItemLabel = styled.div`
  text-transform: uppercase;
  font-size: 14px;
  color: ${globals.textSecondary};
`;

// This overrides inner PanelString stylign to get rid of center.
// Probably not the most composable solution...
// TODO: fix
export const LabeledItemContent = styled.div<{height?: number}>`
  & div {
    // align-items: flex-start !important;
    // text-align: left !important;
  }
  flex-grow: 1;
  width: 100%;
  ${props =>
    props.height &&
    css`
      height: ${props.height}px;
    `}
`;

export const PanelLabeledItemConfigComponent: React.FC<
  PanelLabeledItemProps
> = props => {
  const config = props.config ?? PANEL_LABELED_ITEM_DEFAULT_CONFIG;
  const {updateConfig} = props;
  const updateChildPanelConfig = useCallback(
    newItemConfig =>
      updateConfig({
        ...config,
        item: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
      }),

    [config, updateConfig]
  );

  const {path, selectedPath, dashboardConfigOptions} = usePanelContext();
  const pathStr = path.join('.');
  const selectedPathStr = selectedPath?.join('.') ?? '';

  if (pathStr === selectedPathStr) {
    // We are selected, render our config
    return (
      <ConfigPanel.ConfigSection label={`Properties`}>
        {dashboardConfigOptions}
        <ConfigPanel.ConfigOption label="Label">
          <ConfigPanel.TextInputConfigField
            dataTest={`label`}
            value={config.label ?? ''}
            label={''}
            onChange={(event, {value}) => {
              updateConfig({
                label: value,
              });
            }}
          />
        </ConfigPanel.ConfigOption>
      </ConfigPanel.ConfigSection>
    );
  }

  // One of our descendants is selected.  Render children only
  return (
    <ChildPanelConfigComp
      pathEl="item"
      config={config.item}
      updateConfig={updateChildPanelConfig}
    />
  );
};

export const PanelLabeledItem: React.FC<PanelLabeledItemProps> = props => {
  const config = props.config ?? PANEL_LABELED_ITEM_DEFAULT_CONFIG;
  const {updateConfig} = props;
  const updateChildPanelConfig = useCallback(
    newItemConfig =>
      updateConfig({
        ...config,
        item: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
      }),

    [config, updateConfig]
  );
  return (
    <LabeledItem>
      <LabeledItemLabel>{config.label}</LabeledItemLabel>
      <LabeledItemContent height={config.height}>
        <ChildPanel
          pathEl="item"
          config={config.item}
          updateConfig={updateChildPanelConfig}
        />
      </LabeledItemContent>
    </LabeledItem>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'LabeledItem',
  ConfigComponent: PanelLabeledItemConfigComponent,
  Component: PanelLabeledItem,
  inputType,
};
