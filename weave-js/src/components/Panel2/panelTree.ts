/* Reguralized structure for UI state.

The UI state is a tree of panels. There are three types of non-leaf panels:
- Group: A group of panels, children are stored at config.items in a map from name
  to child panel.
- "Standard panels": Panels that have one or more explicit children defined at a config
  key.
- "TableState panels": These use the older tableState format, where child panel information
  is split across a few keys in tableState.


*/

import {difference} from '@wandb/weave/common/util/data';
import {ID} from '@wandb/weave/common/util/id';
import {
  Client,
  Definition,
  dereferenceAllVars,
  EditingNode,
  Frame,
  isAssignableTo,
  isNodeOrVoidNode,
  NodeOrVoidNode,
  pushFrameDefs,
  refineEditingNode,
  Stack,
  updateVarNames,
  updateVarTypes,
  voidNode,
} from '@wandb/weave/core';
import {produce} from 'immer';
import * as _ from 'lodash';

import {
  LayoutParameters,
  PanelBankSectionConfig,
} from '../WeavePanelBank/panelbank';
import {
  ChildPanelConfig,
  childPanelFromTableState,
  ChildPanelFullConfig,
  getFullChildPanel,
} from './ChildPanel';
import {
  getItemVarPaths,
  getItemVars,
  PANEL_GROUP2_ID,
  PanelGroupConfig,
} from './PanelGroup';

export type PanelTreeNode = ChildPanelConfig;

interface GroupNode {
  vars: Frame;
  input_node: NodeOrVoidNode;
  id: typeof PANEL_GROUP2_ID;
  config: PanelGroupConfig;
}

export const isGroupNode = (node: PanelTreeNode): node is GroupNode => {
  const fullNode = getFullChildPanel(node);
  return fullNode.id === PANEL_GROUP2_ID;
};

const STANDARD_PANEL_CHILD_KEYS: {[key: string]: string[]} = {
  Each: ['panel', 'layout'],
  EachColumn: ['render'],
  FacetTabs: ['panel'],
  Sections: ['panel'],
};

const isStandardPanel = (id: string): boolean => {
  return Object.keys(STANDARD_PANEL_CHILD_KEYS).includes(id);
};

const isTableStatePanel = (id: string): boolean => {
  return ['table', 'Facet'].includes(id);
};

const getTableStatePanelChildren = (
  panel: ChildPanelFullConfig
): null | {[key: string]: ChildPanelFullConfig} => {
  if (panel.id === 'table') {
    const colIds = Object.keys(panel.config.tableState.columns);
    return _.fromPairs(
      colIds.map(colId => [
        colId,
        childPanelFromTableState(panel.config.tableState, colId),
      ])
    );
  } else if (panel.id === 'Facet') {
    return {
      select: childPanelFromTableState(
        panel.config.table,
        panel.config.dims.select
      ),
    };
  }
  return null;
};

const setTableStatePanelChild = (
  panel: ChildPanelFullConfig,
  key: string,
  value: ChildPanelFullConfig
): ChildPanelFullConfig => {
  if (panel.id === 'table') {
    return produce(panel, draft => {
      draft.config.tableState.columnSelectFunctions[key] = value.input_node;
      draft.config.tableState.columns[key] = {
        panelId: value.id,
        panelConfig: value.config,
      };
    });
  } else if (panel.id === 'Facet') {
    const colId = panel.config.dims[key];
    if (colId == null) {
      throw new Error('cannot set table state panel child');
    }
    return produce(panel, draft => {
      draft.config.table.columnSelectFunctions[colId] = value.input_node;
      draft.config.table.columns[colId] = {
        panelId: value.id,
        panelConfig: value.config,
      };
    });
  }
  throw new Error('cannot set table state panel child');
};

export const panelChildren = (
  panel: ChildPanelFullConfig
): {[key: string]: ChildPanelFullConfig} | null => {
  const panelId = panel.id;
  // TODO: This should not need to be hardcoded but we don't
  // have panel config types available in the WeaveJS right now
  if (panelId === 'Group') {
    return panel.config.items;
  } else if (isStandardPanel(panelId)) {
    return _.fromPairs(
      STANDARD_PANEL_CHILD_KEYS[panelId].map(key => [
        key,
        getFullChildPanel(panel.config[key]),
      ])
    );
  } else if (isTableStatePanel(panelId)) {
    return getTableStatePanelChildren(panel);
  }
  return null;
};

