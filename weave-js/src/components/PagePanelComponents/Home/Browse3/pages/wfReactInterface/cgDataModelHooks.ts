/**
 * This file defines `cgWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Compute Graph" (StreamTable) engine.
 */

import _ from 'lodash';
import {useCallback, useEffect, useMemo, useState} from 'react';

import {useWeaveContext} from '../../../../../../context';
import {
  callOpVeryUnsafe,
  constBoolean,
  constFunction,
  constNumber,
  constString,
  listObjectType,
  Node,
  opAnd,
  opArray,
  opArtifactLastMembership,
  opArtifactMembershipArtifactVersion,
  opArtifactName,
  opArtifactTypeArtifacts,
  opArtifactVersionArtifactSequence,
  opArtifactVersionCreatedAt,
  opArtifactVersionFile,
  opArtifactVersionHash,
  opArtifactVersionIsWeaveObject,
  opArtifactVersionMetadata,
  opArtifactVersions,
  opArtifactVersionVersionId,
  opDict,
  opFileContents,
  opFilter,
  opFlatten,
  opGet,
  opIsNone,
  opJoin,
  opLimit,
  opMap,
  opPick,
  opProjectArtifact,
  opProjectArtifactTypes,
  opProjectArtifactVersion,
  opRootProject,
  opStringEqual,
  OutputNode,
  Type,
  typedDict,
} from '../../../../../../core';
import {useDeepMemo} from '../../../../../../hookUtils';
import {
  isWandbArtifactRef,
  parseRef,
  useNodeValue,
  WandbArtifactRef,
} from '../../../../../../react';
import {WeaveApp} from '../../../../../../weave';
import {fnRunsNode, useRuns} from '../../../Browse2/callTreeHooks';
import {
  mutationAppend,
  mutationPublishArtifact,
  mutationSet,
  nodeToEasyNode,
  weaveGet,
} from '../../../Browse2/easyWeave';
import {
  callCache,
  objectVersionCache,
  opVersionCache,
  refDataCache,
  refTypedNodeCache,
} from './cache';
import {
  AWL_COL_EDGE_NAME,
  AWL_ROW_EDGE_NAME,
  DICT_KEY_EDGE_NAME,
  LIST_INDEX_EDGE_NAME,
  OBJECT_ATTR_EDGE_NAME,
  PROJECT_CALL_STREAM_NAME,
  WANDB_ARTIFACT_REF_PREFIX,
} from './constants';
import {
  opNameToCategory,
  refUriToOpVersionKey,
  typeNameToCategory,
} from './utilities';
import {
  CallFilter,
  CallKey,
  CallSchema,
  Loadable,
  LoadableWithError,
  ObjectVersionFilter,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionFilter,
  OpVersionKey,
  OpVersionSchema,
  RawSpanFromStreamTableEra,
  RawSpanFromStreamTableEraWithFeedback,
  RefMutation,
  TableQuery,
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  const cachedCall = key ? callCache.get(key) : null;
  const calls = useRuns(
    {
      entityName: key?.entity ?? '',
      projectName: key?.project ?? '',
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      callIds: [key?.callId ?? ''],
    },
    {skip: key == null || cachedCall != null}
  );

  return useMemo(() => {
    if (key == null) {
      return {
        loading: false,
        result: null,
      };
    }
    if (cachedCall != null) {
      return {
        loading: false,
        result: cachedCall,
      };
    }
    const callResult = calls.result?.[0] ?? null;
    const result = callResult
      ? spanToCallSchema(key.entity, key.project, callResult)
      : null;
    if (calls.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      if (result) {
        callCache.set(key, result);
      }
      return {
        loading: false,
        result,
      };
    }
  }, [cachedCall, calls.loading, calls.result, key]);
};

