import {
  constNodeUnsafe,
  dereferenceAllVars,
  isFunctionType,
  isNodeOrVoidNode,
  NodeOrVoidNode,
  pushFrame,
  replaceChainRoot,
  Stack,
  Type,
  voidNode,
  Weave,
} from '@wandb/weave/core';
import produce, {Draft} from 'immer';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import {Button} from 'semantic-ui-react';
import styled, {css} from 'styled-components';

import {useWeaveContext} from '../../context';
import {IdObj, PanelBankSectionConfig} from '../WeavePanelBank/panelbank';
import {getSectionConfig, PBSection} from '../WeavePanelBank/PBSection';
import {getPanelStacksForType} from './availablePanels';
import {
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  getFullChildPanel,
  isChildPanelFullConfig,
  mutateEnsureItemIsFullChildPanel,
} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import {LayoutSections} from './LayoutSections';
import {LayoutTabs} from './LayoutTabs';
import * as Panel2 from './panel';
import {ExpressionEvent, PanelContextProvider} from './PanelContext';
import {usePanelContext} from './PanelContext';
import {useSetPanelInputExprIsHighlighted} from './PanelInteractContext';
import {isGroupNode, nextPanelName} from './panelTree';

const LAYOUT_MODES = [
  'horizontal' as const,
  'vertical' as const,
  'grid' as const,
  'flow' as const,
  'tab' as const,
  'section' as const,
  'layer' as const,
];

export interface PanelGroupConfig {
  layoutMode: (typeof LAYOUT_MODES)[number];
  equalSize?: boolean;
  showExpressions?: boolean;
  style?: string;
  items: {[key: string]: ChildPanelConfig};
  gridConfig?: PanelBankSectionConfig;
  allowedPanels?: string[];
  enableAddPanel?: boolean;
  childNameBase?: string;
}

export const PANEL_GROUP_DEFAULT_CONFIG = (): PanelGroupConfig => ({
  layoutMode: 'vertical',
  equalSize: true,
  showExpressions: true,
  items: {},
});

const inputType = 'any';

type PanelGroupProps = Panel2.PanelProps<typeof inputType, PanelGroupConfig>;

export const Group = styled.div<{
  layered?: boolean;
  preferHorizontal?: boolean;
  compStyle?: string;
}>`
  ${props =>
    props.layered
      ? css`
          width: 100%;
          height: 100%;
          position: relative;
        `
      : props.preferHorizontal
      ? css`
          display: flex;
          height: 100%;
          flex-direction: row;
        `
      : css`
          display: flex;
          height: 100%;
          width: 100%;
          flex-direction: column;
        `}
  ${props => props.compStyle}
`;

export const GroupItem = styled.div<{
  width?: string;
  layered?: boolean;
  highlight?: boolean;
  preferHorizontal?: boolean;
  equalSize?: boolean;
}>`
  ${props =>
    props.layered
      ? css`
          position: absolute;
          top: 0;
          right: 0;
          bottom: 0;
          left: 0;
        `
      : props.preferHorizontal
      ? props.width
        ? css`
            width: ${props.width};
          `
        : props.equalSize
        ? css`
            flex: 1;
            width: 20px;
          `
        : css`
            flex-grow: 1;
            width: 20px;
          `
      : props.equalSize
      ? css`
          flex: 1;
          width: 100%;
          height: 20px;
          margin-bottom 12px;
        `
      : css`
          // flex-grow: 1;
          width: 100%;
          margin-bottom: 12px;
        `}
`;

