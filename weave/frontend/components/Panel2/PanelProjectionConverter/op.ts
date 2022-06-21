import * as Panel2 from '../panel';
import * as Types from '@wandb/cg/browser/model/types';
import * as Op from '@wandb/cg/browser/ops';
import * as TableType from '../PanelTable/tableType';
import * as PUtil from './util';

export const outputType: Panel2.PanelSpec['outputType'] = inType => {
  let sourceType: Types.Type = inType;
  if (TableType.isTableTypeLike(inType)) {
    sourceType = Types.list(Types.typedDict({}));
  }
  return Types.list(
    Types.typedDict({
      source: Types.listObjectType(sourceType),
      projection: Types.list('number'),
    }),
    Types.listMinLength(sourceType),
    Types.listMaxLength(sourceType)
  );
};

export const equivalentTransform: Panel2.PanelSpec['equivalentTransform'] =
  async (inputNode, config, refineType) => {
    let castedNode: Types.Node = inputNode as any;
    if (TableType.isTableTypeLike(inputNode.type)) {
      castedNode = await refineType(castedNode);
      castedNode = TableType.normalizeTableLike(castedNode);
      castedNode = await refineType(castedNode);
    }
    if (
      !Types.isListLike(castedNode.type) ||
      !Types.isTypedDictLike(Types.listObjectType(castedNode.type))
    ) {
      return Op.constNodeUnsafe(
        Types.list(
          Types.typedDict({
            projection: Types.typedDict({
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
    return Op.opTable2DProjection({
      table: castedNode,
      projectionAlgorithm: Op.constString(pConfig.projectionAlgorithm),
      inputCardinality: Op.constString(pConfig.inputCardinality),
      inputColumnNames: Op.constStringList(pConfig.inputColumnNames),
      algorithmOptions: Op.constNodeUnsafe(
        Types.typedDict({
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