const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<CallSchema[]> => {
  let runsNode = fnRunsNode(
    {
      entityName: entity,
      projectName: project,
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      opUris: filter.opVersionRefs,
      inputUris: filter.inputObjectVersionRefs,
      outputUris: filter.outputObjectVersionRefs,
      traceId: filter.traceId,
      parentIds: filter.parentIds,
      traceRootsOnly: filter.traceRootsOnly,
      callIds: filter.callIds,
    }
  );
  if (limit) {
    runsNode = opLimit({arr: runsNode, limit: constNumber(limit)});
  }
  const calls = useNodeValue(runsNode, {skip: opts?.skip});

  return useMemo(() => {
    const callsResult: RawSpanFromStreamTableEra[] = calls.result ?? [];
    // This `uniqBy` fixes gorilla duplication bug.
    const allResults = _.uniqBy(
      callsResult.map(run => spanToCallSchema(entity, project, run)),
      'callId'
    );
    // Unfortunately, we can't filter by category in the query level yet
    const result = allResults;

    if (calls.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      allResults.forEach(call => {
        callCache.set(
          {
            entity,
            project,
            callId: call.callId,
          },
          call
        );
      });
      return {
        loading: false,
        result,
      };
    }
  }, [calls.result, calls.loading, entity, project]);
};

const useOpVersion = (
  // Null value skips
  key: OpVersionKey | null
): Loadable<OpVersionSchema | null> => {
  const cachedOpVersion = key ? opVersionCache.get(key) : null;
  const artifactVersionNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key?.entity ?? ''),
      project: constString(key?.project ?? ''),
    }),
    artifactName: constString(key?.opId ?? ''),
    artifactVersionAlias: constString(key?.versionHash ?? ''),
  });
  const dataNode = artifactVersionNodeToOpVersionDictNode(
    artifactVersionNode as any
  );
  const dataValue = useNodeValue(dataNode, {
    skip: key == null || cachedOpVersion != null,
  });
  return useMemo(() => {
    if (key == null) {
      return {
        loading: false,
        result: null,
      };
    } else if (cachedOpVersion != null) {
      return {
        loading: false,
        result: cachedOpVersion,
      };
    }
    const result =
      dataValue.result == null || dataValue.result.missing
        ? null
        : {
            ...key,
            versionIndex: dataValue.result.versionIndex as number,
            category: opNameToCategory(key.opId as string),
            createdAtMs: dataValue.result.createdAtMs as number,
          };
    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      if (result) {
        opVersionCache.set(key, result);
      }
      return {
        loading: false,
        result,
      };
    }
  }, [cachedOpVersion, dataValue.loading, dataValue.result, key]);
};

const useOpVersions = (
  entity: string,
  project: string,
  filter: OpVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): LoadableWithError<OpVersionSchema[]> => {
  let dataNode = useOpVersionsNode(entity, project, filter);
  if (limit) {
    dataNode = opLimit({arr: dataNode, limit: constNumber(limit)});
  }

  const dataValue = useNodeValue(dataNode, {skip: opts?.skip});

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        error: null,
        result: [],
      };
    }
    const result = (dataValue.result ?? []).map((row: any) => ({
      entity,
      project,
      opId: row.opId as string,
      versionHash: row.versionHash as string,
      path: 'obj',
      refExtra: null,
      versionIndex: row.dataDict.versionIndex as number,
      typeName: row.dataDict.typeName as string,
      category: opNameToCategory(row.opId as string),
      createdAtMs: row.dataDict.createdAtMs as number,
    })) as OpVersionSchema[];

    if (dataValue.loading) {
      return {
        loading: true,
        error: null,
        result,
      };
    } else {
      result.forEach(op => {
        opVersionCache.set(
          {
            entity,
            project,
            opId: op.opId,
            versionHash: op.versionHash,
          },
          op
        );
      });
      return {
        loading: false,
        error: null,
        result,
      };
    }
  }, [dataValue.loading, dataValue.result, entity, opts?.skip, project]);
};

