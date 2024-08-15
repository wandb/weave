/**
 * This file is responsible for building a tree structure consumable by the x-data-grid-pro component,
 * given a list of strings representing the paths of the columns. Given a list of strings like:
 * `['a.b.c', 'a.b.d', 'a.e', 'f']`, we want to build a tree like:
 * ```
 * root
 * ├── a (group)
 * │   ├── a.b (group)
 * │   │   ├── a.b.c (leaf)
 * │   │   └── a.b.d (leaf)
 * │   └── a.e (leaf)
 * └── f (leaf)
 * ```
 *
 * Note, there is a special case where a leaf column is a prefix of a group column. In this case, the leaf column
 * should be pushed into the group column. For example, given the list of strings `['a.b', 'a.b.c']`, we want to build
 * a tree like:
 * ```
 * root
 * └── a (group)
 *     └── a.b (group)
 *         ├── a.b (leaf) // This is a special case (notice that the leaf is inside the group)
 *         └── a.b.c (leaf)
 * ```
 *
 * However, we would not want to push a leaf column into a group column if the leaf column is not a prefix of the group
 * for example, given the list of strings `['a.b', 'a.c']`, we want to build a tree like:
 * ```
 * root
 * └── a (group)
 *     ├── a.b (leaf) // This is not a special case (notice that the leaf is not inside the group)
 *     └── a.c (leaf)
 * ```
 */

import {
  GridColumnGroup,
  GridColumnNode,
  GridLeafColumn,
} from '@mui/x-data-grid-pro';

export function buildTree(strings: string[]): GridColumnGroup {
  const root: GridColumnGroup = {groupId: '', children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, str, 0);
  }

  return pushLeavesIntoGroupsForGroup(root);
}

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string,
  depth: number
): void {
  if (!fields.length) {
    return;
  }

  if (fields.length === 1) {
    node.children.push({
      field: fullPath,
    });
    return;
  }

  for (const child of node.children) {
    if ('groupId' in child && child.headerName === fields[0]) {
      addToTree(child as GridColumnGroup, fields.slice(1), fullPath, depth + 1);
      return;
    }
  }

  const newNode: GridColumnGroup = {
    headerName: fields[0],
    groupId: fullPath
      .split('.')
      .slice(0, depth + 1)
      .join('.'),
    children: [],
  };
  node.children.push(newNode);
  addToTree(newNode, fields.slice(1), fullPath, depth + 1);
}
function nodeIsGroup(node: GridColumnNode): node is GridColumnGroup {
  return 'groupId' in node;
}
function pushLeavesIntoGroupsForGroup(group: GridColumnGroup): GridColumnGroup {
  const originalChildren = group.children;

  const childrenLeaves: {[key: string]: GridLeafColumn} = Object.fromEntries(
    group.children
      .filter((child): child is GridLeafColumn => !nodeIsGroup(child))
      .map(child => [child.field, child])
  );

  const childrenGroups: {[key: string]: GridColumnGroup} = Object.fromEntries(
    group.children
      .filter((child): child is GridColumnGroup => nodeIsGroup(child))
      .map(child => [child.groupId, child])
  );

  // First, push leaves into groups
  Object.keys(childrenLeaves).forEach(childKey => {
    let found = false;
    Object.keys(childrenGroups).forEach(groupKey => {
      if (!found && childKey.startsWith(groupKey)) {
        childrenGroups[groupKey].children.push(childrenLeaves[childKey]);
        found = true;
      }
    });
    if (found) {
      delete childrenLeaves[childKey];
    }
  });

  // Next, recursively apply the same logic to the groups
  Object.keys(childrenGroups).forEach(key => {
    childrenGroups[key] = pushLeavesIntoGroupsForGroup(childrenGroups[key]);
  });

  const finalChildren = originalChildren
    .map(child => {
      if (nodeIsGroup(child)) {
        return childrenGroups[child.groupId];
      } else {
        return childrenLeaves[child.field];
      }
    })
    .filter((child): child is GridColumnNode => !!child);

  const newGroup: GridColumnGroup = {
    ...group,
    children: finalChildren,
  };

  return newGroup;
}
