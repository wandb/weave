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
import React, {useCallback, useMemo} from 'react';

import * as CGReact from '../../react';
import {
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';

type PanelSectionsConfig = {
  section: NodeOrVoidNode;
  panel: ChildPanelFullConfig;
};

export const PANEL_SECTIONS_DEFAULT_CONFIG: PanelSectionsConfig = {
  section: voidNode(),
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

type PanelSectionsProps = Panel2.PanelProps<
  typeof inputType,
  PanelSectionsConfig
>;

const usePanelSectionsCommon = (props: PanelSectionsProps) => {
  const config = props.config ?? PANEL_SECTIONS_DEFAULT_CONFIG;
  const itemType = useMemo(() => {
    return listObjectType(props.input.type);
  }, [props.input.type]);
  const updateConfig2 = useUpdateConfig2(props);
  const updateSectionExpr = useCallback(
    newExpr => {
      updateConfig2(oldConfig => {
        oldConfig = oldConfig ?? PANEL_SECTIONS_DEFAULT_CONFIG;
        return {
          ...oldConfig,
          section: newExpr,
        };
      });
    },

    [updateConfig2]
  );
  const updateChildPanelConfig = useCallback(
    newItemConfig =>
      updateConfig2(oldConfig => {
        oldConfig = oldConfig ?? PANEL_SECTIONS_DEFAULT_CONFIG;
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
        oldConfig = oldConfig ?? PANEL_SECTIONS_DEFAULT_CONFIG;
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
      updateSectionExpr,
      updateChildPanelConfig,
      updateChildPanelConfig2,
    }),
    [
      itemType,
      config,
      updateConfig2,
      updateSectionExpr,
      updateChildPanelConfig,
      updateChildPanelConfig2,
    ]
  );
};

export const PanelSectionsConfigComp: React.FC<PanelSectionsProps> = props => {
  const {
    config,
    updateChildPanelConfig,
    updateChildPanelConfig2,
    updateSectionExpr,
    itemType,
  } = usePanelSectionsCommon(props);
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
      <ConfigPanel.ConfigOption label={'section'}>
        <PanelContextProvider newVars={tabVars}>
          <ConfigPanel.ExpressionConfigField
            expr={config.section}
            setExpression={updateSectionExpr}
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

const Section: React.FC<{
  input: Node;
  config: PanelSectionsConfig;
}> = props => {
  const {input, config} = props;
  const sectionNameNode = useMemo(() => {
    return opGroupGroupKey({obj: input});
  }, [input]);
  const sectionNameQuery = CGReact.useNodeValue(sectionNameNode);
  const sectionName = sectionNameQuery.result ?? '';

  const sectionVars = useMemo(() => {
    return {
      item: input,
    };
  }, [input]);
  // TODO: Only render child when on screen

  return (
    <div style={{display: 'flex', flexDirection: 'column', height: 400}}>
      <div style={{whiteSpace: 'nowrap', textOverflow: 'ellipsis'}}>
        {sectionName}
      </div>
      <div style={{flexGrow: 1}}>
        <PanelContextProvider newVars={sectionVars}>
          <ChildPanel
            config={config.panel}
            updateConfig={() =>
              console.log('Section child updateConfig not implemented')
            }
            updateConfig2={() =>
              console.log('Section child updateConfig2 not implemented')
            }
          />
        </PanelContextProvider>
      </div>
    </div>
  );
};

export const PanelSections: React.FC<PanelSectionsProps> = props => {
  const {config, itemType} = usePanelSectionsCommon(props);

  const sectionsNode = useMemo(() => {
    return opGroupby({
      arr: props.input,
      groupByFn: constFunction(
        {row: itemType, index: 'number'},
        ({row, index}) =>
          config.section.nodeType === 'void' ? index : config.section
      ),
    });
  }, [config.section, itemType, props.input]) as Node<{
    type: 'list';
    objectType: 'any';
  }>;
  const eachSectionQuery = CGReact.useEach(sectionsNode);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
      }}>
      {eachSectionQuery.result.map((section, i) => (
        <Section key={i} input={section} config={config} />
      ))}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'Sections',
  ConfigComponent: PanelSectionsConfigComp,
  Component: PanelSections,
  inputType,
  hidden: true,
};