// This is a mapping from JS PanelIDs to their corresponding Python type name
const panelIdAlternativeMapping: {[jsId: string]: string} = {
  // These are manually defined in Weave1 python panel module.
  table: 'tablePanel',
  number: 'PanelNumber',
  string: 'PanelString',
  boolean: 'PanelBoolean',
  date: 'PanelDate',
  // Below are defined in `panel_legacy.py`
  barchart: 'PanelBarchart',
  'web-viz': 'PanelWebViz',
  'video-file': 'PanelVideoFile',
  'model-file': 'PanelModelFile',
  'id-count': 'PanelIdCount',
  link: 'PanelLink',
  'run-overview': 'PanelRunOverview',
  none: 'PanelNone',
  artifactVersionAliases: 'PanelArtifactVersionAliases',
  netron: 'PanelNetron',
  object: 'PanelObject',
  'audio-file': 'PanelAudioFile',
  'string-histogram': 'PanelStringHistogram',
  rawimage: 'PanelRawimage',
  'precomputed-histogram': 'PanelPrecomputedHistogram',
  'image-file-compare': 'PanelImageFileCompare',
  'molecule-file': 'PanelMoleculeFile',
  'multi-histogram': 'PanelMultiHistogram',
  'object3D-file': 'PanelObject3DFile',
  'run-color': 'PanelRunColor',
  'multi-string-histogram': 'PanelMultiStringHistogram',
  dir: 'PanelDir',
  'id-compare-count': 'PanelIdCompareCount',
  jupyter: 'PanelJupyter',
  'bokeh-file': 'PanelBokehFile',
  ndarray: 'PanelNdarray',
  'id-compare': 'PanelIdCompare',
  unknown: 'PanelUnknown',
  'image-file': 'PanelImageFile',
  'project-overview': 'PanelProjectOverview',
  textdiff: 'PanelTextdiff',
  type: 'PanelType',
  text: 'PanelText',
  'string-compare': 'PanelStringCompare',
  'debug-expression-graph': 'PanelDebugExpressionGraph',
  tracer: 'PanelTracer',
};

export function toWeaveType(o: any): any {
  if (o == null) {
    return 'none';
  }

  if (o.domain != null && o.selection != null) {
    // More hacks to properly type nested objects that seem like dicts to
    // js.
    // TODO: Really need to support ObjectType in javascript!

    return {
      type: 'Signals',
      _is_object: true,
      domain: {
        ..._.mapValues(o.domain, toWeaveType),
        type: 'AxisSelections',
        _is_object: true,
      },
      selection: {
        ..._.mapValues(o.selection, toWeaveType),
        type: 'AxisSelections',
        _is_object: true,
      },
    };
  }

  if (o.dims != null && o.constants != null) {
    // More hacks to properly type nested objects that seem like dicts to
    // js.
    // TODO: Really need to support ObjectType in javascript!
    return {
      type: 'Series',
      _is_object: true,
      ..._.mapValues(_.omit(o, ['table', 'constants']), toWeaveType),
      table: {
        type: 'TableState',
        _is_object: true,
        ..._.mapValues(o.table, toWeaveType),
      },
      constants: {
        type: 'PlotConstants',
        _is_object: true,
        ..._.mapValues(o.constants, toWeaveType),
      },
    };
  }
  if (o.columns != null && o.columnNames != null) {
    const res = {
      type: 'TableState',
      _is_object: true,
      ..._.mapValues(o, toWeaveType),
    };
    return res;
  }

  if (o.id != null && o.input_node != null) {
    // Such hacks
    let curPanelId = o.id;

    if (curPanelId == null || curPanelId === '') {
      curPanelId = 'Auto';
    }
    // We have to rename some of the types so to avoid collisions with basic
    // types.
    if (panelIdAlternativeMapping[curPanelId] != null) {
      curPanelId = panelIdAlternativeMapping[curPanelId];
    }

    // This is a panel...
    let configType: Type = 'none';
    if (o.config != null) {
      configType = {
        type: curPanelId + 'Config',
        _is_object: true as any,
        ..._.mapValues(o.config, toWeaveType),
      } as any;
    }
    return {
      type: curPanelId,
      id: 'string',
      _is_object: true,
      vars: {
        type: 'typedDict',
        propertyTypes: _.mapValues(o.vars, toWeaveType),
      },
      input_node: toWeaveType(o.input_node),
      config: configType,
      _renderAsPanel: toWeaveType(o.config?._renderAsPanel),
    };
  } else if (o.nodeType != null) {
    if (o.nodeType === 'const' && isFunctionType(o.type)) {
      return o.type;
    }
    return {
      type: 'function',
      inputTypes: {},
      outputType: o.type,
    };
  } else if (_.isArray(o)) {
    return {
      type: 'list',
      objectType: o.length === 0 ? 'unknown' : toWeaveType(o[0]),
    };
  } else if (_.isObject(o)) {
    if ('_type' in o) {
      return {
        type: (o as {_type: any})._type,
        ..._.mapValues(_.omit(o, ['_type']), toWeaveType),
      };
    }
    return {
      type: 'typedDict',
      propertyTypes: _.mapValues(o, toWeaveType),
    };
  } else if (_.isString(o)) {
    return 'string';
  } else if (_.isNumber(o)) {
    return 'number'; // TODO
  } else if (_.isBoolean(o)) {
    return 'boolean';
  }
  throw new Error('Type conversion not implemeneted for value: ' + o);
}

