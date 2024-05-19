import {
  constString,
  isListLike,
  isTypedDictLike,
  listObjectType,
  NodeOrVoidNode,
  opPick,
  Type,
  typedDictPropertyTypes,
  varNode,
  voidNode,
} from '@wandb/weave/core';
import {produce} from 'immer';
import React, {useCallback, useMemo, useState} from 'react';
import styled from 'styled-components';

import {WeaveExpression} from '../../panel/WeaveExpression';
import {PanelBankSectionConfig} from '../WeavePanelBank/panelbank';
import {getSectionConfig, PBSection} from '../WeavePanelBank/PBSection';
import {
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  VariableView,
} from './ChildPanel';
import {ChildConfigContainer, ConfigSection} from './ConfigPanel';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';

interface PanelEachColumnConfig {
  layoutMode: 'absolute' | 'flow';
  pbLayoutConfig?: PanelBankSectionConfig;
  render: ChildPanelConfig;
}

export const PANEL_EACH_COLUMN_DEFAULT_CONFIG: PanelEachColumnConfig = {
  layoutMode: 'flow',
  render: varNode('any', 'column'),
};

const inputType = {
  type: 'list' as const,
  objectType: {type: 'typedDict' as const, propertyTypes: {}},
};

type PanelEachColumnProps = Panel2.PanelProps<
  typeof inputType,
  PanelEachColumnConfig
>;

export const EachColumn = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  // align-items: flex-start;
  flex-wrap: wrap;
  align-content: flex-start;
`;

export const EachColumnItem = styled.div<{
  position?: 'absolute' | 'static';
  top?: number;
  left?: number;
  width?: number;
  height?: number;
}>`
  // flex-grow: 1;
  position: ${props => props.position ?? 'static'};
  top: ${props => (props.top != null ? props.top + 'px' : undefined)};
  left: ${props => (props.left != null ? props.left + 'px' : undefined)};
  width: ${props => (props.width != null ? props.width + 'px' : '50px')};
  height: ${props => (props.height != null ? props.height + 'px' : '50px')};
