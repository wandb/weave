import React from 'react';
import {useState, useMemo} from 'react';
import * as Panel2 from './panel';
import * as globals from '@wandb/common/css/globals.styles';
import styled, {css} from 'styled-components';
import * as Types from '@wandb/cg/browser/model/types';
import {ChildPanelConfig, ChildPanel} from './ChildPanel';
import * as Graph from '@wandb/cg/browser/graph';
import * as CGReact from '@wandb/common/cgreact';
import * as ConfigPanel from './ConfigPanel';
import * as HL from '@wandb/cg/browser/hl';
import {usePanelContext} from './PanelContext';
import {updateArrayIndex} from '../../../../src/util/update';

interface PanelCardTabConfig {
  name: string;
  content: ChildPanelConfig;
}

type PanelCardContent = PanelCardTabConfig[];

interface PanelCardConfig {
  // This allows to name the input variable.
  // TODO: This should probably be more general, maybe a prop for all
  //     panels?
  inputVarName: string;

  title: Types.NodeOrVoidNode<'string'>;
  subtitle: string;
  content: PanelCardContent;
}

const PANEL_CARD_DEFAULT_CONFIG: PanelCardConfig = {
  inputVarName: 'card_input',
  title: Graph.voidNode(),
  subtitle: '',
  content: [
    {
      name: 'first tab',
      content: undefined,
    },
  ],
};

const inputType = 'any';

type PanelCardProps = Panel2.PanelProps<typeof inputType, PanelCardConfig>;

const Card = styled.div`
  display: flex;
  height: 100%;
`;

const CardHeader = styled.div`
  min-width: 200px;
  padding: 16px;
  border-right: 1px solid ${globals.border};
`;

const CardTitle = styled.div`
  font-size: 22px;
  font-weight: bold;
  margin-bottom: 16px;
`;

const CardSubtitle = styled.div`
  font-size: 16px;
  font-weight: normal;
`;

const CardTabs = styled.div``;

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

const CardContent = styled.div`
  overflow: auto;
  flex-grow: 1;
  padding: 16px;
`;

export const PanelCardConfigEditor: React.FC<PanelCardProps> = props => {
  const config = props.config ?? PANEL_CARD_DEFAULT_CONFIG;
  const {updateConfig} = props;
  const {frame: contextFrame} = usePanelContext();
  const frame = useMemo(
    () => ({
      ...contextFrame,
      [config.inputVarName]: props.input,
    }),
    [props.input, config.inputVarName, contextFrame]
  );
  return (
    <ConfigPanel.ConfigOption label="Title">
      <ConfigPanel.ExpressionConfigField
        frame={frame}
        node={config.title}
        updateNode={newNode => updateConfig({...config, title: newNode as any})}
      />
    </ConfigPanel.ConfigOption>
  );
};

export const PanelCard: React.FC<PanelCardProps> = props => {
  const config = props.config ?? PANEL_CARD_DEFAULT_CONFIG;
  const {updateConfig} = props;
  const {frame: contextFrame} = usePanelContext();
  const frame = useMemo(
    () => ({
      ...contextFrame,
      [config.inputVarName]: props.input,
    }),
    [props.input, config.inputVarName, contextFrame]
  );
  const firstTab = config.content[0];
  const [currentTabName, setCurrentTabName] = useState(firstTab.name);
  const currentTabIndex = config.content.findIndex(
    tab => tab.name === currentTabName
  );
  const {node: titleNode} = HL.dereferenceVariables(config.title, frame);
  const title = CGReact.useNodeValue(titleNode);
  if (currentTabIndex === -1) {
    throw new Error('invalid PanelCard configuration');
  }
  const currentTab = config.content[currentTabIndex];
  return (
    <Card>
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
        <ChildPanel
          config={currentTab.content}
          updateConfig={newItemConfig =>
            updateConfig({
              ...config,
              content: updateArrayIndex(config.content, currentTabIndex, {
                ...config.content[currentTabIndex],
                content: newItemConfig,
              }),
            })
          }
        />
      </CardContent>
    </Card>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'card',
  Component: PanelCard,
  ConfigComponent: PanelCardConfigEditor,
  inputType,
};
