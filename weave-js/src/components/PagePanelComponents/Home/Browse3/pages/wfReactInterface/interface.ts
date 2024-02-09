import _ from 'lodash';
import LRUCache from 'lru-cache';
import {useMemo} from 'react';

import {
  constFunction,
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
  opIsNone,
  opMap,
  opPick,
  opProjectArtifact,
  opProjectArtifactTypes,
  opProjectArtifactVersion,
  opRootProject,
  opStringEqual,
} from '../../../../../../core';
import {useNodeValue} from '../../../../../../react';
import {Span, SpanWithFeedback} from '../../../Browse2/callTree';
import {fnRunsNode, useRuns, useRunsWithFeedback} from '../../../Browse2/callTreeHooks';
import {PROJECT_CALL_STREAM_NAME, WANDB_ARTIFACT_REF_PREFIX} from './constants';

export const OP_CATEGORIES = [
  'train',
  'predict',
  'score',
  'evaluate',
  'tune',
] as const;
const OBJECT_CATEGORIES = ['model', 'dataset'] as const;
type OpCategory = (typeof OP_CATEGORIES)[number];
export type ObjectCategory = (typeof OBJECT_CATEGORIES)[number];

type Loadable<T> = {
  loading: boolean;
  result: T | null;
};

type RefUri = string;

export type CallKey = {
  entity: string;
  project: string;
  callId: string;
};
export type CallSchema = CallKey & {
  // TODO: Add more fields & FKs
  spanName: string;
  opVersionRef: string | null;
  traceId: string;
  parentId: string | null;
  rawSpan: Span;
  rawFeedback?: any;
};

const spanToCallSchema = (
  entity: string,
  project: string,
  span: SpanWithFeedback
): CallSchema => {
  return {
    entity,
    project,
    callId: span.span_id,
    traceId: span.trace_id,
    parentId: span.parent_id,
    spanName: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? refUriToOpVersionKey(span.name).opId
      : span.name,
    opVersionRef: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? span.name
      : null,
    rawSpan: span,
    rawFeedback: span.feedback,
  };
};

export const useCall = (key: CallKey): Loadable<CallSchema | null> => {
  const cachedCall = getCallFromCache(key);
  const calls = useRuns(
    {
      entityName: key.entity,
      projectName: key.project,
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      callIds: [key.callId],
    },
    {skip: cachedCall != null}
  );

  return useMemo(() => {
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

export type CallFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  // Commented out means not yet implemented
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  parentIds?: string[];
  traceId?: string;
  callIds?: string[];
  traceRootsOnly?: boolean;
  opCategory?: OpCategory[];
};

// NOTE: THis method does not follow the standard pattern of the other hooks
// Need to think about how to make it more consistent or generalize the pattern
export const callsNode  = (
  entity: string,
  project: string,
  filter: CallFilter
): Node => {
  return fnRunsNode({
    entityName: entity,
    projectName: project,
    streamName: PROJECT_CALL_STREAM_NAME,
  }, {
    opUris: filter.opVersionRefs,
    inputUris: filter.inputObjectVersionRefs,
    outputUris: filter.outputObjectVersionRefs,
    traceId: filter.traceId,
    parentIds: filter.parentIds,
    traceRootsOnly: filter.traceRootsOnly,
    callIds: filter.callIds,
  })
}
export const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter
): Loadable<CallSchema[]> => {
  const calls = useRunsWithFeedback(
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
    },
    // TODO: Re-Enable feedback once we actually have it!
    true
  );
  return useMemo(() => {
    const allResults = (calls.result ?? []).map(run =>
      spanToCallSchema(entity, project, run)
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

type OpVersionKey = {
  entity: string;
  project: string;
  opId: string;
  versionHash: string;
};

export const refUriToOpVersionKey = (refUri: RefUri): OpVersionKey => {
  const refDict = refStringToRefDict(refUri);
  if (
    refDict.filePathParts.length !== 1 ||
    refDict.refExtraTuples.length !== 0 ||
    refDict.filePathParts[0] !== 'obj'
  ) {
    if (refDict.versionCommitHash !== '*') {
      throw new Error('Invalid refUri: ' + refUri);
    }
  }
  return {
    entity: refDict.entity,
    project: refDict.project,
    opId: refDict.artifactName,
    versionHash: refDict.versionCommitHash,
  };
};
export const opVersionKeyToRefUri = (key: OpVersionKey): RefUri => {
  return `${WANDB_ARTIFACT_REF_PREFIX}${key.entity}/${key.project}/${key.opId}:${key.versionHash}/obj`;
};

export type OpVersionSchema = OpVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  createdAtMs: number;
  category: OpCategory | null;
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

export const useOpVersion = (
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

type OpVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  category?: OpCategory[];
  opIds?: string[];
  latestOnly?: boolean;
};
export const useOpVersions = (
  entity: string,
  project: string,
  filter: OpVersionFilter,
  opts?: {skip?: boolean}
): Loadable<OpVersionSchema[]> => {
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
  }, [dataValue.loading, dataValue.result, entity, filter.category, project]);
};

type ObjectVersionKey = {
  entity: string;
  project: string;
  objectId: string;
  versionHash: string;
  path: string;
  refExtra?: string;
};

export const refUriToObjectVersionKey = (refUri: RefUri): ObjectVersionKey => {
  const refDict = refStringToRefDict(refUri);
  return {
    entity: refDict.entity,
    project: refDict.project,
    objectId: refDict.artifactName,
    versionHash: refDict.versionCommitHash,
    path: refDict.filePathParts.join('/'),
    refExtra: refDict.refExtraTuples
      .map(t => `${t.edgeType}/${t.edgeName}`)
      .join('/'),
  };
};

export const objectVersionKeyToRefUri = (key: ObjectVersionKey): RefUri => {
  return `${WANDB_ARTIFACT_REF_PREFIX}${key.entity}/${key.project}/${
    key.objectId
  }:${key.versionHash}/${key.path}${key.refExtra ? '#' + key.refExtra : ''}`;
};

export type ObjectVersionSchema = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  typeName: string;
  category: ObjectCategory | null;
  createdAtMs: number;
};

const typeNameToCategory = (typeName: string): ObjectCategory | null => {
  for (const category of OBJECT_CATEGORIES) {
    if (typeName.toLocaleLowerCase().includes(category)) {
      return category as ObjectCategory;
    }
  }
  return null;
};

const opNameToCategory = (opName: string): OpCategory | null => {
  for (const category of OP_CATEGORIES) {
    if (opName.toLocaleLowerCase().includes(category)) {
      return category as OpCategory;
    }
  }
  return null;
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

export const useObjectVersion = (
  key: ObjectVersionKey
): Loadable<ObjectVersionSchema | null> => {
  const cachedObjectVersion = getObjectVersionFromCache(key);
  const artifactVersionNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key.entity),
      project: constString(key.project),
    }),
    artifactName: constString(key.objectId),
    artifactVersionAlias: constString(key.versionHash),
  });
  const dataNode = artifactVersionNodeToObjectVersionDictNode(
    artifactVersionNode as any
  );
  const dataValue = useNodeValue(dataNode, {skip: cachedObjectVersion != null});

  return useMemo(() => {
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

type ObjectVersionFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  category?: ObjectCategory[];
  objectIds?: string[];
  latestOnly?: boolean;
};

export const useRootObjectVersions = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter
): Loadable<ObjectVersionSchema[]> => {
  // Note: Root objects will always have a single path and refExtra will be null
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

  const dataValue = useNodeValue(dataNode);

  return useMemo(() => {
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
  }, [dataValue.loading, dataValue.result, entity, filter.category, project]);
};

