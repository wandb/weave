import React from 'react';
import * as Panel2 from './panel';
import styled, {css} from 'styled-components';
import {ChildPanelConfig, ChildPanel} from './ChildPanel';
import {updateArrayIndex} from '../../../../src/util/update';

interface PanelGroupConfig {
  preferHorizontal?: boolean;
  items: ChildPanelConfig[];
}

const PANEL_GROUP_DEFAULT_CONFIG: PanelGroupConfig = {
  items: [],
};

const inputType = 'invalid';

type PanelGroupProps = Panel2.PanelProps<typeof inputType, PanelGroupConfig>;

export const Group = styled.div<{preferHorizontal?: boolean}>`
  display: flex;
  ${props =>
    props.preferHorizontal
      ? css`
          height: 100%;
          flex-direction: row;
        `
      : css`
          height: 100%;
          flex-direction: column;
        `}
`;

export const GroupItem = styled.div<{preferHorizontal?: boolean}>`
  ${props =>
    props.preferHorizontal
      ? css`
          flex-grow: 1;
        `
      : css`
          flex-grow: 1;
          margin-bottom: 48px;
        `}
`;

export const PanelGroup: React.FC<PanelGroupProps> = props => {
  const config = props.config ?? PANEL_GROUP_DEFAULT_CONFIG;
  const {updateConfig} = props;
  return (
    <Group preferHorizontal={config.preferHorizontal}>
      {config.items.map((item, i) => (
        <GroupItem key={i} preferHorizontal={config.preferHorizontal}>
          <ChildPanel
            key={i}
            config={item}
            updateConfig={newItemConfig =>
              updateConfig({
                ...config,
                items: updateArrayIndex(config.items, i, newItemConfig),
              })
            }
          />
        </GroupItem>
      ))}
    </Group>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'group',
  Component: PanelGroup,
  inputType,
};
