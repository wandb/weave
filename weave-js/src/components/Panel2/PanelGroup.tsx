// Critical performance note: We must not depend on config/updateConfig
// in the callbacks we construct here. The stack that we construct in PanelContext
// depends on the callbacks, and we don't want to depend on current config state.
// If we do depend on current config state, everything in the UI will re-render
// all the time, because everything depends on stack.

import {
  constNodeUnsafe,
  dereferenceAllVars,
  isNodeOrVoidNode,
  NodeOrVoidNode,
  pushFrame,
  Stack,
  voidNode,
} from '@wandb/weave/core';
import {Draft, produce} from 'immer';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import {Button} from 'semantic-ui-react';
import styled, {css} from 'styled-components';

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
import {IconAddNew as IconAddNewUnstyled} from './Icons';
import {LayoutSections} from './LayoutSections';
import {LayoutTabs} from './LayoutTabs';
import * as Panel2 from './panel';
import {
  ExpressionEvent,
  PanelContextProvider,
  usePanelContext,
} from './PanelContext';
import {useSetPanelInputExprIsHighlighted} from './PanelInteractContext';
import {isGroupNode, nextPanelName} from './panelTree';
import {toWeaveType} from './toWeaveType';
// import {VarBar} from '../Sidebar/VarBar';
import {GRAY_350, GRAY_500, GRAY_800} from '../../common/css/globals.styles';
// import {inJupyterCell} from '../PagePanelComponents/util';
import {useUpdateConfig2} from './PanelComp';
import {replaceChainRoot} from '@wandb/weave/core/mutate';

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
  gridConfig: PanelBankSectionConfig;
  allowedPanels?: string[];
  enableAddPanel?: boolean;
  childNameBase?: string;
}

export const PANEL_GROUP_DEFAULT_CONFIG = (): PanelGroupConfig => ({
  layoutMode: 'vertical',
  equalSize: true,
  showExpressions: true,
  items: {},
  gridConfig: getSectionConfig([], undefined),
});

const inputType = 'any';

type PanelGroupProps = Panel2.PanelProps<typeof inputType, PanelGroupConfig>;