type WFNaiveRefDict = {
  entity: string;
  project: string;
  artifactName: string;
  versionCommitHash: string;
  filePathParts: string[];
  refExtraTuples: Array<{
    edgeType: string;
    edgeName: string;
  }>;
};

const refStringToRefDict = (uri: string): WFNaiveRefDict => {
  const scheme = WANDB_ARTIFACT_REF_PREFIX;
  if (!uri.startsWith(scheme)) {
    throw new Error('Invalid uri: ' + uri);
  }
  const uriWithoutScheme = uri.slice(scheme.length);
  let uriParts = uriWithoutScheme;
  let refExtraPath = '';
  const refExtraTuples = [];
  if (uriWithoutScheme.includes('#')) {
    [uriParts, refExtraPath] = uriWithoutScheme.split('#');
    const refExtraParts = refExtraPath.split('/');
    if (refExtraParts.length % 2 !== 0) {
      throw new Error('Invalid uri: ' + uri);
    }
    for (let i = 0; i < refExtraParts.length; i += 2) {
      refExtraTuples.push({
        edgeType: refExtraParts[i],
        edgeName: refExtraParts[i + 1],
      });
    }
  }
  const [entity, project, artifactNameAndVersion, filePath] = uriParts.split(
    '/',
    4
  );
  const [artifactName, versionCommitHash] = artifactNameAndVersion.split(':');
  const filePathParts = filePath.split('/');

  return {
    entity,
    project,
    artifactName,
    versionCommitHash,
    filePathParts,
    refExtraTuples,
  };
};

//// In Mem Cache Layer ////

const CACHE_SIZE = 5 * 2 ** 20; // 5MB

const callCache = new LRUCache<string, CallSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const callCacheKeyFn = (key: CallKey) => {
  return `call:${key.entity}/${key.project}/${key.callId}`;
};

const getCallFromCache = (key: CallKey) => {
  return callCache.get(callCacheKeyFn(key));
};

const setCallInCache = (key: CallKey, value: CallSchema) => {
  callCache.set(callCacheKeyFn(key), value);
};

const opVersionCache = new LRUCache<string, OpVersionSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const opVersionCacheKeyFn = (key: OpVersionKey) => {
  return `op:${key.entity}/${key.project}/${key.opId}/${key.versionHash}`;
};

const getOpVersionFromCache = (key: OpVersionKey) => {
  return opVersionCache.get(opVersionCacheKeyFn(key));
};

const setOpVersionInCache = (key: OpVersionKey, value: OpVersionSchema) => {
  opVersionCache.set(opVersionCacheKeyFn(key), value);
};

const objectVersionCache = new LRUCache<string, ObjectVersionSchema>({
  max: CACHE_SIZE,
  updateAgeOnGet: true,
});

const objectVersionCacheKeyFn = (key: ObjectVersionKey) => {
  return `obj:${key.entity}/${key.project}/${key.objectId}/${key.versionHash}/${key.path}/${key.refExtra}`;
};

const getObjectVersionFromCache = (key: ObjectVersionKey) => {
  return objectVersionCache.get(objectVersionCacheKeyFn(key));
};

const setObjectVersionInCache = (
  key: ObjectVersionKey,
  value: ObjectVersionSchema
) => {
  objectVersionCache.set(objectVersionCacheKeyFn(key), value);
};

//// Utilities ////
export const opVersionRefOpName = (opVersionRef: string) => {
  return refUriToOpVersionKey(opVersionRef).opId;
};

// This one is a huge hack b/c it is based on the name. Once this
// is added to the data model, we will need to make a query
// wherever this is used!
export const opVersionRefOpCategory = (opVersionRef: string) => {
  return opNameToCategory(opVersionRefOpName(opVersionRef));
};