const useObjectVersion = (
  // Null value skips
  key: ObjectVersionKey | null
): Loadable<ObjectVersionSchema | null> => {
  const cachedObjectVersion = key ? objectVersionCache.get(key) : null;
  const artifactVersionNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key?.entity ?? ''),
      project: constString(key?.project ?? ''),
    }),
    artifactName: constString(key?.objectId ?? ''),
    artifactVersionAlias: constString(key?.versionHash ?? ''),
  });
  const dataNode = artifactVersionNodeToObjectVersionDictNode(
    artifactVersionNode as any
  );
  const dataValue = useNodeValue(dataNode, {
    skip: key == null || cachedObjectVersion != null,
  });

  return useMemo(() => {
    if (key == null) {
      return {
        loading: false,
        result: null,
      };
    }
    if (cachedObjectVersion != null) {
      return {
        loading: false,
        result: cachedObjectVersion,
      };
    }
    const result =
      dataValue.result == null || dataValue.result.missing
        ? null
        : {
            ...key,
            versionIndex: dataValue.result.versionIndex as number,
            typeName: dataValue.result.typeName as string,
            baseObjectClass: null,
            createdAtMs: dataValue.result.createdAtMs as number,
            val: null,
          };
    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      if (result) {
        objectVersionCache.set(key, result);
      }
      return {
        loading: false,
        result,
      };
    }
  }, [cachedObjectVersion, dataValue.loading, dataValue.result, key]);
};

const useRootObjectVersions = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): LoadableWithError<ObjectVersionSchema[]> => {
  let dataNode = useRootObjectVersionsNode(entity, project, filter);
  if (limit) {
    dataNode = opLimit({arr: dataNode, limit: constNumber(limit)});
  }
  const dataValue = useNodeValue(dataNode, {skip: opts?.skip});

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        error: null,
        result: [],
      };
    }
    const result = (dataValue.result ?? [])
      .map((row: any) => ({
        entity,
        project,
        objectId: row.objectId as string,
        versionHash: row.versionHash as string,
        path: 'obj',
        refExtra: null,
        versionIndex: row.dataDict.versionIndex as number,
        typeName: row.dataDict.typeName as string,
        category: typeNameToCategory(row.dataDict.typeName as string),
        createdAtMs: row.dataDict.createdAtMs as number,
      }))
      .filter((row: any) => {
        return (
          filter.baseObjectClasses == null ||
          filter.baseObjectClasses.includes(row.category)
        );
      })
      // TODO: Move this to the weave filters?
      .filter((row: any) => {
        return !['OpDef', 'stream_table', 'type'].includes(row.typeName);
      }) as ObjectVersionSchema[];

    if (dataValue.loading) {
      return {
        loading: true,
        error: null,
        result,
      };
    } else {
      result.forEach(obj => {
        objectVersionCache.set(
          {
            scheme: 'wandb-artifact',
            entity,
            project,
            objectId: obj.objectId,
            versionHash: obj.versionHash,
            path: obj.path,
            refExtra: obj.refExtra,
          },
          obj
        );
      });
      return {
        loading: false,
        error: null,
        result,
      };
    }
  }, [
    dataValue.loading,
    dataValue.result,
    entity,
    filter.baseObjectClasses,
    opts?.skip,
    project,
  ]);
};

