import {constNumber, opCount, opIndex, varNode} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';

import * as CGReact from '../../react';
import {PanelBankSectionConfig} from '../WeavePanelBank/panelbank';
import {getSectionConfig, PBSection} from '../WeavePanelBank/PBSection';
import {
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  initPanel,
  useChildPanelProps,
} from './ChildPanel';
import {ChildConfigContainer, ConfigSection} from './ConfigPanel';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';

type PanelTable2Config = {
  columns: ChildPanelFullConfig[];
  pbConfig?: PanelBankSectionConfig;
};

export const PANEL_TABLE2_DEFAULT_CONFIG: PanelTable2Config = {
  columns: [],
};

const inputType = {
  type: 'list' as const,
  objectType: 'any' as const,
};

type PanelTable2Props = Panel2.PanelProps<typeof inputType, PanelTable2Config>;

const usePbLayoutConfig = (
  panelKeys: string[],
  config: PanelTable2Config | undefined,
  updateConfig2: (
    change: (oldConfig: PanelTable2Config) => Partial<PanelTable2Config>
  ) => void
) => {
  const pbLayoutConfig = useMemo(() => {
    return getSectionConfig(panelKeys, config?.pbConfig);
  }, [config, panelKeys]);
  // Hmm... does not just depend on config, depends on rendered panelKeys.
  // TODO: don't like
  const updatePbLayoutConfig2 = useCallback(
    (change: (oldConfig: PanelBankSectionConfig) => PanelBankSectionConfig) => {
      return updateConfig2(currentConfig => {
        const gridConfig = getSectionConfig(panelKeys, currentConfig.pbConfig);
        const newLayoutConfig = change(gridConfig);
        return {...currentConfig, pbConfig: newLayoutConfig};
      });
    },
    [panelKeys, updateConfig2]
  );
  return {pbLayoutConfig, updatePbLayoutConfig2};
};

const usePanelTable2Common = (props: PanelTable2Props) => {
  // Augh, we have to do this because PanelPanel doesn't properly
  // hydrate the config.
  // essentially it needs to walk the PanelTree, finding and initializing
  // any uninitialized panels.
  // TODO: Fix PanelPanel
  props = {
    ...props,
    config: props.config == null ? PANEL_TABLE2_DEFAULT_CONFIG : props.config,
  };
  const childPanelPanelProps = useChildPanelProps(props, 'panel');
  return useMemo(
    () => ({
      childPanelPanelProps,
    }),
    [childPanelPanelProps]
  );
};

export const PanelTable2ConfigComp: React.FC<PanelTable2Props> = props => {
  const {childPanelPanelProps} = usePanelTable2Common(props);
  const {dashboardConfigOptions} = usePanelContext();
  const itemNode = opIndex({
    arr: props.input,
    index: varNode('number', 'itemIndex'),
  });

  const newVars = useMemo(() => {
    return {
      item: itemNode,
    };
  }, [itemNode]);

  return (
    <ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <ChildConfigContainer>
        <PanelContextProvider newVars={newVars}>
          <ChildPanelConfigComp {...childPanelPanelProps} />
        </PanelContextProvider>
      </ChildConfigContainer>
    </ConfigSection>
  );
};

const PanelTable2Item: React.FC<
  PanelTable2Props & {itemIndex: number}
> = props => {
  const {childPanelPanelProps} = usePanelTable2Common(props);
  const {itemIndex} = props;
  const itemNode = opIndex({
    arr: props.input,
    index: constNumber(itemIndex),
  });

  const newVars = useMemo(() => {
    return {
      item: itemNode,
    };
  }, [itemNode]);

  return (
    <PanelContextProvider newVars={newVars}>
      <ChildPanel
        {...childPanelPanelProps}
        passthroughUpdate={true}
        updateInput={props.updateInput}
      />
    </PanelContextProvider>
  );
};

export const PanelTable2: React.FC<PanelTable2Props> = props => {
  const {config} = props;
  const updateConfig2 = useUpdateConfig2(props);

  const countNode = useMemo(() => {
    return opCount({arr: props.input});
  }, [props.input]);
  const countQuery = CGReact.useNodeValue(countNode);
  const count = countQuery.result ?? 10;
  const panels = useMemo(() => {
    return [...Array(count).keys()].map(i => i.toString());
  }, [count]);

  const {pbLayoutConfig, updatePbLayoutConfig2} = usePbLayoutConfig(
    panels,
    config,
    updateConfig2
  );

  return (
    <PBSection
      mode="flow"
      config={pbLayoutConfig}
      updateConfig2={updatePbLayoutConfig2}
      renderPanel={panel => (
        <PanelTable2Item {...props} itemIndex={parseInt(panel.id, 10)} />
      )}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'Each',
  initialize: async (weave, inputNode, stack) => {
    const itemNode = opIndex({
      arr: inputNode as any,
      index: varNode('number', 'itemIndex'),
    });
    const {id: childPanelId, config: childPanelConfig} = await initPanel(
      weave,
      itemNode,
      undefined,
      undefined,
      stack
    );
    console.log('childPanelConfig', childPanelId, childPanelConfig);
    return {
      pbConfig: getSectionConfig([], undefined),
      panel: {
        id: childPanelId,
        input_node: varNode('any', 'item'),
        config: childPanelConfig,
        vars: {},
      },
    };
  },
  ConfigComponent: PanelTable2ConfigComp,
  Component: PanelTable2,
  inputType,
  hidden: true,
};