export const fixChildData = (
  fullItem: ChildPanelFullConfig,
  weave: Weave
): ChildPanelFullConfig => {
  if (isGroupNode(fullItem)) {
    return {
      ...fullItem,
      config:
        fullItem.config == null
          ? undefined
          : {
              ...fullItem.config,
              items: _.mapValues(fullItem.config.items, item =>
                fixChildData(getFullChildPanel(item), weave)
              ),
            },
    };
  }
  return fullItem;
};

function dereferenceItemVars(item: any, stack: Stack, weave: Weave): any {
  // We fully dereference variables found with panels here. Because on the server
  // we end up with const(Panel).config... we need any expressions fetched in that
  // way to be executable (no variables present).

  // This function needs to be updated to mirror PanelContextProvider logic in any
  // panels.
  // TODO: standardize so we don't have to maintain this!
  if (isChildPanelFullConfig(item)) {
    const childStack = pushFrame(stack, {input: item.input_node});
    return {
      ...item,
      input_node: dereferenceAllVars(item.input_node, stack).node,
      config:
        item.config == null
          ? undefined
          : _.mapValues(item.config, child =>
              dereferenceItemVars(child, childStack, weave)
            ),
    };
  } else if (isNodeOrVoidNode(item)) {
    return dereferenceAllVars(item, stack).node;
  } else if (_.isPlainObject(item)) {
    return _.mapValues(item, child => dereferenceItemVars(child, stack, weave));
  }
  return item;
}

export function makeItemNode(
  item: ChildPanelConfig,
  stack: Stack,
  weave: Weave,
  allowedPanels: string[] | undefined
): NodeOrVoidNode {
  let fullItem = getFullChildPanel(item);
  const curPanelId = getPanelStacksForType(
    fullItem.input_node != null ? fullItem.input_node.type : 'invalid',
    fullItem.id,
    {allowedPanels}
  ).curPanelId;
  if (curPanelId === 'Expression') {
    return fullItem.input_node;
  }
  fullItem = {
    ...fullItem,
    id: fullItem.input_node != null ? curPanelId : fullItem.id,
    config: curPanelId === fullItem.id ? fullItem.config : undefined,
    _renderAsPanel: fullItem?.config?._renderAsPanel,
  } as any;
  fullItem = fixChildData(fullItem, weave);

  // Walk through the value, dereferencing encountered variables.
  fullItem = dereferenceItemVars(fullItem, stack, weave);

  const weaveType = toWeaveType(fullItem);
  return constNodeUnsafe(weaveType, fullItem);
}

function getItemVars(
  varName: string,
  item: ChildPanelConfig,
  stack: Stack,
  weave: Weave,
  allowedPanels: string[] | undefined
): {[name: string]: NodeOrVoidNode} {
  const fullItem = getFullChildPanel(item);
  if (isGroupNode(fullItem)) {
    // Recursive group variables are hoisted
    const result = _.mapValues(fullItem.config.items, i =>
      makeItemNode(i, stack, weave, fullItem.config.allowedPanels)
    );
    // some of the notebooks have not been updated to fetch nested
    // variables instead of accessing from the sidebar, so leaving this
    // here for now.
    result[varName] = makeItemNode(fullItem, stack, weave, allowedPanels);
    return result;
  }
  return {
    [varName]: makeItemNode(fullItem, stack, weave, allowedPanels),
  };
}