const useChildCallsForCompare = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): {
  loading: boolean;
  result: CallSchema[];
} => {
  const parentRunsNode = selectedObjectVersionRef
    ? callsNode(entity, project, {
        callIds: parentCallIds,
        inputObjectVersionRefs: [selectedObjectVersionRef],
      })
    : opArray({} as any);
  const childRunsNode = selectedOpVersionRef
    ? callsNode(entity, project, {
        opVersionRefs: [selectedOpVersionRef],
      })
    : opArray({} as any);
  const joinedRuns = opJoin({
    arr1: parentRunsNode,
    arr2: childRunsNode,
    join1Fn: constFunction({row: typedDict({span_id: 'string'})}, ({row}) => {
      return opPick({obj: row, key: constString('span_id')});
    }) as any,
    join2Fn: constFunction({row: typedDict({parent_id: 'string'})}, ({row}) => {
      return opPick({obj: row, key: constString('parent_id')});
    }) as any,
    alias1: constString('parent'),
    alias2: constString('child'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(false),
  });
  const nodeValue = useNodeValue(joinedRuns, {
    skip: !selectedObjectVersionRef || !selectedOpVersionRef,
  });
  return useMemo(() => {
    return {
      loading: nodeValue.loading,
      result: (nodeValue.result ?? []).map((row: any) =>
        spanToCallSchema(entity, project, row.child)
      ),
    };
  }, [entity, nodeValue.loading, nodeValue.result, project]);
};

// Helpers //

const callsNode = (
  entity: string,
  project: string,
  filter: CallFilter
): Node => {
  return fnRunsNode(
    {
      entityName: entity,
      projectName: project,
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      opUris: filter.opVersionRefs,
      inputUris: filter.inputObjectVersionRefs,
      outputUris: filter.outputObjectVersionRefs,
      traceId: filter.traceId,
      parentIds: filter.parentIds,
      traceRootsOnly: filter.traceRootsOnly,
      callIds: filter.callIds,
    }
  );
};

const artifactVersionNodeToOpVersionDictNode = (
  artifactVersionNode: Node<'artifactVersion'>
) => {
  const versionIndexNode = opArtifactVersionVersionId({
    artifactVersion: artifactVersionNode,
  });
  const createdAtNode = opArtifactVersionCreatedAt({
    artifactVersion: artifactVersionNode,
  });
  return opDict({
    missing: opIsNone({val: artifactVersionNode}),
    versionIndex: versionIndexNode,
    createdAtMs: createdAtNode,
  } as any);
};

const artifactVersionNodeToObjectVersionDictNode = (
  artifactVersionNode: Node<'artifactVersion'>
) => {
  const versionIndexNode = opArtifactVersionVersionId({
    artifactVersion: artifactVersionNode,
  });
  const metadataNode = opArtifactVersionMetadata({
    artifactVersion: artifactVersionNode,
  });
  const typeNameNode = opPick({
    obj: metadataNode,
    key: constString('_weave_meta.type_name'),
  });
  const createdAtNode = opArtifactVersionCreatedAt({
    artifactVersion: artifactVersionNode,
  });
  return opDict({
    missing: opIsNone({val: artifactVersionNode}),
    typeName: typeNameNode,
    versionIndex: versionIndexNode,
    createdAtMs: createdAtNode,
  } as any);
};

const useRootObjectVersionsNode = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter,
  opts?: {skip?: boolean}
): Node => {
  const projectNode = opRootProject({
    entityName: constString(entity),
    projectName: constString(project),
  });
  let artifactsNode = opArray({} as any);

  if (filter.objectIds == null) {
    artifactsNode = opFlatten({
      arr: opArtifactTypeArtifacts({
        artifactType: opProjectArtifactTypes({
          project: projectNode,
        }),
      }) as any,
    });
  } else {
    artifactsNode = opArray(
      _.fromPairs(
        filter.objectIds.map(objId => {
          return [
            objId,
            opProjectArtifact({
              project: projectNode,
              artifactName: constString(objId),
            }),
          ];
        })
      ) as any
    );
  }

  let artifactVersionsNode = opArray({} as any);
  if (filter.latestOnly) {
    artifactVersionsNode = opArtifactMembershipArtifactVersion({
      artifactMembership: opArtifactLastMembership({
        artifact: artifactsNode,
      }),
    }) as any;
  } else {
    artifactVersionsNode = opFlatten({
      arr: opArtifactVersions({
        artifact: artifactsNode,
      }) as any,
    });
  }

  // Filter to only Weave Objects
  const weaveObjectsNode = opFilter({
    arr: artifactVersionsNode,
    filterFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return opArtifactVersionIsWeaveObject({artifactVersion: row});
    }),
  });

  // Build Keys
  const dataNode = opMap({
    arr: weaveObjectsNode,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return opDict({
        objectId: opArtifactName({
          artifact: opArtifactVersionArtifactSequence({artifactVersion: row}),
        }),
        versionHash: opArtifactVersionHash({artifactVersion: row}),
        dataDict: artifactVersionNodeToObjectVersionDictNode(row as any),
      } as any);
    }),
  });

  return dataNode;
};

