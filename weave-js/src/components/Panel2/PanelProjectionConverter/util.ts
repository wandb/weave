import {
  allObjPaths,
  isAssignableTo,
  list,
  listObjectType,
  Node,
  nonNullable,
  nullableTaggableValue,
  Type,
  typedDict,
} from '@wandb/weave/core';
import * as _ from 'lodash';

import * as PTypes from './types';

export const getValidColumns = (inputType: Type) => {
  const innerType = nullableTaggableValue(listObjectType(inputType));
  let validEmbeddingColumns: string[] = [];
  let validNumericColumns: string[] = [];
  if (isAssignableTo(innerType, typedDict({}))) {
    const allPaths = allObjPaths(innerType);

    validEmbeddingColumns = allPaths
      .filter(path => isAssignableTo(nonNullable(path.type), list('number')))
      .map(path => path.path.join('.'));
    validNumericColumns = allPaths
      .filter(path => isAssignableTo(nonNullable(path.type), 'number'))
      .map(path => path.path.join('.'));
  }
  return {
    validEmbeddingColumns,
    validNumericColumns,
  };
};

export const processConfig: <U extends Type>(
  config: any,
  inputNode: Node<U>
) => PTypes.PanelProjectionConverterConfigType = (
  config,
  inputNode
): PTypes.PanelProjectionConverterConfigType => {
  const {validEmbeddingColumns, validNumericColumns} = getValidColumns(
    inputNode.type
  );
  const projectionAlgorithm = config?.projectionAlgorithm ?? 'pca';
  const inputCardinality =
    config?.inputCardinality ??
    (validEmbeddingColumns.length > 0 ? 'single' : 'multiple');

  let inputColumnNames = config?.inputColumnNames ?? [];
  if (inputCardinality === 'single') {
    if (
      inputColumnNames.length >= 1 &&
      validEmbeddingColumns.indexOf(inputColumnNames[0]) === -1
    ) {
      inputColumnNames = [];
    }
    if (inputColumnNames.length === 0 && validEmbeddingColumns.length > 0) {
      inputColumnNames = [validEmbeddingColumns[0]];
    }
  } else {
    if (
      inputColumnNames.length > 0 &&
      _.some(inputColumnNames, name => validNumericColumns.indexOf(name) === -1)
    ) {
      inputColumnNames = [];
    }
    if (inputColumnNames.length === 0 && validNumericColumns.length > 0) {
      inputColumnNames = validNumericColumns;
    }
  }
  return {
    projectionAlgorithm,
    inputCardinality,
    inputColumnNames,
    algorithmOptions: {
      pca: {},
      tsne: {
        perplexity: config?.algorithmOptions?.tsne?.perplexity ?? 30,
        learningRate: config?.algorithmOptions?.tsne?.learningRate ?? 10,
        iterations: config?.algorithmOptions?.tsne?.iterations ?? 25,
      },
      umap: {
        neighbors: config?.algorithmOptions?.umap?.neighbors ?? 15,
        minDist: config?.algorithmOptions?.umap?.minDist ?? 0.1,
        spread: config?.algorithmOptions?.umap?.spread ?? 1.0,
      },
    },
  };
};
