import {
  GridColumnGroup,
  GridColumnGroupingModel,
  GridColumnNode,
  GridLeafColumn,
} from '@mui/x-data-grid';

/**
 * Collapses all groups in the grouping model. Specifically, a `GridColumnGroupingModel` can be throught of
 * as a tree of columns. Effectively, for each unique path from the root to a leaf, we want to keep at most
 * `maxRootGroups` starting from the root and `maxLeafGroups` ending at the leaf.
 *
 *
 * @param groupingModel - The grouping model to collapse.
 * @param maxRootGroups - The maximum number of root groups to keep.
 * @param maxLeafGroups - The maximum number of leaf groups to keep.
 * @returns The collapsed grouping model.
 */
export const collapseGroupingModel = (
  groupingModel: GridColumnGroupingModel,
  maxRootGroups: number = 1,
  maxLeafGroups: number = 1
): GridColumnGroupingModel => {
  // Helper function to check if a node is a group
  const isGroup = (node: GridColumnNode): node is GridColumnGroup => {
    return 'groupId' in node && 'children' in node;
  };

  // Helper function to check if a node is a leaf column
  const isLeafColumn = (node: GridColumnNode): node is GridLeafColumn => {
    return 'field' in node;
  };

  // Helper function to collect all paths from a node to its leaf columns
  const collectPaths = (
    node: GridColumnGroup,
    currentPath: GridColumnGroup[] = []
  ): Array<{path: GridColumnGroup[]; leaf: GridLeafColumn}> => {
    const paths: Array<{path: GridColumnGroup[]; leaf: GridLeafColumn}> = [];

    for (const child of node.children) {
      if (isLeafColumn(child)) {
        paths.push({path: [...currentPath], leaf: child});
      } else if (isGroup(child)) {
        paths.push(...collectPaths(child, [...currentPath, child]));
      }
    }

    return paths;
  };

  // Helper function to determine which groups to keep from a path
  const selectGroupsToKeep = (path: GridColumnGroup[]): GridColumnGroup[] => {
    if (path.length === 0) return [];

    const totalGroups = path.length;
    const totalToKeep = Math.min(maxRootGroups + maxLeafGroups, totalGroups);

    if (totalToKeep >= totalGroups) {
      // Keep all groups if we can
      return path;
    }

    // Keep maxRootGroups from the beginning and maxLeafGroups from the end
    const keptGroups: GridColumnGroup[] = [];

    // Add root groups
    const rootGroupsToKeep = Math.min(maxRootGroups, totalGroups);
    for (let i = 0; i < rootGroupsToKeep; i++) {
      keptGroups.push(path[i]);
    }

    // Add leaf groups (from the end)
    const leafGroupsToKeep = Math.min(
      maxLeafGroups,
      totalGroups - rootGroupsToKeep
    );
    const startLeafIndex = totalGroups - leafGroupsToKeep;

    for (let i = startLeafIndex; i < totalGroups; i++) {
      if (!keptGroups.includes(path[i])) {
        keptGroups.push(path[i]);
      }
    }

    return keptGroups;
  };

  // Helper function to build a new tree structure from selected paths
  const buildCollapsedTree = (
    pathsWithLeaves: Array<{
      keptGroups: GridColumnGroup[];
      leaf: GridLeafColumn;
    }>
  ): GridColumnGroup[] => {
    const rootGroups = new Map<string, GridColumnGroup>();

    for (const {keptGroups, leaf} of pathsWithLeaves) {
      if (keptGroups.length === 0) {
        // No groups kept, leaf should be at root level
        // This shouldn't happen given the function logic, but handle it anyway
        continue;
      }

      // Clone groups to avoid modifying the original
      const clonedGroups = keptGroups.map(g => ({
        ...g,
        children: [] as GridColumnNode[],
      }));

      // Get or create the root group
      const rootGroup = clonedGroups[0];
      if (!rootGroups.has(rootGroup.groupId)) {
        rootGroups.set(rootGroup.groupId, rootGroup);
      }

      // Build the chain of groups
      let currentParent = rootGroups.get(rootGroup.groupId)!;

      for (let i = 1; i < clonedGroups.length; i++) {
        const group = clonedGroups[i];

        // Find if this group already exists as a child
        let existingChild = currentParent.children.find(
          child => isGroup(child) && child.groupId === group.groupId
        ) as GridColumnGroup | undefined;

        if (!existingChild) {
          existingChild = group;
          currentParent.children.push(existingChild);
        }

        currentParent = existingChild;
      }

      // Add the leaf to the last group
      currentParent.children.push(leaf);
    }

    return Array.from(rootGroups.values());
  };

  // Process each top-level group
  const collapsedModel: GridColumnGroupingModel = [];

  for (const topLevelNode of groupingModel) {
    // All top-level nodes should be groups in GridColumnGroupingModel
    // Collect all paths from this top-level group
    const paths = collectPaths(topLevelNode, [topLevelNode]);

    // Select which groups to keep for each path
    const processedPaths = paths.map(({path, leaf}) => ({
      keptGroups: selectGroupsToKeep(path),
      leaf,
    }));

    // Build the collapsed tree
    const collapsedGroups = buildCollapsedTree(processedPaths);
    collapsedModel.push(...collapsedGroups);
  }

  return collapsedModel;
};