const useOpVersionsNode = (
  entity: string,
  project: string,
  filter: OpVersionFilter,
  opts?: {skip?: boolean}
): Node => {
  const projectNode = opRootProject({
    entityName: constString(entity),
    projectName: constString(project),
  });
  let artifactsNode = opArray({} as any);

  if (filter.opIds == null) {
    artifactsNode = opFlatten({
      arr: opArtifactTypeArtifacts({
        artifactType: opProjectArtifactTypes({
          project: projectNode,
        }),
      }) as any,
    });
  } else {
    artifactsNode = opArray(
      _.fromPairs(
        filter.opIds.map(opId => {
          return [
            opId,
            opProjectArtifact({
              project: projectNode,
              artifactName: constString(opId),
            }),
          ];
        })
      ) as any
    );
  }

  let artifactVersionsNode = opArray({} as any);
  if (filter.latestOnly) {
    artifactVersionsNode = opArtifactMembershipArtifactVersion({
      artifactMembership: opArtifactLastMembership({
        artifact: artifactsNode,
      }),
    }) as any;
  } else {
    artifactVersionsNode = opFlatten({
      arr: opArtifactVersions({
        artifact: artifactsNode,
      }) as any,
    });
  }

  // Filter to only Weave Objects
  const weaveObjectsNode = opFilter({
    arr: artifactVersionsNode,
    filterFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return opAnd({
        lhs: opArtifactVersionIsWeaveObject({artifactVersion: row}),
        rhs: opStringEqual({
          lhs: opPick({
            obj: opArtifactVersionMetadata({
              artifactVersion: row,
            }),
            key: constString('_weave_meta.type_name'),
          }),
          rhs: constString('OpDef'),
        }),
      });
    }),
  });

  // Build Keys
  const dataNode = opMap({
    arr: weaveObjectsNode,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return opDict({
        opId: opArtifactName({
          artifact: opArtifactVersionArtifactSequence({artifactVersion: row}),
        }),
        versionHash: opArtifactVersionHash({artifactVersion: row}),
        dataDict: artifactVersionNodeToOpVersionDictNode(row as any),
      } as any);
    }),
  });

  return dataNode;
};

const applyTableQuery = (node: Node, tableQuery: TableQuery): Node => {
  if ((tableQuery.columns ?? []).length > 0) {
    node = opMap({
      arr: node,
      mapFn: constFunction({row: listObjectType(node.type)}, ({row}) =>
        opDict(
          _.fromPairs(
            (tableQuery.columns ?? []).map(key => [
              key,
              opPick({obj: row, key: constString(key)}),
            ])
          ) as any
        )
      ),
    });
  }
  if (tableQuery.limit) {
    node = opLimit({
      arr: node,
      limit: constNumber(tableQuery.limit),
    });
  }
  return node;
};

const getCachedRefData = async (
  weave: WeaveApp,
  uri: string,
  tableQuery?: TableQuery
): Promise<any> => {
  const key = uri + (tableQuery ? '?query=' + JSON.stringify(tableQuery) : '');
  const cacheRes = refDataCache.get(key);
  if (cacheRes != null) {
    return cacheRes;
  }
  let node = await getCachedRefToTypedNode(weave, uri);
  if (tableQuery) {
    node = applyTableQuery(node, tableQuery);
  }
  const res = await weave.client.query(node);
  refDataCache.set(key, res);
  return res;
};

