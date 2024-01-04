import * as globals from '@wandb/weave/common/css/globals.styles';
import {NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import {produce} from 'immer';
import React, {useState} from 'react';
import styled, {css} from 'styled-components';

import * as CGReact from '../../react';
import {ChildPanel, ChildPanelConfig} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';

interface PanelCardTabConfig {
  name: string;
  content: ChildPanelConfig;
}

type PanelCardContent = PanelCardTabConfig[];

interface PanelCardConfig {
  title: NodeOrVoidNode<'string'>;
  subtitle: string;
  content: PanelCardContent;
}

const PANEL_CARD_DEFAULT_CONFIG: PanelCardConfig = {
  title: voidNode(),
  subtitle: '',
  content: [
    {
      name: 'first tab',
      content: undefined,
    },
  ],
};

const inputType = 'invalid';

type PanelCardProps = Panel2.PanelProps<typeof inputType, PanelCardConfig>;

const Card = styled.div`
  display: flex;
  height: 100%;
`;
Card.displayName = 'S.Card';

const CardHeader = styled.div`
  min-width: 200px;
  padding: 16px;
  border-right: 1px solid ${globals.border};
`;
CardHeader.displayName = 'S.CardHeader';

const CardTitle = styled.div`
  font-size: 22px;
  font-weight: bold;
  margin-bottom: 16px;
`;
CardTitle.displayName = 'S.CardTitle';

const CardSubtitle = styled.div`
  font-size: 16px;
  font-weight: normal;
`;
CardSubtitle.displayName = 'S.CardSubtitle';

const CardTabs = styled.div``;
CardTabs.displayName = 'S.CardTabs';

const CardTab = styled.div<{active?: boolean}>`
  cursor: pointer;
  margin-bottom: 4px;
  text-align: left;
  ${props =>
    props.active &&
    css`
      color: ${globals.primary};
      border-right: 2px solid ${globals.primary};
      margin-right: -16px;
    `}
`;
CardTab.displayName = 'S.CardTab';

const CardContent = styled.div`
  overflow: auto;
  flex-grow: 1;
  padding: 16px;
`;
CardContent.displayName = 'S.CardContent';

export const PanelCardConfigEditor: React.FC<PanelCardProps> = props => {
  const config = props.config ?? PANEL_CARD_DEFAULT_CONFIG;
  const {updateConfig} = props;
  return (
    <ConfigPanel.ConfigOption label="Title">
      <ConfigPanel.ExpressionConfigField
        expr={config.title}
        setExpression={newNode =>
          updateConfig({...config, title: newNode as any})
        }
      />
    </ConfigPanel.ConfigOption>
  );
};

export const PanelCard: React.FC<PanelCardProps> = props => {
  const config = props.config ?? PANEL_CARD_DEFAULT_CONFIG;
  const {updateConfig} = props;
  const firstTab = config.content[0];
  const [currentTabName, setCurrentTabName] = useState(firstTab.name);
  const currentTabIndex = config.content.findIndex(
    tab => tab.name === currentTabName
  );
  const title = CGReact.useNodeValue(config.title);
  if (currentTabIndex === -1) {
    throw new Error('invalid PanelCard configuration');
  }
  const currentTab = config.content[currentTabIndex];
  return (
    <Card data-test-weave-id="Card">
      <CardHeader>
        <CardTitle>
          {title.result}
          <CardSubtitle>{config.subtitle}</CardSubtitle>
        </CardTitle>
        <CardTabs>
          {config.content.map(tab => (
            <CardTab
              key={tab.name}
              active={currentTabName === tab.name}
              onClick={() => setCurrentTabName(tab.name)}>
              {tab.name}
            </CardTab>
          ))}
        </CardTabs>
      </CardHeader>
      <CardContent>
        {/* Zoom into expression */}
        {/* <div
          style={{cursor: 'pointer'}}
          onClick={() => props.updateInput(currentTab.content)}>
          🔍
        </div> */}
        <ChildPanel
          passthroughUpdate={true}
          config={currentTab.content}
          updateConfig={newItemConfig =>
            updateConfig(
              produce(config, draft => {
                draft.content[currentTabIndex].content = newItemConfig;
              })
            )
          }
          updateInput={props.updateInput as any}
        />
      </CardContent>
    </Card>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: 'Card',
  Component: PanelCard,
  ConfigComponent: PanelCardConfigEditor,
  inputType,
};
