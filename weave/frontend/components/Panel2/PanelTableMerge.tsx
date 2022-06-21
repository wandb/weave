import _ from 'lodash';
import React from 'react';
import {useMemo, useCallback} from 'react';
import * as Panel2 from './panel';
import * as TableType from './PanelTable/tableType';
import * as Types from '@wandb/cg/browser/model/types';
import * as CG from '@wandb/cg/browser/graph';
import * as Op from '@wandb/cg/browser/ops';

import {allObjPaths, PathType} from '@wandb/cg/browser/model/typeHelpers';
import {constBoolean} from '@wandb/cg/browser/ops';
import {useNodeWithServerType} from '@wandb/common/cgreact';
import Loader from '@wandb/common/components/WandbLoader';
import * as ConfigPanel from './ConfigPanel';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, TableType.DataTableLikeType],
  },
};

type PanelTableMergeConfigType = {
  compareMethod?: 'joining' | 'concatenating' | 'none';
  joinKey?: string; // legacy
  outer: boolean;
  joinKeys?: string[];
};
type ProcessedPanelTableMergeConfigType = {
  compareMethod: 'joining' | 'concatenating' | 'none';
  outer: boolean;
  joinKeys: string[];
};

type PanelTableMergeProps = Panel2.PanelProps<
  typeof inputType,
  PanelTableMergeConfigType
>;

const preferredJoinTypes: Types.Type[] = Types.typesWithDigest.concat([
  'id',
] as Types.Type[]);

function pathAsKey(op: PathType) {
  return op.path.join('.');
}

function tablesRowsIsCompare(rowsOrListOfRowsType: Types.Type): boolean {
  const nDims = Types.nDims(rowsOrListOfRowsType);
  if (nDims > 2) {
    throw new Error('Invalid input: dimensionality > 2');
  }
  return nDims === 2;
}

function rowsOrListOfRowsObjType(rowsOrListOfRowsType: Types.Type) {
  let objType: Types.Type = Types.listObjectType(rowsOrListOfRowsType);
  if (Types.isTaggedValue(objType)) {
    objType = objType.value;
  }
  if (Types.isListLike(objType)) {
    objType = Types.listObjectType(objType);
  }
  if (Types.isTaggedValue(objType)) {
    objType = objType.value;
  }
  return objType;
}

function useRowsOrListOfRowsObjType(rowsOrListOfRowsType: Types.Type) {
  return useMemo(() => {
    return rowsOrListOfRowsObjType(rowsOrListOfRowsType);
  }, [rowsOrListOfRowsType]);
}

function getJoinKeys(
  objType: Types.Type,
  usedKeys?: string[]
): {
  allJoinKeys: string[];
  preferredJoinKeys: string[];
  joinableObjPathsMap: {[key: string]: Types.Type};
} {
  let uniqueRowTypes: Types.Type[];
  if (Types.isTypedDict(objType)) {
    uniqueRowTypes = [objType];
  } else if (Types.isUnion(objType)) {
    uniqueRowTypes = objType.members.map(mem =>
      Types.isListLike(mem) ? Types.listObjectType(mem) : mem
    );
  } else {
    // Instead of throwing an error here, return empty values. This occurs
    // because opMap can return a list<none> if the run producing the
    // table key is beyond 25 runs deep.
    return {allJoinKeys: [], preferredJoinKeys: [], joinableObjPathsMap: {}};
  }

  const allJoinableKeyPaths = uniqueRowTypes
    .filter(mem => mem !== 'none')
    .map(mem =>
      Types.isTypedDictLike(mem)
        ? allObjPaths(mem).filter(op => Types.canGroupType(op.type))
        : []
    );
  const filteredJoinableKeyPaths = allJoinableKeyPaths.filter(mem =>
    mem.every(op => !usedKeys?.includes(pathAsKey(op)))
  );
  const preferredJoinKeys =
    usedKeys == null || usedKeys.length === 0
      ? _.intersection(
          ...filteredJoinableKeyPaths.map(joinableKeyPaths =>
            joinableKeyPaths
              .filter(objPath =>
                _.some(
                  preferredJoinTypes.map(t =>
                    Types.isAssignableTo(t, objPath.type)
                  )
                )
              )
              .map(op => pathAsKey(op))
          )
        )
      : [];
  const allJoinKeys = _.union(
    ...filteredJoinableKeyPaths.map(joinableKeyPaths =>
      joinableKeyPaths.map(op => pathAsKey(op))
    )
  );

  const joinableObjPathsMap = _.fromPairs(
    _.flatten(allJoinableKeyPaths).map(op => [pathAsKey(op), op.type])
  );

  return {allJoinKeys, preferredJoinKeys, joinableObjPathsMap};
}