const usePanelGroupCommon = (props: PanelGroupProps) => {
  const {updateConfig2} = props;
  if (updateConfig2 == null) {
    throw new Error('updateConfig2 is required');
  }

  const handleAddPanel = useCallback(() => {
    updateConfig2(currentConfig => {
      let panelId = '';
      if (props.config?.allowedPanels != null) {
        panelId = props.config.allowedPanels[0];
      }
      return produce(currentConfig, draft => {
        draft.items[
          nextPanelName(
            Object.keys(currentConfig.items),
            props.config?.childNameBase
          )
        ] = {
          vars: {},
          id: panelId,
          input_node: voidNode(),
          config: undefined,
        };
      });
    });
  }, [props.config?.allowedPanels, props.config?.childNameBase, updateConfig2]);

  return useMemo(() => ({handleAddPanel}), [handleAddPanel]);
};

export const PanelGroupConfigComponent: React.FC<PanelGroupProps> = props => {
  const weave = useWeaveContext();
  const {handleAddPanel} = usePanelGroupCommon(props);
  const config = props.config ?? PANEL_GROUP_DEFAULT_CONFIG();
  const {updateConfig, updateConfig2} = props;
  const {path, selectedPath, stack, dashboardConfigOptions} = usePanelContext();
  let newVars: {[name: string]: NodeOrVoidNode} = {};

  const pathStr = path.join('.');
  const selectedPathStr = selectedPath?.join('.') ?? '';

  const curPanelSelected = pathStr.startsWith(selectedPathStr);

  // We are selected. Render our config.
  // if (curPanelSelected) {
  //   return (
  //     <>
  //       <ConfigPanel.ConfigOption label="Layout mode">
  //         <ConfigPanel.ModifiedDropdownConfigField
  //           options={LAYOUT_MODES.map(m => ({key: m, value: m, text: m}))}
  //           value={config.layoutMode}
  //           onChange={(e, {value}) => updateConfig({layoutMode: value as any})}
  //         />
  //       </ConfigPanel.ConfigOption>
  //       {/* <ConfigPanel.ConfigOption label="Equal size">
  //         <Checkbox
  //           checked={config.equalSize ?? false}
  //           onChange={(e, {checked}) => updateConfig({equalSize: !!checked})}
  //         />
  //       </ConfigPanel.ConfigOption>
  //       <ConfigPanel.ConfigOption label="Show Expressions">
  //         <Checkbox
  //           checked={config.showExpressions ?? false}
  //           onChange={(e, {checked}) =>
  //             updateConfig({showExpressions: !!checked})
  //           }
  //         />
  //       </ConfigPanel.ConfigOption> */}
  //       {/* <ConfigPanel.ConfigOption label="Style">
  //         <ConfigPanel.TextInputConfigField
  //           dataTest={`style`}
  //           value={config.style ?? ''}
  //           label={''}
  //           onChange={(event, {value}) => {
  //             updateConfig({
  //               style: value,
  //             });
  //           }}
  //         />
  //       </ConfigPanel.ConfigOption> */}
  //       <Button size="mini" onClick={handleAddPanel}>
  //         Add Panel
  //       </Button>
  //     </>
  //   );
  // }

  const childrenConfig = _.map(config.items, (item, name) => {
    const renderedItem = (
      <PanelContextProvider key={name} newVars={newVars}>
        <ChildPanelConfigComp
          allowedPanels={config.allowedPanels}
          pathEl={'' + name}
          config={item}
          updateConfig={newItemConfig =>
            updateConfig(
              produce(config, draft => {
                draft.items[name] = newItemConfig;
              })
            )
          }
          updateConfig2={(change: (oldConfig: any) => any) => {
            if (updateConfig2 == null) {
              return;
            }
            return updateConfig2(currentConfig => {
              currentConfig = currentConfig ?? PANEL_GROUP_DEFAULT_CONFIG();
              const fullChildPanel = getFullChildPanel(
                currentConfig?.items?.[name]
              );
              const changed = change(fullChildPanel);
              return produce(currentConfig, draft => {
                draft.items[name] = changed;
              });
            });
          }}
        />
      </PanelContextProvider>
    );

    newVars = {
      ...newVars,
      ...getItemVars(
        name,
        item,
        pushFrame(stack, newVars),
        weave,
        config.allowedPanels
      ),
    };

    return renderedItem;
  });

  if (!curPanelSelected) {
    // One of our descendants is selected.  Render children only
    return <>{childrenConfig}</>;
  }

  // We are selected. Render our config.
  return (
    <>
      <ConfigPanel.ConfigSection label={`Properties`}>
        {dashboardConfigOptions}
        <ConfigPanel.ConfigOption label="layout">
          <ConfigPanel.ModifiedDropdownConfigField
            options={LAYOUT_MODES.map(m => ({key: m, value: m, text: m}))}
            value={config.layoutMode}
            onChange={(e, {value}) => updateConfig({layoutMode: value as any})}
          />
        </ConfigPanel.ConfigOption>
        {/* <ConfigPanel.ConfigOption label="Equal size">
          <Checkbox
            checked={config.equalSize ?? false}
            onChange={(e, {checked}) => updateConfig({equalSize: !!checked})}
          />
        </ConfigPanel.ConfigOption>
        <ConfigPanel.ConfigOption label="Show Expressions">
          <Checkbox
            checked={config.showExpressions ?? false}
            onChange={(e, {checked}) =>
              updateConfig({showExpressions: !!checked})
            }
          />
        </ConfigPanel.ConfigOption> */}
        {/* <ConfigPanel.ConfigOption label="Style">
          <ConfigPanel.TextInputConfigField
            dataTest={`style`}
            value={config.style ?? ''}
            label={''}
            onChange={(event, {value}) => {
              updateConfig({
                style: value,
              });
            }}
          />
        </ConfigPanel.ConfigOption> */}
        <ConfigPanel.ChildConfigContainer>
          {childrenConfig}
        </ConfigPanel.ChildConfigContainer>
      </ConfigPanel.ConfigSection>
      <ConfigPanel.ConfigSection>
        <Button size="mini" onClick={handleAddPanel}>
          Add Child
        </Button>
      </ConfigPanel.ConfigSection>
    </>
  );
};