export function getConfigForPath(
  config: ChildPanelFullConfig,
  path: string[]
): ChildPanelFullConfig {
  if (path.length === 0) {
    return config;
  }
  const key = path[0];
  const children = panelChildren(config);
  if (children == null) {
    throw new Error('Children not found');
  }
  return getConfigForPath(children[key], path.slice(1));
}

export const nextPanelName = (
  existingNames: string[],
  varNameBase?: string
) => {
  varNameBase = varNameBase ?? 'panel';
  for (let i = 0; i < 1000; i++) {
    const name = `${varNameBase}${i}`;
    if (!existingNames.includes(name)) {
      return name;
    }
  }
  throw new Error('Could not find a unique panel name');
};

export const makePanel = (
  id: string,
  config: any,
  inputNode?: NodeOrVoidNode
): ChildPanelFullConfig => {
  return {
    vars: {},
    id,
    input_node: inputNode ?? voidNode(),
    config,
  };
};

export const makeGroup = (
  items: PanelGroupConfig['items'],
  options?: Omit<PanelGroupConfig, 'items'>
) => {
  return makePanel('Group', {items, ...options});
};

export const getPath = (
  node: PanelTreeNode,
  path: string[]
): ChildPanelFullConfig => {
  node = getFullChildPanel(node);
  if (path.length === 0) {
    return node;
  }
  const key = path[0];
  let child;
  if (isGroupNode(node)) {
    child = node.config.items[key];
  } else if (isStandardPanel(node.id)) {
    child = node.config[key];
  } else if (isTableStatePanel(node.id)) {
    const tableStateChildren = getTableStatePanelChildren(node);
    if (tableStateChildren != null) {
      child = tableStateChildren[key];
    }
  }
  if (child == null) {
    throw new Error('cannot get children for node');
  }
  return getPath(child, path.slice(1));
};

export const setPath = (
  node: PanelTreeNode,
  path: string[],
  value: PanelTreeNode
): ChildPanelFullConfig => {
  const fullNode = getFullChildPanel(node);
  if (path.length === 0) {
    return getFullChildPanel(value);
  }
  const newChild = setPath(
    getPath(fullNode, [path[0]]),
    path.slice(1, path.length),
    value
  );
  if (isGroupNode(fullNode)) {
    return produce(fullNode, draft => {
      draft.config.items[path[0]] = newChild;
    });
  } else if (isStandardPanel(fullNode.id)) {
    return produce(fullNode, draft => {
      draft.config[path[0]] = newChild;
    });
  } else if (isTableStatePanel(fullNode.id)) {
    return setTableStatePanelChild(fullNode, path[0], newChild);
  }
  throw new Error('cannot set path for node');
};

// TODO: this hasn't been updated for regularized representation (Group, Standard, TableState)
// as addPath and getPath have.
export const removePath = (
  node: PanelTreeNode,
  path: string[]
): {newNode: PanelTreeNode; removed: PanelTreeNode} => {
  const fullNode = getFullChildPanel(node);
  if (path.length === 0) {
    throw new Error('path not found');
  } else if (path.length === 1) {
    if (!isGroupNode(fullNode)) {
      throw new Error('Cannot remove child from non-group panel');
    }
    if (fullNode.config.items[path[0]] == null) {
      throw new Error('No child at path to remove');
    }

    return {
      newNode: produce(fullNode, draft => {
        delete draft.config.items[path[0]];
      }),

      removed: fullNode.config.items[path[0]],
    };
  }
  // recurse
  if (!isGroupNode(fullNode)) {
    throw new Error('Cannot remove child from non-group panel');
  }
  if (fullNode.config.items[path[0]] == null) {
    throw new Error('No child at path to remove');
  }
  const {newNode: newChildNode, removed} = removePath(
    fullNode.config.items[path[0]],
    path.slice(1)
  );
  const newNode = produce(fullNode, draft => {
    draft.config.items[path[0]] = newChildNode;
  });

  return {newNode, removed};
};

export const movePath = (
  config: PanelTreeNode,
  fromPath: string[],
  toPath: string[]
) => {
  const {newNode, removed} = removePath(config, fromPath);
  return setPath(newNode, toPath, removed);
};

