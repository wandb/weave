import {
  GridColumnGroup,
  GridColumnNode,
  GridLeafColumn,
} from '@mui/x-data-grid-pro';

/// Start of RunsTable.tsx move over
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

  // Next, apply the same logic to the groups
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
export function buildTree(strings: string[]): GridColumnGroup {
  const root: GridColumnGroup = {groupId: '', children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, str, 0);
  }

  return pushLeavesIntoGroupsForGroup(root);
}
