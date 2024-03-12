/**
 * This file defines `cgWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Compute Graph" (StreamTable) engine.
 */

import _ from 'lodash';
import {useCallback, useEffect, useMemo, useState} from 'react';

import { useWeaveContext } from '../../../../../../context';
import {
  constBoolean,
  constFunction,
  constNumber,
  constString,
  Node,
  opAnd,
  opArray,
  opArtifactLastMembership,
  opArtifactMembershipArtifactVersion,
  opArtifactName,
  opArtifactTypeArtifacts,
  opArtifactVersionArtifactSequence,
  opArtifactVersionCreatedAt,
  opArtifactVersionHash,
  opArtifactVersionIsWeaveObject,
  opArtifactVersionMetadata,
  opArtifactVersions,
  opArtifactVersionVersionId,
  opDict,
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
import { useDeepMemo } from '../../../../../../hookUtils';
import {parseRef, useNodeValue, WandbArtifactRef} from '../../../../../../react';
import {nodeFromExtra} from '../../../Browse2/Browse2ObjectVersionItemPage';
import {fnRunsNode, useRuns} from '../../../Browse2/callTreeHooks';
import {
  getCallFromCache,
  getObjectVersionFromCache,
  getOpVersionFromCache,
  setCallInCache,
  setObjectVersionInCache,
  setOpVersionInCache,
} from './cache';
import {
  OBJECT_CATEGORIES,
  PROJECT_CALL_STREAM_NAME,
  WANDB_ARTIFACT_REF_PREFIX,
} from './constants';
import {
  opNameToCategory,
  opVersionRefOpCategory,
  refUriToOpVersionKey,
} from './utilities';
import {
  CallFilter,
  CallKey,
  CallSchema,
  Loadable,
  ObjectCategory,
  ObjectVersionFilter,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpCategory,
  OpVersionFilter,
  OpVersionKey,
  OpVersionSchema,
  RawSpanFromStreamTableEra,
  RawSpanFromStreamTableEraWithFeedback,
  RefMutation,
  TableQuery,
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';
import { mutationPublishArtifact, mutationSet, nodeToEasyNode, weaveGet } from '../../../Browse2/easyWeave';

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  const cachedCall = key ? getCallFromCache(key) : null;
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
        setCallInCache(key, result);
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
    const result = allResults.filter((row: any) => {
      return (
        filter.opCategory == null ||
        (row.opVersionRef &&
          filter.opCategory.includes(
            opVersionRefOpCategory(row.opVersionRef) as OpCategory
          ))
      );
    });

    if (calls.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      allResults.forEach(call => {
        setCallInCache(
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
  }, [calls.result, calls.loading, entity, project, filter.opCategory]);
};

const useOpVersion = (
  // Null value skips
  key: OpVersionKey | null
): Loadable<OpVersionSchema | null> => {
  const cachedOpVersion = key ? getOpVersionFromCache(key) : null;
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
        setOpVersionInCache(key, result);
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
): Loadable<OpVersionSchema[]> => {
  let dataNode = useOpVersionsNode(entity, project, filter);
  if (limit) {
    dataNode = opLimit({arr: dataNode, limit: constNumber(limit)});
  }

  const dataValue = useNodeValue(dataNode, {skip: opts?.skip});

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        result: [],
      };
    }
    const result = (dataValue.result ?? [])
      .map((row: any) => ({
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
      }))
      .filter((row: any) => {
        return (
          filter.category == null || filter.category.includes(row.category)
        );
      }) as OpVersionSchema[];

    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      result.forEach(op => {
        setOpVersionInCache(
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
        result,
      };
    }
  }, [
    dataValue.loading,
    dataValue.result,
    entity,
    filter.category,
    opts?.skip,
    project,
  ]);
};