export const addChild = (
  node: PanelTreeNode,
  path: string[],
  value: PanelTreeNode,
  panelName: string,
  layout?: LayoutParameters
) => {
  const group = getPath(node, path);
  if (!isGroupNode(group)) {
    throw new Error('Cannot add child to non-group panel');
  }
  const groupValue = {
    ...group,
    config: {
      ...group.config,
      items: {
        ...group.config.items,
        [panelName]: value,
      },
    },
  };

  // Set the location for the new child
  if (layout && groupValue.config.gridConfig) {
    groupValue.config = {
      ...groupValue.config,
      gridConfig: {
        ...groupValue.config.gridConfig,
        panels: [
          ...groupValue.config.gridConfig.panels,
          {
            id: panelName,
            layout,
          },
        ],
      },
    };
  }

  return setPath(node, path, groupValue);
};

type DefinitionWithDirtyHandler = Definition & {
  dirty?: boolean;
};

function updateStackForItem(
  key: string,
  panel: ChildPanelFullConfig,
  stack: DefinitionWithDirtyHandler[],
  allowedPanels: string[] | undefined,
  path: string[] = [],
  dirtyAction?: Action
): DefinitionWithDirtyHandler[] {
  const childVars = getItemVars(key, panel, stack, allowedPanels);
  const childVarPaths = getItemVarPaths(key, panel);
  for (const varName of Object.keys(childVars)) {
    const varPath = [...path, ...childVarPaths[varName]];
    let dirty = false;
    if (dirtyAction != null && _.isEqual(varPath, dirtyAction.path)) {
      dirty = true;
    }
    stack = pushFrameDefs(stack, [
      {
        name: varName,
        value: childVars[varName],
        dirty,
      },
    ]);
  }
  return stack;
}

// Must match the variables that the rest of the UI
// pushes onto the stack!
// Implementation should exactly match mapPanelsAsync
export const mapPanels = (
  node: PanelTreeNode,
  stack: Stack,
  fn: (node: ChildPanelFullConfig, stack: Stack) => ChildPanelFullConfig,

  // path and dirtyAction are optional. They are used for special behavior where
  // we mark a variable as dirty when we encounter it, based on whatever is specified
  // in dirtyAction.
  dirtyAction?: Action,
  path: string[] = []
): ChildPanelFullConfig => {
  const fullNode = getFullChildPanel(node);
  let withMappedChildren: ChildPanelFullConfig = fullNode;
  if (isGroupNode(fullNode)) {
    const items: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(fullNode.config.items)) {
      items[key] = mapPanels(
        fullNode.config.items[key],
        stack,
        fn,
        dirtyAction,
        [...path, key]
      );
      stack = updateStackForItem(
        key,
        items[key],
        stack,
        fullNode.config.allowedPanels,
        path,
        dirtyAction
      );
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, items},
    };
  } else if (isStandardPanel(fullNode.id)) {
    const children: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(STANDARD_PANEL_CHILD_KEYS[fullNode.id])) {
      children[key] = mapPanels(fullNode.config[key], stack, fn, dirtyAction, [
        ...path,
        key,
      ]);
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, ...children},
    };
  } else if (isTableStatePanel(fullNode.id)) {
    // TODO: not yet handled
  }
  // TODO: This doesn't create "input" variables like ChildPanel does. But I think that's ok
  // because it only happens at render time?

  return fn(withMappedChildren, stack);
};

// Implementation should exactly match mapPanels (the sync version!)
export const mapPanelsAsync = async (
  node: PanelTreeNode,
  stack: Stack,
  fn: (
    node: ChildPanelFullConfig,
    stack: Stack
  ) => Promise<ChildPanelFullConfig>,
  dirtyAction?: Action,
  path: string[] = []
): Promise<ChildPanelFullConfig> => {
  const fullNode = getFullChildPanel(node);
  let withMappedChildren: ChildPanelFullConfig = fullNode;
  if (isGroupNode(fullNode)) {
    const items: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(fullNode.config.items)) {
      items[key] = await mapPanelsAsync(
        fullNode.config.items[key],
        stack,
        fn,
        dirtyAction,
        [...path, key]
      );
      stack = updateStackForItem(
        key,
        items[key],
        stack,
        fullNode.config.allowedPanels,
        path,
        dirtyAction
      );
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, items},
    };
  } else if (isStandardPanel(fullNode.id)) {
    const children: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(STANDARD_PANEL_CHILD_KEYS[fullNode.id])) {
      children[key] = await mapPanelsAsync(
        fullNode.config[key],
        stack,
        fn,
        dirtyAction,
        [...path, key]
      );
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, ...children},
    };
  } else if (isTableStatePanel(fullNode.id)) {
    // TODO: not yet handled
  }
  // TODO: This doesn't create "input" variables like ChildPanel does. But I think that's ok
  // because it only happens at render time?

  return fn(withMappedChildren, stack);
};

