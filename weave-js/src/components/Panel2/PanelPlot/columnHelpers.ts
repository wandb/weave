/**
 * Get information about columns for a table.
 */

import {
  allObjPaths,
  isAssignableTo,
  isSimpleTypeShape,
  isTimestamp,
  isUnion,
  nullableTaggableValue,
  Type,
} from '@wandb/weave/core';

import * as TableState from '../PanelTable/tableState';
import {PanelPlotProps} from './types';

export type Column = {
  path: string[];

  // We map the actual type of the column, which might be e.g. a union with 'none',
  // to a string that is easier to work with.
  type: string;
};
export type Columns = Column[];

const getColumnTypeForPropertyType = (propertyType: Type): string => {
  if (isUnion(propertyType)) {
    const nonNone = propertyType.members.filter(m => m !== 'none');
    if (nonNone.length > 0) {
      const nonNoneType = nonNone[0];
      if (isTimestamp(nonNoneType)) {
        return 'timestamp';
      } else if (isSimpleTypeShape(nonNoneType)) {
        return nonNoneType.toString();
      } else if (isAssignableTo(nonNoneType, {type: 'image-file'})) {
        return 'image';
      } else if (isAssignableTo(nonNoneType, {type: 'audio-file'})) {
        return 'audio';
      }
    }
  }
  return 'other';
};

export const getColumnsFromInput = (
  input: PanelPlotProps['input']
): Columns => {
  const exampleRow = TableState.getExampleRow(input);
  const propertyTypes = allObjPaths(nullableTaggableValue(exampleRow.type));
  // TODO: For dimensions like x and y, selecting an image column is just going
  //       to show an error in the plot. However, if we filtered those out here,
  //       you wouldn't be able to select them for a dimension like tooltip that
  //       can display them.
  //       See https://wandb.atlassian.net/browse/WB-16675
  return propertyTypes.map(({path, type}) => ({
    path,
    type: getColumnTypeForPropertyType(type),
  }));
};