`;

const usePbLayoutConfig = (
  panelKeys: string[],
  config: PanelEachColumnConfig | undefined,
  updateConfig2: (
    change: (oldConfig: PanelEachColumnConfig) => Partial<PanelEachColumnConfig>
  ) => void
) => {
  const pbLayoutConfig = useMemo(() => {
    const conf = config ?? PANEL_EACH_COLUMN_DEFAULT_CONFIG;
    return getSectionConfig(panelKeys, conf.pbLayoutConfig);
  }, [config, panelKeys]);
  // Hmm... does not just depend on config, depends on rendered panelKeys.
  // TODO: don't like
  const updatePbLayoutConfig2 = useCallback(
    (change: (oldConfig: PanelBankSectionConfig) => PanelBankSectionConfig) => {
      return updateConfig2(currentConfig => {
        currentConfig = currentConfig ?? PANEL_EACH_COLUMN_DEFAULT_CONFIG;
        const gridConfig = getSectionConfig(
          panelKeys,
          currentConfig.pbLayoutConfig
        );
        const newLayoutConfig = change(gridConfig);
        return produce(currentConfig, draft => {
          draft.pbLayoutConfig = newLayoutConfig;
        });
      });
    },
    [panelKeys, updateConfig2]
  );
  return {pbLayoutConfig, updatePbLayoutConfig2};
};

const usePanelEachColumnCommon = (props: PanelEachColumnProps) => {
  const updateConfig2 = useUpdateConfig2(props);
  const updateChildPanelConfig = useCallback(
    newItemConfig =>
      updateConfig2(oldConfig => ({
        ...oldConfig,
        render: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
      })),

    [updateConfig2]
  );
  const updateChildPanelConfig2 = useCallback(
    (change: (oldItemConfig: any) => any) => {
      updateConfig2(oldConfig => {
        const newItemConfig = change(oldConfig.render);
        return {
          ...oldConfig,
          render: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
        };
      });
    },
    [updateConfig2]
  );
  return useMemo(
    () => ({
      updateChildPanelConfig,
      updateChildPanelConfig2,
      updateConfig2,
    }),
    [updateChildPanelConfig, updateChildPanelConfig2, updateConfig2]
  );
};

export const PanelEachColumnConfigComp: React.FC<
  PanelEachColumnProps
> = props => {
  const config = props.config ?? PANEL_EACH_COLUMN_DEFAULT_CONFIG;
  const {updateChildPanelConfig, updateChildPanelConfig2} =
    usePanelEachColumnCommon(props);
  const {dashboardConfigOptions} = usePanelContext();

  const newVars = useMemo(() => {
    const columnNameNode = varNode('string', '<string>');
    return {
      columnName: columnNameNode,
      column: opPick({
        obj: props.input,
        key: varNode('string', 'columnName'),
      }),
    };
  }, [props.input]);

  return (
    <ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <VariableView newVars={newVars} />
      <ChildConfigContainer>
        <PanelContextProvider newVars={newVars}>
          <ChildPanelConfigComp
            pathEl="render"
            config={config.render}
            updateConfig={updateChildPanelConfig}
            updateConfig2={updateChildPanelConfig2}
          />
        </PanelContextProvider>
      </ChildConfigContainer>
    </ConfigSection>
  );
};

const tableColumnTypes = (tableType: Type): {[key: string]: Type} => {
  if (!isListLike(tableType)) {
    throw new Error('Expected list type');
  }
  const objectType = listObjectType(tableType);
  if (!isTypedDictLike(objectType)) {
    throw new Error('Expected typed dict type');
  }
  return typedDictPropertyTypes(objectType);
};

export const PanelEachColumn: React.FC<PanelEachColumnProps> = props => {
  const config = props.config ?? PANEL_EACH_COLUMN_DEFAULT_CONFIG;
  const {updateChildPanelConfig, updateChildPanelConfig2, updateConfig2} =
    usePanelEachColumnCommon(props);

  // const typedInputNode = CGReact.useNodeWithServerType(props.input);

  const colTypes = useMemo(() => {
    return tableColumnTypes(props.input.type);
  }, [props.input.type]);
  const colNames = Object.keys(colTypes);

  const [searchExpr, setSearchExpr] = useState<NodeOrVoidNode>(voidNode());

  const panels = useMemo(() => {
    const ps: {[key: string]: React.ReactNode} = {};
    colNames
      .filter(colName =>
        colName.includes(
          searchExpr.nodeType === 'const' && searchExpr.type === 'string'
            ? searchExpr.val
            : ''
        )
      )
      .forEach((columnName, i) => {
        const columnNameNode = constString(columnName);
        const column = opPick({
          obj: props.input,
          key: columnNameNode,
        });
        ps[columnName] = (
          <PanelContextProvider newVars={{columnName: columnNameNode, column}}>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
              }}>
              <div style={{whiteSpace: 'nowrap', textOverflow: 'ellipsis'}}>
                {columnName}
              </div>
              <div style={{flexGrow: 1}}>
                <ChildPanel
                  key={i}
                  config={config.render}
                  updateConfig={updateChildPanelConfig}
                  updateConfig2={updateChildPanelConfig2}
                />
              </div>
            </div>
          </PanelContextProvider>
        );
      });
    return ps;
  }, [
    colNames,
    searchExpr,
    props.input,
    config.render,
    updateChildPanelConfig,
    updateChildPanelConfig2,
  ]);

  const {pbLayoutConfig, updatePbLayoutConfig2} = usePbLayoutConfig(
    Object.keys(panels),
    config,
    updateConfig2
  );

  return (
    <div style={{height: '100%'}}>
      <WeaveExpression expr={searchExpr} setExpression={setSearchExpr} />
      <PBSection
        mode="flow"
        config={pbLayoutConfig}
        updateConfig2={updatePbLayoutConfig2}
        renderPanel={panel => {
          return panels[panel.id];
        }}
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'EachColumn',
  initialize: (weave, inputNode) => PANEL_EACH_COLUMN_DEFAULT_CONFIG,
  ConfigComponent: PanelEachColumnConfigComp,
  Component: PanelEachColumn,
  inputType,
  hidden: true,
};
