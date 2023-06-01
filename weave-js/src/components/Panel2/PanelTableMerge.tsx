import Loader from '@wandb/weave/common/components/WandbLoader';
import {
  allObjPaths,
  canGroupType,
  constBoolean,
  constFunction,
  constNodeUnsafe,
  constString,
  isAssignableTo,
  isListLike,
  isTaggedValue,
  isTypedDict,
  isTypedDictLike,
  isUnion,
  list,
  listMaxLength,
  listObjectType,
  ListType,
  maybe,
  nDims,
  Node,
  opConcat,
  opDropNa,
  opJoinAll,
  opNoneCoalesce,
  opPick,
  PathType,
  Type,
  typedDict,
  TYPES_WITH_DIGEST,
  union,
  voidNode,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {useNodeWithServerType} from '../../react';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import * as TableType from './PanelTable/tableType';

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

const preferredJoinTypes: Type[] = TYPES_WITH_DIGEST.concat(['id'] as Type[]);

function pathAsKey(op: PathType) {
  return op.path.join('.');
}

function tablesRowsIsCompare(rowsOrListOfRowsType: Type): boolean {
  const dims = nDims(rowsOrListOfRowsType);
  if (dims > 2) {
    throw new Error('Invalid input: dimensionality > 2');
  }
  return dims === 2;
}

function rowsOrListOfRowsObjType(rowsOrListOfRowsType: Type) {
  let objType: Type = listObjectType(rowsOrListOfRowsType);
  if (isTaggedValue(objType)) {
    objType = objType.value;
  }
  if (isListLike(objType)) {
    objType = listObjectType(objType);
  }
  if (isTaggedValue(objType)) {
    objType = objType.value;
  }
  return objType;
}

function useRowsOrListOfRowsObjType(rowsOrListOfRowsType: Type) {
  return useMemo(() => {
    return rowsOrListOfRowsObjType(rowsOrListOfRowsType);
  }, [rowsOrListOfRowsType]);
}

function getJoinKeys(
  objType: Type,
  usedKeys?: string[]
): {
  allJoinKeys: string[];
  preferredJoinKeys: string[];
  joinableObjPathsMap: {[key: string]: Type};
} {
  let uniqueRowTypes: Type[];
  if (isTypedDict(objType)) {
    uniqueRowTypes = [objType];
  } else if (isUnion(objType)) {
    uniqueRowTypes = objType.members.map(mem =>
      isListLike(mem) ? listObjectType(mem) : mem
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
      isTypedDictLike(mem)
        ? allObjPaths(mem).filter(op => canGroupType(op.type))
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
                  preferredJoinTypes.map(
                    t =>
                      isAssignableTo(t, objPath.type) ||
                      // This condition is a relic of the past. In Weave0, we assume any column with the name `id` is an `id` type.
                      // We did not do this with Weave1. So this is a small stopgap to make sure that we don't break existing
                      // and continue to auto-join on string/number columns that are called id.
                      (objPath.path.join('') === 'id' &&
                        isAssignableTo(
                          objPath.type,
                          maybe(union(['string', 'number']))
                        ))
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
  objType: Type,
  usedKeys?: string[]
): {
  allJoinKeys: string[];
  preferredJoinKeys: string[];
  joinableObjPathsMap: {[key: string]: Type};
} {
  return useMemo(() => {
    return getJoinKeys(objType, usedKeys);
  }, [objType, usedKeys]);
}

const useFilteredJoinKeys = (
  allJoinKeys: string[],
  joinKeys: string[],
  joinableObjPathsMap: _.Dictionary<Type>
) => {
  return useMemo(() => {
    if (joinKeys.length > 0) {
      return allJoinKeys.filter(jk => {
        return isAssignableTo(
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
  rowsOrListOfRows: Node
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
    inputMaxLength = listMaxLength(rowsOrListOfRows.type);
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
            if (!isAssignableTo(currType, prevType)) {
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
  rowsOrListOfRows: Node
): ProcessedPanelTableMergeConfigType => {
  return useMemo(() => {
    return getProcessedConfig(config, rowsOrListOfRows);
  }, [config, rowsOrListOfRows]);
};

const getAggregatedRowsNode = (
  compareMethod: ProcessedPanelTableMergeConfigType['compareMethod'],
  joinKeys: ProcessedPanelTableMergeConfigType['joinKeys'],
  outer: ProcessedPanelTableMergeConfigType['outer'],
  rowsOrListOfRows: Node<ListType>
) => {
  if (compareMethod === 'none') {
    return rowsOrListOfRows;
  } else if (compareMethod === 'concatenating') {
    return opConcat({arr: rowsOrListOfRows as any});
  } else if (joinKeys.length === 0) {
    return voidNode();
  }

  const objType = listObjectType(listObjectType(rowsOrListOfRows.type));

  const joinFn = constFunction({row: objType}, ({row}) => {
    let commonJoinFnNode = opPick({
      obj: row,
      key: constString(joinKeys[0]),
    });

    for (let i = 1; i < joinKeys.length; i++) {
      commonJoinFnNode = opNoneCoalesce({
        lhs: commonJoinFnNode,
        rhs: opPick({
          obj: row,
          key: constString(joinKeys[i]),
        }),
      });
    }

    return commonJoinFnNode;
  });

  return opJoinAll({
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
        : voidNode(),
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
        <Loader name="panel-table-merge-loader" />
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
        <ConfigPanel.ConfigOption label="Combine By">
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
                text: 'Joining Rows...',
                value: 'joining',
              },
              {
                text: 'Concatenating Rows',
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
          {processedConfig.joinKeys.length > 0 &&
            altJoinKeyOptions.length > 0 && (
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
  displayName: 'Combined Table',
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
    const expectedReturnType = list(typedDict({}));
    const defaultNode = constNodeUnsafe(expectedReturnType, []);
    const castedNode: Node = inputNode as any;
    const refinedNode = await refineType(castedNode);
    const arrNode = TableType.normalizeTableLike(refinedNode);
    const normalizedNode = opDropNa({
      arr: arrNode,
    });
    const refinedNormalizedNode = await refineType(normalizedNode);
    const processedConfig = getProcessedConfig(config, refinedNormalizedNode);
    const res = getAggregatedRowsNode(
      processedConfig.compareMethod,
      processedConfig.joinKeys,
      processedConfig.outer,
      refinedNormalizedNode as Node<ListType>
    );
    // In cases where the resolved type is not assignable to our expected return
    // type, we return the default node instead. The primary case where this
    // happens is when the input list is empty, then the resolved type ends up
    // being a list<none> which does not conform to the output contract
    if (isAssignableTo(res.type, expectedReturnType)) {
      return res;
    }
    return defaultNode;
  },
};

Panel2.registerPanelFunction(
  Spec.id,
  Spec.inputType,
  Spec.equivalentTransform!
);
