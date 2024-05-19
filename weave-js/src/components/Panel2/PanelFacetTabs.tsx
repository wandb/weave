// TODO:
//   - make tabs virtualized so we don't have to render all of them
//   - get rid of scrollbar
//   - make active index part of config and edited with mutations so
//     it can be externally controlled by other weave components.

import {
  constFunction,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opGroupby,
  opGroupGroupKey,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo, useState} from 'react';

import * as CGReact from '../../react';
import {
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import {Tabs} from './LayoutTabs';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';

type PanelFacetTabsConfig = {
  tab: NodeOrVoidNode;
  panel: ChildPanelFullConfig;
};

export const PANEL_FACET_TABS_DEFAULT_CONFIG: PanelFacetTabsConfig = {
  tab: voidNode(),
  panel: {
    id: 'Auto',
    input_node: varNode({type: 'list', objectType: 'any'}, 'item'),
    config: undefined,
    vars: {},
  },
};

const inputType = {
  type: 'list' as const,
  objectType: 'any' as const,
};

type PanelFacetTabsProps = Panel2.PanelProps<
  typeof inputType,
  PanelFacetTabsConfig
>;

const usePanelFacetTabsCommon = (props: PanelFacetTabsProps) => {
  const config = props.config ?? PANEL_FACET_TABS_DEFAULT_CONFIG;
  const itemType = useMemo(() => {
    console.log('LIST OBJECT TYPE', props.input.type);
    return listObjectType(props.input.type);
  }, [props.input.type]);
  const updateConfig2 = useUpdateConfig2(props);
  const updateTabExpr = useCallback(
    newExpr =>
      updateConfig2(oldConfig => {
        oldConfig = oldConfig ?? PANEL_FACET_TABS_DEFAULT_CONFIG;
        return {
          ...oldConfig,
          tab: newExpr,
        };
      }),

    [updateConfig2]
  );
  const updateChildPanelConfig = useCallback(
    newItemConfig =>
      updateConfig2(oldConfig => {
        oldConfig = oldConfig ?? PANEL_FACET_TABS_DEFAULT_CONFIG;
        return {
          ...oldConfig,
          panel: newItemConfig,
        };
      }),

    [updateConfig2]
  );
  const updateChildPanelConfig2 = useCallback(
    (change: (oldConfig: any) => any) => {
      updateConfig2(oldConfig => {
        oldConfig = oldConfig ?? PANEL_FACET_TABS_DEFAULT_CONFIG;
        const newItemConfig = change(oldConfig.panel);
        return {
          ...oldConfig,
          panel: newItemConfig,
        };
      });
    },
    [updateConfig2]
  );
  return useMemo(
    () => ({
      itemType,
      config,
      updateConfig2,
      updateTabExpr,
      updateChildPanelConfig,
      updateChildPanelConfig2,
    }),
    [
      itemType,
      config,
      updateConfig2,
      updateTabExpr,
      updateChildPanelConfig,
      updateChildPanelConfig2,
    ]
  );
};

export const PanelFacetTabsConfigComp: React.FC<
  PanelFacetTabsProps
> = props => {
  const {
    config,
    updateChildPanelConfig,
    updateChildPanelConfig2,
    updateTabExpr,
    itemType,
  } = usePanelFacetTabsCommon(props);
  const {dashboardConfigOptions} = usePanelContext();
  const tabVars = useMemo(() => {
    return {
      row: varNode(itemType, 'row'),
    };
  }, [itemType]);
  const panelVars = useMemo(() => {
    return {
      // TODO: need group key as part of type
      item: varNode(props.input.type, 'item'),
    };
  }, [props.input.type]);
  return (
    <ConfigPanel.ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <ConfigPanel.ConfigOption label={'tab'}>
        <PanelContextProvider newVars={tabVars}>
          <ConfigPanel.ExpressionConfigField
            expr={config.tab}
            setExpression={updateTabExpr}
          />
        </PanelContextProvider>
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ChildConfigContainer>
        <PanelContextProvider newVars={panelVars}>
          <ChildPanelConfigComp
            pathEl="panel"
            config={config.panel}
            updateConfig={updateChildPanelConfig}
            updateConfig2={updateChildPanelConfig2}
          />
        </PanelContextProvider>
      </ConfigPanel.ChildConfigContainer>
    </ConfigPanel.ConfigSection>
  );
};

export const PanelFacetTabs: React.FC<PanelFacetTabsProps> = props => {
  const {config, itemType} = usePanelFacetTabsCommon(props);

  const tabsNode = useMemo(() => {
    return opGroupby({
      arr: props.input,
      groupByFn: constFunction(
        {row: itemType, index: 'number'},
        ({row, index}) => (config.tab.nodeType === 'void' ? index : config.tab)
      ),
    });
  }, [config.tab, itemType, props.input]) as Node<{
    type: 'list';
    objectType: 'any';
  }>;

  const eachTabQuery = CGReact.useEach(tabsNode);
  const tabNamesNode = useMemo(() => {
    return opGroupGroupKey({obj: tabsNode});
  }, [tabsNode]);

  const [activeIndex, setActiveIndex] = useState(0);
  const newVars = useMemo(() => {
    return {item: eachTabQuery.result[activeIndex] ?? voidNode()};
  }, [activeIndex, eachTabQuery.result]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <div>
        <Tabs
          input={tabNamesNode}
          activeIndex={activeIndex}
          setActiveIndex={setActiveIndex}
        />
      </div>
      <div style={{flexGrow: 1}}>
        <PanelContextProvider newVars={newVars}>
          <ChildPanel
            config={config.panel}
            updateConfig={() =>
              console.log('Tab child updateConfig not implemented')
            }
            updateConfig2={() =>
              console.log('Tab child updateConfig2 not implemented')
            }
          />
        </PanelContextProvider>
      </div>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'FacetTabs',
  ConfigComponent: PanelFacetTabsConfigComp,
  Component: PanelFacetTabs,
  inputType,
  hidden: true,
};
