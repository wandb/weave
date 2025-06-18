import { GridColumnGroupingModel } from "@mui/x-data-grid";

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
export const collapseGroupingModel = (groupingModel: GridColumnGroupingModel, maxRootGroups: number = 1, maxLeafGroups: number = 1): GridColumnGroupingModel => {
    // TODO: Implement this
  return groupingModel
};