export const PanelGroupItem: React.FC<{
  item: ChildPanelConfig;
  name: string;
  config: PanelGroupConfig;
  updateConfig: (newConfig: PanelGroupConfig) => void;
  updateConfig2: (
    change: (oldConfig: PanelGroupConfig) => Partial<PanelGroupConfig>
  ) => void;
  siblingVars: {[name: string]: NodeOrVoidNode};
  handleSiblingVarEvent: (
    varName: string,
    target: NodeOrVoidNode,
    event: ExpressionEvent
  ) => void;
}> = ({
  siblingVars,
  item,
  name,
  config,
  updateConfig,
  updateConfig2,
  handleSiblingVarEvent,
}) => {
  const itemUpdateConfig = useCallback(
    (newItemConfig: any) =>
      updateConfig(
        produce(config, draft => {
          draft.items[name] = newItemConfig;
        })
      ),
    [config, name, updateConfig]
  );

  const itemUpdateConfig2 = useCallback(
    (change: (oldConfig: any) => any) => {
      if (updateConfig2 == null) {
        return;
      }
      return updateConfig2(currentConfig => {
        currentConfig = currentConfig ?? PANEL_GROUP_DEFAULT_CONFIG();
        const fullChildItem = getFullChildPanel(currentConfig?.items?.[name]);
        const changed = change(fullChildItem);
        return produce(currentConfig, draft => {
          draft.items[name] = changed;
        });
      });
    },
    [name, updateConfig2]
  );

  const itemUpdateName = useCallback(
    (newName: string) => {
      updateConfig(
        produce(config, draft => {
          draft.items[newName] = draft.items[name];
          delete draft.items[name];
        })
      );
    },
    [config, name, updateConfig]
  );

  return (
    <PanelContextProvider
      newVars={siblingVars}
      handleVarEvent={handleSiblingVarEvent}>
      <ChildPanel
        allowedPanels={config.allowedPanels}
        pathEl={'' + name}
        config={item}
        editable={config.layoutMode !== 'layer' && config.showExpressions}
        updateConfig={itemUpdateConfig}
        updateConfig2={itemUpdateConfig2}
        updateName={itemUpdateName}
      />
    </PanelContextProvider>
  );
};