interface Dashboard extends GroupNode {
  config: {
    layoutMode: 'horizontal';
    items: {
      sidebar: GroupNode;
      main: GroupNode;
    };
    gridConfig: PanelBankSectionConfig;
  };
}

const isDashboard = (node: PanelTreeNode): node is Dashboard => {
  const fullNode = getFullChildPanel(node);
  return (
    isGroupNode(fullNode) &&
    fullNode.config.items.main != null &&
    fullNode.config.items.sidebar != null
  );
};

/**
 * Returns whether a path points to the "main" group in a {@link Dashboard}
 */
export const isMain = (path: string[]): boolean => {
  return path[0] === 'main' && path.length === 1;
};

/**
 * Returns whether a path points to a panel *inside* the "main" group
 * in a {@link Dashboard}. **This excludes "main" itself!**
 *
 * @param path  path to the target panel
 * @param depth max depth of panels to include. For example, depth 1 will
 *              only return true for top-level panels in main.
 */
export const isInsideMain = (path: string[], depth = Infinity): boolean => {
  if (depth < 1) {
    throw new Error('depth must be at least 1');
  }
  return path[0] === 'main' && path.length > 1 && path.length <= 1 + depth;
};

export const ensureDashboard = (node: PanelTreeNode): ChildPanelFullConfig => {
  if (isDashboard(node)) {
    return node;
  }
  let main = node;
  const mainConfig = {
    layoutMode: 'grid' as const,
    showExpressions: true,
    enableAddPanel: true,
    disableDeletePanel: true,
    gridConfig: {
      id: ID(),
      panels: [
        {
          id: 'panel0',
          layout: {
            x: 0,
            y: 0,
            w: 24,
            h: 9,
          },
        },
      ],
    },
  };
  const full = getFullChildPanel(node);
  if (!isGroupNode(main)) {
    main = makeGroup({panel0: full}, mainConfig);
  } else {
    main = {
      ...main,
      config: {...main.config, ...mainConfig},
    };
  }
  return makeGroup(
    {
      sidebar: makeGroup(
        {
          var0: {
            vars: {},
            input_node: voidNode(),
            id: 'Expression',
            config: null,
          },
        },
        {
          layoutMode: 'vertical',
          equalSize: false,
          style: 'width:300px;',
          showExpressions: true,
          allowedPanels: [
            'Expression',
            'Query',
            'Slider',
            'StringEditor',
            'SelectEditor',
            'Dropdown',
            'FilterEditor',
            'GroupingEditor',
            'DateRange',
          ],
          enableAddPanel: true,
          disableDeletePanel: true,
          childNameBase: 'var',
        }
      ),
      main,
    },
    {layoutMode: 'horizontal', disableDeletePanel: true}
  );
};

export const ensureDashboardFromItems = (
  seedItems: {[name: string]: ChildPanelFullConfig},
  vars: {[name: string]: NodeOrVoidNode}
): ChildPanelFullConfig => {
  const mainConfig = {
    layoutMode: 'grid' as const,
    showExpressions: true,
    enableAddPanel: true,
    disableDeletePanel: true,
    gridConfig: {
      id: ID(),
      panels: Object.entries(seedItems).map(([name, item], ndx) => ({
        id: name,
        layout: {
          x: 0,
          y: ndx * 10,
          w: 24,
          h: 9,
        },
      })),
    },
  };
  const main = makeGroup(seedItems, mainConfig);
  if (Object.keys(vars).length === 0) {
    vars = {var0: voidNode()};
  }
  const sidebarVars = _.mapValues(vars, (node, name) =>
    getFullChildPanel({
      vars: {},
      input_node: node,
      id: 'Expression',
      config: null,
    })
  );
  return makeGroup(
    {
      sidebar: makeGroup(sidebarVars, {
        layoutMode: 'vertical',
        equalSize: false,
        style: 'width:300px;',
        showExpressions: true,
        allowedPanels: [
          'Expression',
          'Query',
          'Slider',
          'StringEditor',
          'SelectEditor',
          'Dropdown',
          'FilterEditor',
          'GroupingEditor',
          'DateRange',
        ],
        enableAddPanel: true,
        disableDeletePanel: true,
        childNameBase: 'var',
      }),
      main,
    },
    {layoutMode: 'horizontal', disableDeletePanel: true}
  );
};

