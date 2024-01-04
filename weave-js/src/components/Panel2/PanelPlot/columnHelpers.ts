/**
 * Get information about columns for a table.
 */

import {
  allObjPaths,
  isAssignableTo,
  isSimpleTypeShape,
  isTimestamp,
  nonNullable,
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
  const nonNullableType = nonNullable(propertyType);
  if (isTimestamp(nonNullableType)) {
    return 'timestamp';
  } else if (isSimpleTypeShape(nonNullableType)) {
    return nonNullableType.toString();
  } else if (isAssignableTo(nonNullableType, {type: 'image-file'})) {
    return 'image';
  } else if (isAssignableTo(nonNullableType, {type: 'audio-file'})) {
    return 'audio';
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