export const Group = styled.div<{
  layered?: boolean;
  preferHorizontal?: boolean;
  compStyle?: string;
  isVarBar: boolean;
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

  ${p =>
    p.isVarBar &&
    css`
      border-right: 1px solid ${GRAY_350};
      .edit-bar {
        border-bottom: none;
        border-top: 1px solid ${GRAY_350};
        padding-top: 12px;
        margin-bottom: 0;
      }
      > :first-child .edit-bar {
        border-top: none;
      }
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
          /* flex: 1 1 100px; */
          width: 100%;
          margin-bottom: 12px;
        `}
`;

export const fixChildData = (
  fullItem: ChildPanelFullConfig
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
                fixChildData(getFullChildPanel(item))
              ),
            },
    };
  }
  return fullItem;
};

function dereferenceItemVars(item: any, stack: Stack): any {
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
              dereferenceItemVars(child, childStack)
            ),
    };
  } else if (isNodeOrVoidNode(item)) {
    return dereferenceAllVars(item, stack).node;
  } else if (_.isPlainObject(item)) {
    return _.mapValues(item, child => dereferenceItemVars(child, stack));
  }
  return item;
}

export function makeItemNode(
  item: ChildPanelConfig,
  stack: Stack,
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
  fullItem = fixChildData(fullItem);

  // Walk through the value, dereferencing encountered variables.
  fullItem = dereferenceItemVars(fullItem, stack);

  const weaveType = toWeaveType(fullItem);
  return constNodeUnsafe(weaveType, fullItem);
}

export function getItemVars(
  varName: string,
  item: ChildPanelConfig,
  stack: Stack,
  allowedPanels: string[] | undefined
): {[name: string]: NodeOrVoidNode} {
  const fullItem = getFullChildPanel(item);
  if (isGroupNode(fullItem)) {
    // Recursive group variables are hoisted
    const result = _.mapValues(fullItem.config.items, i =>
      makeItemNode(i, stack, fullItem.config.allowedPanels)
    );
    // some of the notebooks have not been updated to fetch nested
    // variables instead of accessing from the sidebar, so leaving this
    // here for now.
    result[varName] = makeItemNode(fullItem, stack, allowedPanels);
    return result;
  }
  return {
    [varName]: makeItemNode(fullItem, stack, allowedPanels),
  };
}

export const addPanelToGroupConfig = (
  currentConfig: PanelGroupConfig,
  allowedPanels?: string[],
  childNameBase?: string,
  childConfig?: ChildPanelConfig
) => {
  let panelId = '';
  if (allowedPanels != null) {
    panelId = allowedPanels[0];
  }
  return produce(currentConfig, draft => {
    if (childConfig == null) {
      childConfig = {
        vars: {},
        id: panelId,
        input_node: voidNode(),
        config: undefined,
      };
    }
    draft.items[
      nextPanelName(Object.keys(currentConfig.items), childNameBase)
    ] = childConfig;
    if (currentConfig.layoutMode === 'flow') {
      // If there is only one panel, and one row and column, add a second
      // column. This is a nice behavior in notebooks.
      const nRows = currentConfig.gridConfig?.flowConfig.rowsPerPage ?? 1;
      const nCols = currentConfig.gridConfig?.flowConfig.columnsPerPage ?? 1;
      if (
        Object.keys(currentConfig.items).length === 1 &&
        nRows === 1 &&
        nCols === 1
      ) {
        draft.gridConfig.flowConfig.columnsPerPage = 2;
      }
    }
  });
};

const usePanelGroupCommon = (props: PanelGroupProps) => {
  const updateConfig2 = useUpdateConfig2(props);

  const handleAddPanel = useCallback(() => {
    updateConfig2(currentConfig => {
      return addPanelToGroupConfig(
        currentConfig,
        props.config?.allowedPanels,
        props.config?.childNameBase
      );
    });
  }, [props.config?.allowedPanels, props.config?.childNameBase, updateConfig2]);

  return useMemo(() => ({handleAddPanel}), [handleAddPanel]);
};

export const PanelGroupConfigComponent: React.FC<PanelGroupProps> = props => {
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
  const config = props.config ?? PANEL_GROUP_DEFAULT_CONFIG();
  const {stack, path: groupPath} = usePanelContext();
  const {updateConfig} = props;
  const updateConfig2 = useUpdateConfig2(props);
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

  const setPanelIsHighlightedByPath = useSetPanelInputExprIsHighlighted();
  const setItemIsHighlighted = useCallback(
    (name: string, isHighlighted: boolean) => {
      // NOTE: this uses updateConfig2, even though we don't intend to update
      // the config (we just return it from the updateConfig2 callback). This
      // let's us get access to the current config, without depending on it
      // in our closure. This is critical for performance.
      updateConfig2(currentConfig => {
        // console.log('SET ITEM IS HIGHLIGHTED', name, isHighlighted, config);
        const itemPath = groupPath.concat(findItemPath(currentConfig, name));
        setPanelIsHighlightedByPath(itemPath, isHighlighted);
        return currentConfig;
      });
    },
    [groupPath, setPanelIsHighlightedByPath, updateConfig2]
  );

  const handleSiblingVarEvent = useCallback(
    (varName: string, target: NodeOrVoidNode, event: ExpressionEvent) => {
      console.log('PG2 handleSiblingVarEvent', varName, target, event);
      if (event.id === 'hover') {
        setItemIsHighlighted(varName, true);
      } else if (event.id === 'unhover') {
        setItemIsHighlighted(varName, false);
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
        ...getItemVars(name, item, stack, config.allowedPanels),
      };
    });
    return keyedChildPanels;
  }, [config, handleSiblingVarEvent, stack, updateConfig, updateConfig2]);
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

  // const inJupyter = inJupyterCell();
  // TODO: This special-case rendering is insane
  const isVarBar = _.isEqual(groupPath, [`sidebar`]);
  // if (isVarBar) {
  //   return (
  //     <VarBar
  //       config={config}
  //       updateConfig={updateConfig}
  //       handleSiblingVarEvent={handleSiblingVarEvent}
  //       stack={stack}
  //       handleAddVar={handleAddPanel}
  //     />
  //   );
  // }

  if (config.layoutMode === 'grid' || config.layoutMode === 'flow') {
    return (
      <PBSection
        mode={config.layoutMode}
        config={gridConfig}
        groupPath={groupPath}
        enableAddPanel={config.enableAddPanel}
        updateConfig2={updateGridConfig2}
        renderPanel={renderSectionPanel}
        handleAddPanel={config.enableAddPanel ? handleAddPanel : undefined}
      />
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
      className="group"
      isVarBar={isVarBar}
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
      {config.enableAddPanel &&
        (isVarBar ? (
          <AddVarButton onClick={handleAddPanel}>
            New variable
            <IconAddNew />
          </AddVarButton>
        ) : (
          <Button onClick={handleAddPanel} size="tiny">
            Add {props.config?.childNameBase ?? 'panel'}
          </Button>
        ))}
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

const AddVarButton = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  padding: 12px;
  cursor: pointer;
  width: calc(100%);
  border-top: 1px solid ${GRAY_350};

  color: ${GRAY_500};
  &:hover {
    color: ${GRAY_800};
  }

  svg {
    width: 18px;
    height: 18px;
  }
`;

const IconAddNew = styled(IconAddNewUnstyled)`
  width: 18px;
  height: 18px;
`;