export const ensureSimpleDashboard = (
  node: PanelTreeNode
): ChildPanelFullConfig => {
  return makeGroup(
    {panel0: getFullChildPanel(node)},
    {
      layoutMode: 'vertical',
      showExpressions: true,
      enableAddPanel: true,
      disableDeletePanel: true,
    }
  );
};

// Map a function over a panel config
const mapConfig = (c: any, mapFn: (v: any) => any) => {
  if (_.isArray(c)) {
    return c.map(mapFn);
  } else if (_.isObject(c)) {
    return _.mapValues(c, mapFn);
  } else {
    return mapFn(c);
  }
};

// Walk through all panels, updating VarNode types to match the types of
// the nodes they reference.
export const updateExpressionVarTypes = (node: PanelTreeNode, stack: Stack) => {
  return mapPanels(node, stack, (child, childStack) => {
    const newInputNode = updateVarTypes(child.input_node, childStack);
    const newVars = _.mapValues(child.vars, (varNode, varName) =>
      updateVarTypes(varNode, childStack)
    );
    let config = child.config;
    if (
      // Filter out these panels, since the map code walks them, correctly pushing
      // stuff onto stack as it goes.
      child.id !== 'Group' &&
      !isStandardPanel(child.id) &&
      !isTableStatePanel(child.id)
    ) {
      config = mapConfig(config, v =>
        isNodeOrVoidNode(v) ? updateVarTypes(v, childStack) : v
      );
    }
    return {
      vars: newVars,
      input_node: newInputNode,
      id: child.id,
      config,
    } as ChildPanelFullConfig;
  });
};

// This is called on an old config and new config, gets the delta
// if the delta lines up with a VarNameChange it updates the references to said VarName
// Note this function cannot be run to change a VarName, it can only be run to update the references
export const updateExpressionVarNamesFromConfig = (
  oldConfig: PanelTreeNode,
  newConfig: PanelTreeNode
) => {
  const addedDelta = difference(oldConfig, newConfig);
  const deletedDelta = difference(newConfig, oldConfig);
  const path = getPathFromDelta(addedDelta);
  const deletedPath = getPathFromDelta(deletedDelta);

  const oldName = deletedPath[deletedPath.length - 1];
  const newName = path[path.length - 1];

  if (
    // If the paths are the same, and the configs are the same except for the varName, we rename
    path.slice(0, path.length - 1).join('.') ===
      deletedPath.slice(0, deletedPath.length - 1).join('.') &&
    _.isEqual(
      getConfigForPath(getFullChildPanel(newConfig), path),
      getConfigForPath(getFullChildPanel(oldConfig), deletedPath)
    )
  ) {
    return updateExpressionVarNames(
      newConfig,
      [],
      deletedPath,
      oldName,
      newName
    );
  }
  return getFullChildPanel(newConfig);
};

// Note this function cannot be run to change a VarName, it can only be run to update the references
export const updateExpressionVarNames = (
  node: PanelTreeNode,
  stack: Stack,
  path: string[],
  oldName: string,
  newName: string
) => {
  return mapPanels(
    node,
    stack,
    (child, childStack) => {
      let newInputNode = child.input_node;
      // marks null vars as dirty as well
      // vars under the oldname will be null
      const res = dereferenceAllVars(child.input_node, childStack, true);
      for (const def of res.usedStack) {
        if ((def as any).dirty) {
          // if any of those variables are dirty, update the input_node
          newInputNode = updateVarNames(
            child.input_node,
            childStack,
            oldName,
            newName
          ) as NodeOrVoidNode;
          break;
        }
      }

      const newVars = _.mapValues(child.vars, (varNode, varName) =>
        updateVarNames(varNode, childStack, oldName, newName)
      );

      let config = child.config;
      if (
        // Filter out these panels, since the map code walks them, correctly pushing
        // stuff onto stack as it goes.
        child.id !== 'Group' &&
        !isStandardPanel(child.id) &&
        !isTableStatePanel(child.id)
      ) {
        config = mapConfig(config, v =>
          isNodeOrVoidNode(v)
            ? updateVarNames(v, childStack, oldName, newName)
            : v
        );
      }
      return {
        vars: newVars,
        input_node: newInputNode,
        id: child.id,
        config,
      } as ChildPanelFullConfig;
    },
    {
      type: 'VarRename',
      path,
      newName,
    }
  );
};

