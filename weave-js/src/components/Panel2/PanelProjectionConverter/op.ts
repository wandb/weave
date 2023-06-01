import {
  constNodeUnsafe,
  constString,
  constStringList,
  isListLike,
  isTypedDictLike,
  list,
  listMaxLength,
  listMinLength,
  listObjectType,
  Node,
  opTable2DProjection,
  Type,
  typedDict,
} from '@wandb/weave/core';

import * as Panel2 from '../panel';
import * as TableType from '../PanelTable/tableType';
import * as PUtil from './util';

export const outputType: Panel2.PanelSpec['outputType'] = inType => {
  let sourceType: Type = inType;
  if (TableType.isTableTypeLike(inType)) {
    sourceType = list(typedDict({}));
  }
  return list(
    typedDict({
      source: listObjectType(sourceType),
      projection: list('number'),
    }),
    listMinLength(sourceType),
    listMaxLength(sourceType)
  );
};

export const equivalentTransform: Panel2.PanelSpec['equivalentTransform'] =
  async (inputNode, config, refineType) => {
    let castedNode: Node = inputNode as any;
    if (TableType.isTableTypeLike(inputNode.type)) {
      castedNode = await refineType(castedNode);
      castedNode = TableType.normalizeTableLike(castedNode);
      castedNode = await refineType(castedNode);
    }
    // In cases where the resolved type is not assignable to our expected return
    // type, we return the default node instead. The primary case where this
    // happens is when the input list is empty, then the resolved type ends up
    // being a list<none> which does not conform to the output contract
    if (
      !isListLike(castedNode.type) ||
      !isTypedDictLike(listObjectType(castedNode.type))
    ) {
      return constNodeUnsafe(
        list(
          typedDict({
            projection: typedDict({
              x: 'number',
              y: 'number',
            }),
            source: 'none',
          })
        ),
        []
      );
    }
    const pConfig = PUtil.processConfig(config, castedNode as any);
    return opTable2DProjection({
      table: castedNode,
      projectionAlgorithm: constString(pConfig.projectionAlgorithm),
      inputCardinality: constString(pConfig.inputCardinality),
      inputColumnNames: constStringList(pConfig.inputColumnNames),
      algorithmOptions: constNodeUnsafe(
        typedDict({
          tsne: {
            type: 'typedDict' as const,
            propertyTypes: {
              perplexity: 'number',
              learningRate: 'number',
              iterations: 'number',
            },
          },
          pca: {type: 'typedDict' as const, propertyTypes: {}},
          umap: {
            type: 'typedDict' as const,
            propertyTypes: {
              neighbors: 'number',
              minDist: 'number',
              spread: 'number',
            },
          },
        }),
        pConfig.algorithmOptions
      ),
    });
  };