const useRefsData = (
  refUris: string[],
  tableQuery?: TableQuery
): Loadable<any[]> => {
  const refUrisDeep = useDeepMemo(refUris);
  const tableQueryDeep = useDeepMemo(tableQuery);
  const weave = useWeaveContext();
  const [refData, setRefData] = useState<any[]>();
  useEffect(() => {
    let isMounted = true;
    const updateRefData = async () => {
      const uris = [...refUrisDeep];
      const data = await Promise.allSettled(
        uris.map(uri => getCachedRefData(weave, uri, tableQueryDeep))
      );
      if (!isMounted || !_.isEqual(uris, refUrisDeep)) {
        return;
      }

      setRefData(
        data.map(d => {
          if (d.status === 'fulfilled') {
            return d.value;
          } else {
            return null;
          }
        })
      );
    };
    updateRefData();
    return () => {
      isMounted = false;
    };
  }, [refUrisDeep, tableQueryDeep, weave]);

  return useMemo(
    () => ({
      loading: refData == null,
      result: refData ?? [],
    }),
    [refData]
  );
};

const useApplyMutationsToRef = (): ((
  refUri: string,
  mutations: RefMutation[]
) => Promise<string>) => {
  const weave = useWeaveContext();
  const applyMutationsToRef = useCallback(
    async (refUri: string, mutations: RefMutation[]): Promise<string> => {
      let workingRootNode = await getCachedRefToTypedNode(weave, refUri);
      const rootObjectRef = parseRef(refUri) as WandbArtifactRef;
      for (const edit of mutations) {
        let targetNode = nodeToEasyNode(workingRootNode as OutputNode);
        if (edit.type === 'set') {
          for (const pathEl of edit.path) {
            if (pathEl.type === 'getattr') {
              targetNode = targetNode.getAttr(pathEl.key);
            } else if (pathEl.type === 'pick') {
              targetNode = targetNode.pick(pathEl.key);
            } else {
              throw new Error('invalid pathEl type');
            }
          }
          const workingRootUri = await mutationSet(
            weave,
            targetNode,
            edit.newValue
          );
          workingRootNode = weaveGet(workingRootUri);
        } else if (edit.type === 'append') {
          const workingRootUri = await mutationAppend(
            weave,
            targetNode,
            edit.newValue
          );
          workingRootNode = weaveGet(workingRootUri);
        } else {
          throw new Error('invalid mutation type');
        }
      }
      const finalRootUri = await mutationPublishArtifact(
        weave,
        // Local branch
        workingRootNode,
        // Target branch
        rootObjectRef.entityName,
        rootObjectRef.projectName,
        rootObjectRef.artifactName
      );
      return finalRootUri;
    },

    [weave]
  );
  return applyMutationsToRef;
};

const getCachedRefToTypedNode = async (
  weave: WeaveApp,
  refUri: string
): Promise<Node> => {
  const cachedTypedNode = refTypedNodeCache.get(refUri);
  if (cachedTypedNode != null) {
    return cachedTypedNode;
  }

  const uriParts = refUri.split('#');
  const baseUri = uriParts[0];
  let node: Node = opGet({uri: constString(baseUri)});

  if (uriParts.length !== 1) {
    const extraFields = uriParts[1].split('/');
    node = nodeFromExtra(node, extraFields);
  }
  const typedNode = await weave.refineNode(node, []);
  refTypedNodeCache.set(refUri, typedNode);

  return typedNode;
};

const useGetRefsType = (): ((refUris: string[]) => Promise<Type[]>) => {
  const weave = useWeaveContext();
  const getRefsType = useCallback(
    async (refUris: string[]): Promise<Type[]> => {
      const results = refUris.map(refUri =>
        getCachedRefToTypedNode(weave, refUri)
      );
      return Promise.allSettled(results).then(nodeResults =>
        nodeResults.map(nodeResult =>
          nodeResult.status === 'rejected' ? 'unknown' : nodeResult.value.type
        )
      );
    },
    [weave]
  );
  return getRefsType;
};

const useRefsType = (refUris: string[]): Loadable<Type[]> => {
  const refUrisDeep = useDeepMemo(refUris);
  const [results, setResults] = useState<Type[]>();
  const getRefsType = useGetRefsType();
  useEffect(() => {
    let isMounted = true;
    const updateResults = async () => {
      const res = await getRefsType(refUrisDeep);
      if (!isMounted) {
        return;
      }
      setResults(res);
    };
    updateResults();
    return () => {
      isMounted = false;
    };
  }, [getRefsType, refUrisDeep]);
  return {
    loading: results == null,
    result: results ?? [],
  };
};