function useJoinKeys(
  objType: Types.Type,
  usedKeys?: string[]
): {
  allJoinKeys: string[];
  preferredJoinKeys: string[];
  joinableObjPathsMap: {[key: string]: Types.Type};
} {
  return useMemo(() => {
    return getJoinKeys(objType, usedKeys);
  }, [objType, usedKeys]);
}

const useFilteredJoinKeys = (
  allJoinKeys: string[],
  joinKeys: string[],
  joinableObjPathsMap: _.Dictionary<Types.Type>
) => {
  return useMemo(() => {
    if (joinKeys.length > 0) {
      return allJoinKeys.filter(jk => {
        return Types.isAssignableTo(
          joinableObjPathsMap[jk],
          joinableObjPathsMap[joinKeys[0]]
        );
      });
    } else {
      return allJoinKeys;
    }
  }, [allJoinKeys, joinKeys, joinableObjPathsMap]);
};

const getProcessedConfig = (
  config: PanelTableMergeConfigType | undefined,
  rowsOrListOfRows: Types.Node
) => {
  const isCompare = tablesRowsIsCompare(rowsOrListOfRows.type);
  const rowsObjType = rowsOrListOfRowsObjType(rowsOrListOfRows.type);
  const {allJoinKeys, preferredJoinKeys, joinableObjPathsMap} =
    getJoinKeys(rowsObjType);
  const canAutoJoin = preferredJoinKeys.length > 0;

  const configCompareMethod = config?.compareMethod;
  const configJoinKeys = config?.joinKeys;
  const configJoinKey = config?.joinKey;
  const configOuter = config?.outer;
  const configIsNull = config?.compareMethod == null;
  let inputMaxLength: number | undefined;
  try {
    inputMaxLength = Types.listMaxLength(rowsOrListOfRows.type);
  } catch (e) {
    // leave undefined
  }

  const processedConfig: ProcessedPanelTableMergeConfigType = {
    compareMethod: configCompareMethod ?? 'concatenating',
    joinKeys: configJoinKeys ?? (configJoinKey != null ? [configJoinKey] : []),
    outer: configOuter ?? true,
  };
  if (
    configIsNull ||
    (isCompare &&
      configCompareMethod === 'none' &&
      (inputMaxLength == null || inputMaxLength > 1)) ||
    (!isCompare && configCompareMethod !== 'none')
  ) {
    // If the config is null, we need to create smart defaults
    if (isCompare) {
      // Default to always concat
      // Keeping the block below in case we want to revert
      // if (canAutoJoin && (inputMaxLength == null || inputMaxLength > 1)) {
      //   processedConfig.compareMethod = 'joining';
      //   processedConfig.joinKeys = [preferredJoinKeys[0]];
      // } else {
      //   processedConfig.compareMethod = 'concatenating';
      // }
      processedConfig.compareMethod = 'concatenating';
    } else {
      processedConfig.compareMethod = 'none';
    }
  } else {
    if (configCompareMethod === 'joining' && isCompare) {
      // walk down the join keys and clear invalid assignments
      for (let i = 0; i < processedConfig.joinKeys.length; i++) {
        const jk = processedConfig.joinKeys[i];
        if (jk != null && !allJoinKeys.includes(jk)) {
          processedConfig.joinKeys = processedConfig.joinKeys.slice(0, i);
          break;
        } else if (i > 0) {
          const currKey = processedConfig.joinKeys[i];
          const prevKey = processedConfig.joinKeys[i - 1];
          if (prevKey == null) {
            processedConfig.joinKeys = processedConfig.joinKeys.slice(0, i);
            break;
          } else if (currKey != null) {
            const prevType = joinableObjPathsMap[prevKey];
            const currType = joinableObjPathsMap[currKey];
            if (!Types.isAssignableTo(currType, prevType)) {
              processedConfig.joinKeys = processedConfig.joinKeys.slice(0, i);
              break;
            }
          }
        }
      }
      if (processedConfig.joinKeys.length === 0 && canAutoJoin) {
        processedConfig.joinKeys = [preferredJoinKeys[0]];
      }
    } else if (configCompareMethod === 'concatenating' || isCompare) {
      processedConfig.compareMethod = 'concatenating';
    } else {
      processedConfig.compareMethod = 'none';
    }
  }
  return processedConfig;
};

