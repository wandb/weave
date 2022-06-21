import * as _ from 'lodash';
import * as PTypes from './types';
import * as Types from '@wandb/cg/browser/model/types';
import {allObjPaths} from '@wandb/cg/browser/model/typeHelpers';
export const getValidColumns = (inputType: Types.Type) => {
  const innerType = Types.nullableTaggableValue(
    Types.listObjectType(inputType)
  );
  let validEmbeddingColumns: string[] = [];
  let validNumericColumns: string[] = [];
  if (Types.isAssignableTo(innerType, Types.typedDict({}))) {
    const allPaths = allObjPaths(innerType);

    validEmbeddingColumns = allPaths
      .filter(path =>
        Types.isAssignableTo(path.type, Types.maybe(Types.list('number')))
      )
      .map(path => path.path.join('.'));
    validNumericColumns = allPaths
      .filter(path => Types.isAssignableTo(path.type, Types.maybe('number')))
      .map(path => path.path.join('.'));
  }
  return {
    validEmbeddingColumns,
    validNumericColumns,
  };
};

export const processConfig: <U extends Types.Type>(
  config: any,
  inputNode: Types.Node<U>
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