const useCodeForOpRef = (opVersionRef: string): Loadable<string> => {
  return useNodeValue(
    useMemo(() => opDefCodeNode(opVersionRef), [opVersionRef])
  );
};

// Converters //
const spanToCallSchema = (
  entity: string,
  project: string,
  span: RawSpanFromStreamTableEraWithFeedback
): CallSchema => {
  // This rawSpan construction fixes issues with crashed runs using the
  // streamtable graph client (will be fixed in the future)
  const rawSpan = span;
  rawSpan.summary = span.summary ?? {
    latency_s: 0,
  };
  rawSpan.summary.latency_s = span.summary?.latency_s ?? 0;
  rawSpan.status_code = span.status_code ?? 'UNSET';
  rawSpan.inputs = span.inputs ?? {};

  return {
    entity,
    project,
    callId: span.span_id,
    traceId: span.trace_id,
    parentId: span.parent_id ?? null,
    spanName: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? refUriToOpVersionKey(span.name).opId
      : span.name,
    opVersionRef: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? span.name
      : null,
    rawSpan,
    rawFeedback: span.feedback,
    userId: null,
    runId: null,
  };
};

export const nodeFromExtra = (node: Node, extra: string[]): Node => {
  if (extra.length === 0) {
    return node;
  }
  if (extra[0] === LIST_INDEX_EDGE_NAME || extra[0] === AWL_ROW_EDGE_NAME) {
    return nodeFromExtra(
      callOpVeryUnsafe('index', {
        arr: node,
        index: constNumber(parseInt(extra[1], 10)),
      }) as Node,
      extra.slice(2)
    );
  } else if (
    extra[0] === DICT_KEY_EDGE_NAME ||
    extra[0] === AWL_COL_EDGE_NAME
  ) {
    return nodeFromExtra(
      callOpVeryUnsafe('pick', {
        obj: node,
        key: constString(extra[1]),
      }) as Node,
      extra.slice(2)
    );
  } else if (extra[0] === OBJECT_ATTR_EDGE_NAME) {
    return nodeFromExtra(
      callOpVeryUnsafe('Object-__getattr__', {
        self: node,
        name: constString(extra[1]),
      }) as Node,
      extra.slice(2)
    );
  } else {
    throw new Error('Unknown extra type: ' + extra);
  }
};

const refUnderlyingArtifactNode = (uri: string) => {
  const ref = parseRef(uri);
  if (!isWandbArtifactRef(ref)) {
    throw new Error(`Expected wandb artifact ref, got ${ref}`);
  }
  const projNode = opRootProject({
    entityName: constString(ref.entityName),
    projectName: constString(ref.projectName),
  });
  return opProjectArtifactVersion({
    project: projNode,
    artifactName: constString(ref.artifactName),
    artifactVersionAlias: constString(ref.artifactVersion),
  });
};

const opDefCodeNode = (uri: string) => {
  const artifactVersionNode = refUnderlyingArtifactNode(uri);
  const objPyFileNode = opArtifactVersionFile({
    artifactVersion: artifactVersionNode,
    path: constString('obj.py'),
  });
  return opFileContents({file: objPyFileNode});
};

const useFileContent = (
  entity: string,
  project: string,
  digest: string,
  opts?: {skip?: boolean}
): Loadable<string> => {
  throw new Error('Not implemented');
};

const useCallsDeleteFunc = (): {
  callsDelete: (projectID: string, callIDs: string[]) => Promise<void>;
  onDelete: () => void;
} => {
  throw new Error('Not implemented');
};

export const cgWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useCallsDeleteFunc,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  useRefsData,
  useApplyMutationsToRef,
  useFileContent,
  derived: {
    useChildCallsForCompare,
    useGetRefsType,
    useRefsType,
    useCodeForOpRef,
  },
};