const useProcessedConfig = (
  config: PanelTableMergeConfigType | undefined,
  rowsOrListOfRows: Types.Node
): ProcessedPanelTableMergeConfigType => {
  return useMemo(() => {
    return getProcessedConfig(config, rowsOrListOfRows);
  }, [config, rowsOrListOfRows]);
};

const getAggregatedRowsNode = (
  compareMethod: ProcessedPanelTableMergeConfigType['compareMethod'],
  joinKeys: ProcessedPanelTableMergeConfigType['joinKeys'],
  outer: ProcessedPanelTableMergeConfigType['outer'],
  rowsOrListOfRows: Types.Node<Types.ListType>
) => {
  if (compareMethod === 'none') {
    return rowsOrListOfRows;
  } else if (compareMethod === 'concatenating') {
    return Op.opConcat({arr: rowsOrListOfRows as any});
  } else if (joinKeys.length === 0) {
    return CG.voidNode();
  }

  const objType = Types.listObjectType(
    Types.listObjectType(rowsOrListOfRows.type)
  );

  const joinFn = Op.defineFunction({row: objType}, ({row}) => {
    let commonJoinFnNode = Op.opPick({
      obj: row,
      key: Op.constString(joinKeys[0]),
    });

    for (let i = 1; i < joinKeys.length; i++) {
      commonJoinFnNode = Op.opNoneCoalesce({
        lhs: commonJoinFnNode,
        rhs: Op.opPick({
          obj: row,
          key: Op.constString(joinKeys[i]),
        }),
      });
    }

    return commonJoinFnNode;
  });

  return Op.opJoinAll({
    arrs: rowsOrListOfRows as any,
    joinFn: joinFn as any,
    outer: constBoolean(outer),
  });
};

const PanelTableMerge: React.FC<PanelTableMergeProps> = props => {
  throw new Error('PanelTableMerge: Cannot be rendered directly');
};

const PanelTableMergeConfig: React.FC<PanelTableMergeProps> = props => {
  const {input} = props;
  const pathServerType = useNodeWithServerType(input);
  const rowsOrListOfRows = useMemo(
    () =>
      !pathServerType.loading && pathServerType.result.nodeType !== 'void'
        ? TableType.normalizeTableLike(pathServerType.result)
        : CG.voidNode(),
    [pathServerType]
  );
  const resolvedPath = useNodeWithServerType(rowsOrListOfRows);
  const innerProps = useMemo(() => {
    return {
      ...props,
      input: resolvedPath.result,
    };
  }, [props, resolvedPath]);
  if (pathServerType.loading || resolvedPath.loading) {
    return (
      <div style={{width: '100%', height: '100px', position: 'relative'}}>
        <Loader />
      </div>
    );
  } else {
    return <PanelTableMergeConfigInner {...(innerProps as any)} />;
  }
};