const useObjectVersion = (
  // Null value skips
  key: ObjectVersionKey | null
): Loadable<ObjectVersionSchema | null> => {
  const cachedObjectVersion = key ? getObjectVersionFromCache(key) : null;
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
            category: typeNameToCategory(dataValue.result.typeName as string),
            createdAtMs: dataValue.result.createdAtMs as number,
          };
    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      if (result) {
        setObjectVersionInCache(key, result);
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
): Loadable<ObjectVersionSchema[]> => {
  let dataNode = useRootObjectVersionsNode(entity, project, filter);
  if (limit) {
    dataNode = opLimit({arr: dataNode, limit: constNumber(limit)});
  }
  const dataValue = useNodeValue(dataNode, {skip: opts?.skip});

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
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
          filter.category == null || filter.category.includes(row.category)
        );
      })
      // TODO: Move this to the weave filters?
      .filter((row: any) => {
        return !['OpDef', 'stream_table', 'type'].includes(row.typeName);
      }) as ObjectVersionSchema[];

    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      result.forEach(obj => {
        setObjectVersionInCache(
          {
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
        result,
      };
    }
  }, [
    dataValue.loading,
    dataValue.result,
    entity,
    filter.category,
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

const useRefsData = (refUris: string[], tableQuery?:TableQuery): Loadable<any[]> => {
  const refUrisDeep = useDeepMemo(refUris);
  const tableQueryDeep = useDeepMemo(tableQuery);

  const itemsNode = useMemo(() => {
    let nodes = refUrisDeep.map(refToNode);
    if (tableQueryDeep) {
      nodes = nodes.map(node => {
        if (tableQueryDeep.columns.length > 0) {
          node = opMap({
            arr: node,
            mapFn: constFunction({row: 'any'}, ({row}) =>
              opDict(
                _.fromPairs(
                  tableQueryDeep.columns.map(key => [
                    key,
                    opPick({obj: row, key: constString(key)}),
                  ])
                ) as any
              )
            ),
          })
        }
        if (tableQueryDeep.limit) {
          node = opLimit({
            arr: node,
            limit: constNumber(tableQueryDeep.limit),
          });
        }
        return node
      })
    }
    return opArray(_.fromPairs(nodes.map((node, i) => [i, node])) as any);
  }, [refUrisDeep, tableQueryDeep]);
  return useNodeValue(itemsNode);
};


const useApplyMutationsToRef = (): ((
  refUri: string,
  edits: RefMutation[]
) => Promise<string>) => {
  const weave = useWeaveContext();
  const applyMutationsToRef = useCallback(
    async (refUri: string, edits: RefMutation[]): Promise<string> => {
      let workingRootNode = refToNode(refUri);
      const rootObjectRef = parseRef(refUri) as WandbArtifactRef;
      for (const edit of edits) {
        let targetNode = nodeToEasyNode(workingRootNode as OutputNode);
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


const useRefsType = (refUris: string[]) : Loadable<Type[]> => {
  const weave = useWeaveContext();
  const refUrisDeep = useDeepMemo(refUris);
  const [results, setResults] = useState<Type[] | null>(null);
  useEffect(() => {
    let mounted = true;
    const loadTypes = () => {
      const proms =  refUrisDeep.map(refUri => weave.refineNode(refToNode(refUri), []));
      Promise.all(proms).then((nodes) => {
        if (mounted) {
          const simpleTypes: Type[] = nodes.map((node) => {
            return node.type
          })
          setResults(simpleTypes);
        }
      });
    }

    loadTypes();

    return () => {
      mounted = false;
    };
  }, [refUrisDeep, weave])
  return useMemo(() => {
    if (results == null) {
      return {
        loading: true,
        result: [],
      };
    }
    return {
      loading: false,
      result: results,
    };
  }, [results])
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

const refToNode = (refUri: string): Node => {
  const uriParts = refUri.split('#');
  const baseUri = uriParts[0];
  const objNode = opGet({uri: constString(baseUri)});
  if (uriParts.length === 1) {
    return objNode;
  }
  const extraFields = uriParts[1].split('/');
  return nodeFromExtra(objNode, extraFields);
};


// Helpers //
const typeNameToCategory = (typeName: string): ObjectCategory | null => {
  for (const category of OBJECT_CATEGORIES) {
    if (typeName.toLocaleLowerCase().includes(category)) {
      return category as ObjectCategory;
    }
  }
  return null;
};

export const cgWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  useRefsData,
  useApplyMutationsToRef,
  derived: {useChildCallsForCompare, useRefsType},
};
