/* Reguralized structure for UI state.

The UI state is a tree of panels. There are three types of non-leaf panels:
- Group: A group of panels, children are stored at config.items in a map from name
  to child panel.
- "Standard panels": Panels that have one or more explicit children defined at a config
  key.
- "TableState panels": These use the older tableState format, where child panel information
  is split across a few keys in tableState.


*/

import {
  Frame,
  NodeOrVoidNode,
  pushFrame,
  Stack,
  voidNode,
} from '@wandb/weave/core';
import {produce} from 'immer';
import * as _ from 'lodash';

import {
  ChildPanelConfig,
  childPanelFromTableState,
  ChildPanelFullConfig,
  getFullChildPanel,
} from './ChildPanel';
import {getItemVars, PANEL_GROUP2_ID, PanelGroupConfig} from './PanelGroup';
import {PanelBankSectionConfig} from '../WeavePanelBank/panelbank';

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
  items: {[key: string]: ChildPanelConfig},
  options?: {[key: string]: any}
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
  value: PanelTreeNode
) => {
  const group = getPath(node, path);
  if (!isGroupNode(group)) {
    throw new Error('Cannot add child to non-group panel');
  }
  return setPath(node, path, {
    ...group,
    config: {
      ...group.config,
      items: {
        ...group.config.items,
        [nextPanelName(Object.keys(group.config.items))]: value,
      },
    },
  });
};

// Must match the variables that the rest of the UI
// pushes onto the stack!
// Implementation should exactly match mapPanelsAsync
export const mapPanels = (
  node: PanelTreeNode,
  stack: Stack,
  fn: (node: ChildPanelFullConfig, stack: Stack) => ChildPanelFullConfig
): ChildPanelFullConfig => {
  const fullNode = getFullChildPanel(node);
  let withMappedChildren: ChildPanelFullConfig = fullNode;
  if (isGroupNode(fullNode)) {
    const items: {[key: string]: ChildPanelFullConfig} = {};
    let childFrame: Frame = {};
    for (const key of Object.keys(fullNode.config.items)) {
      const childItem = fullNode.config.items[key];
      items[key] = mapPanels(
        fullNode.config.items[key],
        pushFrame(stack, childFrame),
        fn
      );
      const childVars = getItemVars(key, childItem, stack, undefined);
      childFrame = {...childFrame, ...childVars};
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, items},
    };
  } else if (isStandardPanel(fullNode.id)) {
    const children: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(STANDARD_PANEL_CHILD_KEYS[fullNode.id])) {
      children[key] = mapPanels(fullNode.config[key], stack, fn);
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, ...children},
    };
  } else if (isTableStatePanel(fullNode.id)) {
    // TODO: not yet handled
  }
  // TODO: This doesn't create "input" variables like ChildPanel does. But I think that's ok
  // becuase it only happens at render time?

  return fn(withMappedChildren, stack);
};

// Implementation should exactly match mapPanels (the sync version!)
export const mapPanelsAsync = async (
  node: PanelTreeNode,
  stack: Stack,
  fn: (
    node: ChildPanelFullConfig,
    stack: Stack
  ) => Promise<ChildPanelFullConfig>
): Promise<ChildPanelFullConfig> => {
  const fullNode = getFullChildPanel(node);
  let withMappedChildren: ChildPanelFullConfig = fullNode;
  if (isGroupNode(fullNode)) {
    const items: {[key: string]: ChildPanelFullConfig} = {};
    let childFrame: Frame = {};
    for (const key of Object.keys(fullNode.config.items)) {
      const childItem = fullNode.config.items[key];
      items[key] = await mapPanelsAsync(
        fullNode.config.items[key],
        pushFrame(stack, childFrame),
        fn
      );
      const childVars = getItemVars(
        key,
        childItem,
        stack,
        fullNode.config.allowedPanels
      );
      childFrame = {...childFrame, ...childVars};
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, items},
    };
  } else if (isStandardPanel(fullNode.id)) {
    const children: {[key: string]: ChildPanelFullConfig} = {};
    for (const key of Object.keys(STANDARD_PANEL_CHILD_KEYS[fullNode.id])) {
      children[key] = await mapPanelsAsync(fullNode.config[key], stack, fn);
    }
    withMappedChildren = {
      ...fullNode,
      config: {...fullNode.config, ...children},
    };
  } else if (isTableStatePanel(fullNode.id)) {
    // TODO: not yet handled
  }
  // TODO: This doesn't create "input" variables like ChildPanel does. But I think that's ok
  // becuase it only happens at render time?

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

export const ensureDashboard = (node: PanelTreeNode): ChildPanelFullConfig => {
  if (isDashboard(node)) {
    return node;
  }
  let main = node;
  const mainConfig = {
    layoutMode: 'grid',
    showExpressions: true,
    enableAddPanel: true,
    disableDeletePanel: true,
    gridConfig: {
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
    layoutMode: 'grid',
    showExpressions: true,
    enableAddPanel: true,
    disableDeletePanel: true,
    gridConfig: {
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