const PanelTableMergeConfigInner: React.FC<PanelTableMergeProps> = props => {
  const {input, config, updateConfig} = props;
  const processedConfig = useProcessedConfig(config, input);
  const rowsObjType = useRowsOrListOfRowsObjType(input.type);
  const {allJoinKeys, joinableObjPathsMap} = useJoinKeys(
    rowsObjType,
    processedConfig.joinKeys
  );
  const filteredJoinKeys = useFilteredJoinKeys(
    allJoinKeys,
    processedConfig.joinKeys,
    joinableObjPathsMap
  );
  const altJoinKeys = useMemo(
    () =>
      processedConfig.joinKeys.length > 1
        ? processedConfig.joinKeys.slice(1)
        : [],
    [processedConfig.joinKeys]
  );
  const altJoinKeyOptions = useMemo(
    () => altJoinKeys.concat(filteredJoinKeys),
    [altJoinKeys, filteredJoinKeys]
  );

  const setConfigCompareMethod = useCallback(
    (compareMethod: ProcessedPanelTableMergeConfigType['compareMethod']) => {
      updateConfig({
        ...processedConfig,
        compareMethod,
      });
    },
    [updateConfig, processedConfig]
  );

  const setConfigOuter = useCallback(
    (outer: ProcessedPanelTableMergeConfigType['outer']) => {
      updateConfig({
        ...processedConfig,
        outer,
      });
    },
    [updateConfig, processedConfig]
  );

  const setConfigJoinKeys = useCallback(
    (joinKeys: ProcessedPanelTableMergeConfigType['joinKeys']) => {
      updateConfig({
        ...processedConfig,
        joinKeys,
      });
    },
    [updateConfig, processedConfig]
  );

  return (
    <div
      data-test={
        processedConfig.compareMethod !== 'none'
          ? 'panel-wb-table-compare-header'
          : ''
      }>
      {processedConfig.compareMethod !== 'none' && (
        <ConfigPanel.ConfigOption label="Merge By">
          <ConfigPanel.ModifiedDropdownConfigField
            selection
            data-test="compare_method"
            scrolling
            disabled={
              Object.keys(joinableObjPathsMap).length === 0 &&
              processedConfig.compareMethod === 'concatenating'
            }
            multiple={false}
            options={[
              {
                text: 'Joining',
                value: 'joining',
              },
              {
                text: 'Concatenating',
                value: 'concatenating',
              },
            ]}
            value={processedConfig.compareMethod}
            onChange={(e, data) => {
              setConfigCompareMethod(
                data.value as ProcessedPanelTableMergeConfigType['compareMethod']
              );
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
      {processedConfig.compareMethod === 'joining' && (
        <>
          <ConfigPanel.ConfigOption label="Style">
            <ConfigPanel.ModifiedDropdownConfigField
              selection
              data-test="join_method"
              scrolling
              multiple={false}
              options={[
                {
                  text: 'Outer Join (Union)',
                  value: true,
                },
                {
                  text: 'Inner Join (Intersection)',
                  value: false,
                },
              ]}
              value={processedConfig.outer}
              onChange={(e, data) => {
                setConfigOuter(
                  data.value as ProcessedPanelTableMergeConfigType['outer']
                );
              }}
            />
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label="Key">
            <ConfigPanel.ModifiedDropdownConfigField
              selection
              data-test="join_key"
              scrolling
              multiple={false}
              placeholder="Select a key"
              options={_.keys(joinableObjPathsMap).map(jk => {
                return {
                  text: jk,
                  value: jk,
                };
              })}
              value={processedConfig.joinKeys[0]}
              onChange={(e, data) => {
                setConfigJoinKeys([
                  data.value,
                ] as ProcessedPanelTableMergeConfigType['joinKeys']);
              }}
            />
          </ConfigPanel.ConfigOption>
          {processedConfig.joinKeys.length > 0 && altJoinKeyOptions.length > 0 && (
            <ConfigPanel.ConfigOption label="Alt Keys">
              <ConfigPanel.ModifiedDropdownConfigField
                selection
                data-test="altjoin_key"
                multiple={true}
                value={altJoinKeys}
                options={altJoinKeyOptions.map(jk => {
                  return {
                    text: jk,
                    value: jk,
                  };
                })}
                onChange={(e, data) => {
                  setConfigJoinKeys(
                    [processedConfig.joinKeys[0]].concat(
                      data.value as ProcessedPanelTableMergeConfigType['joinKeys']
                    )
                  );
                }}
              />
            </ConfigPanel.ConfigOption>
          )}
        </>
      )}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'merge',
  displayName: 'Merge Tables',
  Component: PanelTableMerge,
  ConfigComponent: PanelTableMergeConfig,
  inputType,
  outputType: () => ({
    type: 'list' as const,
    objectType: {
      type: 'typedDict',
      propertyTypes: {},
    },
  }),
  equivalentTransform: async (inputNode, config, refineType) => {
    const castedNode: Types.Node = inputNode as any;
    const refinedNode = await refineType(castedNode);
    const normalizedNode = Op.opDropNa({
      arr: TableType.normalizeTableLike(refinedNode),
    });
    const refinedNormalizedNode = await refineType(normalizedNode);
    const processedConfig = getProcessedConfig(config, refinedNormalizedNode);
    const res = getAggregatedRowsNode(
      processedConfig.compareMethod,
      processedConfig.joinKeys,
      processedConfig.outer,
      refinedNormalizedNode as Types.Node<Types.ListType>
    );
    return res;
  },
};

Panel2.registerPanelFunction(
  Spec.id,
  Spec.inputType,
  Spec.equivalentTransform!
);