const useSectionConfig = (
  config: PanelGroupConfig | undefined,

  updateConfig2: (
    change: (oldConfig: PanelGroupConfig) => Partial<PanelGroupConfig>
  ) => void
) => {
  const gridConfig = useMemo(() => {
    const conf = config ?? PANEL_GROUP_DEFAULT_CONFIG();
    return getSectionConfig(Object.keys(conf.items), conf.gridConfig);
  }, [config]);
  const updateGridConfig2 = useCallback(
    (change: (oldConfig: PanelBankSectionConfig) => PanelBankSectionConfig) => {
      return updateConfig2(currentConfig => {
        currentConfig = currentConfig ?? PANEL_GROUP_DEFAULT_CONFIG();
        const innerGridConfig = getSectionConfig(
          Object.keys(currentConfig.items),
          currentConfig.gridConfig
        );
        const newGridConfig = change(innerGridConfig);
        return produce(currentConfig, draft => {
          draft.gridConfig = newGridConfig;
        });
      });
    },
    [updateConfig2]
  );
  return {gridConfig, updateGridConfig2};
};

export const PanelGroup: React.FC<PanelGroupProps> = props => {
  const weave = useWeaveContext();
  const config = props.config ?? PANEL_GROUP_DEFAULT_CONFIG();
  const {stack} = usePanelContext();
  const {updateConfig, updateConfig2} = props;

  if (updateConfig2 == null) {
    // For dev only
    throw new Error('PanelGroup requires updateConfig2');
  }
  const {handleAddPanel} = usePanelGroupCommon(props);

  const mutateItem = useCallback(
    (name: string, applyFn: (item: Draft<ChildPanelFullConfig>) => void) => {
      console.log('HIGHLIGHT ITEM NAME', name);
      updateConfig2(currentConfig => {
        return produce(currentConfig, draft => {
          if (currentConfig.items[name] != null) {
            console.log('HIGHLIGHT DIRECT CHILD');
            mutateEnsureItemIsFullChildPanel(draft.items, name);
            applyFn(draft.items[name] as ChildPanelFullConfig);
          } else {
            _.forEach(currentConfig.items, (item, itemName) => {
              const fullItem = getFullChildPanel(item);
              if (
                fullItem.id === 'Group' &&
                fullItem.config.items[name] != null
              ) {
                console.log('HIGHLIGHT GRAND CHILD');
                mutateEnsureItemIsFullChildPanel(draft.items, itemName);
                mutateEnsureItemIsFullChildPanel(
                  (draft.items[itemName] as ChildPanelFullConfig).config.items,
                  name
                );
                applyFn(
                  (draft.items[itemName] as ChildPanelFullConfig).config.items[
                    name
                  ] as ChildPanelFullConfig
                );
              }
            });
          }
        });
      });
    },
    [updateConfig2]
  );

  const findItemPath = (findInConfig: PanelGroupConfig, name: string) => {
    if (findInConfig.items[name] != null) {
      return [name];
    } else {
      for (const [itemName, item] of Object.entries(findInConfig.items)) {
        const fullItem = getFullChildPanel(item);
        if (fullItem.id === 'Group' && fullItem.config.items[name] != null) {
          return [itemName, name];
        }
      }
    }
    throw new Error('Could not find item path for ' + name);
  };

  const {path: groupPath} = usePanelContext();
  const setPanelIsHighlightedByPath = useSetPanelInputExprIsHighlighted();
  const setItemIsHighlighted = useCallback(
    (name: string, isHighlighted: boolean) => {
      // console.log('SET ITEM IS HIGHLIGHTED', name, isHighlighted, config);
      const itemPath = groupPath.concat(findItemPath(config, name));
      setPanelIsHighlightedByPath(itemPath, isHighlighted);
    },
    [config, groupPath, setPanelIsHighlightedByPath]
  );

  const handleSiblingVarEvent = useCallback(
    (varName: string, target: NodeOrVoidNode, event: ExpressionEvent) => {
      console.log('PG2 handleSiblingVarEvent', varName, target, event);
      if (event.id === 'hover') {
        setItemIsHighlighted(varName, true);
        // mutateItem(varName, item => (item.highlight = true));
      } else if (event.id === 'unhover') {
        setItemIsHighlighted(varName, false);
        // mutateItem(varName, item => (item.highlight = false));
      } else if (event.id === 'mutate') {
        mutateItem(varName, item => {
          console.log('PG2 mutate input expr');
          item.input_node = replaceChainRoot(
            item.input_node,
            event.newRootNode
          );
        });
      }
    },
    [mutateItem, setItemIsHighlighted]
  );

  const childPanelsByKey = useMemo(() => {
    let newVars: {[name: string]: NodeOrVoidNode} = {};
    const keyedChildPanels: {[key: string]: React.ReactNode} = {};
    _.forEach(config.items, (item, name) => {
      const unwrappedItem = (
        <PanelContextProvider newVars={newVars}>
          <PanelGroupItem
            siblingVars={newVars}
            handleSiblingVarEvent={handleSiblingVarEvent}
            item={item}
            name={name}
            config={config}
            updateConfig={updateConfig}
            updateConfig2={updateConfig2}
          />
        </PanelContextProvider>
      );
      keyedChildPanels[name] = unwrappedItem;
      newVars = {
        ...newVars,
        ...getItemVars(name, item, stack, weave, config.allowedPanels),
      };
    });
    return keyedChildPanels;
  }, [
    config,
    handleSiblingVarEvent,
    stack,
    updateConfig,
    updateConfig2,
    weave,
  ]);
  const {gridConfig, updateGridConfig2} = useSectionConfig(
    props.config,
    updateConfig2
  );
  const renderSectionPanel = useCallback(
    (panel: IdObj) => {
      return childPanelsByKey[panel.id];
    },
    [childPanelsByKey]
  );

  if (config.layoutMode === 'grid' || config.layoutMode === 'flow') {
    return (
      <div style={{position: 'relative'}}>
        <PBSection
          mode={config.layoutMode}
          config={gridConfig}
          updateConfig2={updateGridConfig2}
          renderPanel={renderSectionPanel}
        />
        {config.enableAddPanel && (
          <Button
            size="tiny"
            style={{position: 'absolute', top: 0, right: 0}}
            onClick={handleAddPanel}>
            +
          </Button>
        )}
      </div>
    );
  }

  if (config.layoutMode === 'tab') {
    const tabNames = Object.keys(config.items);
    return (
      <div>
        <LayoutTabs tabNames={tabNames} renderPanel={renderSectionPanel} />
      </div>
    );
  }

  if (config.layoutMode === 'section') {
    const sectionNames = Object.keys(config.items);
    return (
      <div>
        <LayoutSections
          sectionNames={sectionNames}
          renderPanel={renderSectionPanel}
        />
      </div>
    );
  }

  return (
    <Group
      layered={config.layoutMode === 'layer'}
      preferHorizontal={config.layoutMode === 'horizontal'}
      compStyle={config.style}>
      {Object.entries(config.items).map(([name, item]) => {
        const childPanelConfig = getFullChildPanel(item).config;
        // Hacky: pull width up from child to here.
        // TODO: fix
        let width: string | undefined;
        if (childPanelConfig?.style != null) {
          const styleItems: string[] = childPanelConfig.style.split(';');
          const widthItem = styleItems.find(i => i.includes('width'));
          width = widthItem?.split(':')[1];
        }
        return (
          <GroupItem
            key={name}
            width={width}
            layered={config.layoutMode === 'layer'}
            preferHorizontal={config.layoutMode === 'horizontal'}
            equalSize={config.equalSize}>
            {childPanelsByKey[name]}
          </GroupItem>
        );
      })}
      {config.enableAddPanel && (
        <Button onClick={handleAddPanel} size="tiny">
          Add {props.config?.childNameBase ?? 'panel'}
        </Button>
      )}
    </Group>
  );
};

export const PANEL_GROUP2_ID = 'Group';

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  id: PANEL_GROUP2_ID,
  initialize: (weave, inputNode) => PANEL_GROUP_DEFAULT_CONFIG(),
  Component: PanelGroup,
  ConfigComponent: PanelGroupConfigComponent,
  inputType,
};