const removeListTypeMinMax = (t: any): any => {
  if (_.isArray(t)) {
    return t.map(removeListTypeMinMax);
  }
  if (_.isObject(t)) {
    const res: {[key: string]: any} = {};
    for (const [key, value] of Object.entries(t)) {
      if (key !== 'minLength' && key !== 'maxLength') {
        res[key] = removeListTypeMinMax(value);
      }
    }
    return res;
  }
  return t;
};

export const refineAllExpressions = async (
  client: Client,
  panel: PanelTreeNode,
  stack: Stack
) => {
  // We walk all panels, refining all input_nodes.

  // not sure if providing this refine cache really helps anything, but why not.
  const refineCache = new Map<EditingNode, EditingNode>();

  const refined = await mapPanelsAsync(
    panel,
    stack,
    async (p: ChildPanelFullConfig, childStack: Stack) => {
      const refinedInputNode = (await refineEditingNode(
        client,
        p.input_node,
        childStack,
        refineCache
      )) as NodeOrVoidNode;

      const newInputNodeType = removeListTypeMinMax(refinedInputNode.type);
      // Refining can produce a narrower type, like when a column is added  to table.
      // It can also produce a wider type, like when a column is removed from a table or
      //   when a string becomes Union<string, number>.
      // In either case, we need to make the update.
      if (
        !isAssignableTo(p.input_node.type, newInputNodeType) ||
        !isAssignableTo(newInputNodeType, p.input_node.type)
      ) {
        // we refined to a narrower type, so make the update
        return {...p, input_node: refinedInputNode};
      }
      return p;

      // A former attempt at hydration also initialized all the panels.
      // This is still more correct, but I haven't tried to get it fully working yet.
      // We want to do this because Python code doesn't always hydrate panels, for
      // example it may just set an input_node and expect js to figure out an auto
      // panel.
      // const {id, config} = await initPanel(
      //   weave,
      //   panel.input_node,
      //   panel.id,
      //   undefined,
      //   childStack
      // );
      // return {...panel, id, config};
    }
  );

  // Variables have .type attached, but what they refer to may now have a difference
  // type, so go through and update them.
  return updateExpressionVarTypes(refined, stack);
};

type PanelConfigUpdateAction = {
  type: 'PanelConfigUpdate';
  path: string[];
};

type VarRenameAction = {
  type: 'VarRename';
  path: string[];
  newName: string;
};

type Action = PanelConfigUpdateAction | VarRenameAction;

const getPathFromDelta = (delta: any): string[] => {
  if (delta.config == null || delta.config.items == null) {
    return [];
  }
  const keys = Object.keys(delta.config.items);
  if (keys.length === 0) {
    return [];
  }
  return [keys[0], ...getPathFromDelta(delta.config.items[keys[0]])];
};

const getActionFromDelta = (delta: any): Action => {
  const path = getPathFromDelta(delta);
  return {
    type: 'PanelConfigUpdate',
    path,
  };
};

// Given a prior config and a new config, first figure out what the change was.
// Then only refine the expressions that depend on any variables that changed.
export const refineForUpdate = async (
  client: Client,
  oldConfig: PanelTreeNode,
  newConfig: PanelTreeNode
) => {
  const delta = difference(oldConfig, newConfig);
  const dirtyAction = getActionFromDelta(delta);
  const refineCache = new Map<EditingNode, EditingNode>();
  return mapPanelsAsync(
    newConfig,
    [],
    async (panel, childStack) => {
      // Get all the variables used by this panel's input_node
      const res = dereferenceAllVars(panel.input_node, childStack);
      for (const def of res.usedStack) {
        if ((def as any).dirty) {
          // if any of those variables are dirty, refine the input_node
          const refinedInputNode = (await refineEditingNode(
            client,
            panel.input_node,
            childStack,
            refineCache
          )) as NodeOrVoidNode;
          return {...panel, input_node: refinedInputNode};
        }
      }
      return panel;
    },
    // We pass dirtyAction into mapNodesAsync, mapNodesAsync will mark the appropriate
    // variable as dirty when it encounters it.
    dirtyAction
  );
};
