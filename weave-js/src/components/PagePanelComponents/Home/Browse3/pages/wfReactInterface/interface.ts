import _ from 'lodash';
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
import {Call as CallTreeSpan} from '../../../Browse2/callTree';
import {useRuns} from '../../../Browse2/callTreeHooks';
import {PROJECT_CALL_STREAM_NAME, WANDB_ARTIFACT_REF_PREFIX} from './constants';

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
  rawSpan: CallTreeSpan;
};

const spanToCallSchema = (
  entity: string,
  project: string,
  span: CallTreeSpan
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
  };
};

export const useCall = (key: CallKey): Loadable<CallSchema | null> => {
  const calls = useRuns(
    {
      entityName: key.entity,
      projectName: key.project,
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      callIds: [key.callId],
    }
  );

  return useMemo(() => {
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
      return {
        loading: false,
        result,
      };
    }
  }, [calls.loading, calls.result, key.entity, key.project]);
};

type CallFilter = {
  // Filters are ANDed across the fields and ORed within the fields
  // Commented out means not yet implemented
  opVersionRefs?: string[];
  inputObjectVersionRefs?: string[];
  outputObjectVersionRefs?: string[];
  //   traceIds?: string[];
  parentIds?: string[];
  //   callIds?: string[];
  //   traceRootsOnly?: boolean;
};
export const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter
): Loadable<CallSchema[]> => {
  const calls = useRuns(
    {
      entityName: entity,
      projectName: project,
      streamName: PROJECT_CALL_STREAM_NAME,
    },
    {
      opUris: filter.opVersionRefs,
      inputUris: filter.inputObjectVersionRefs,
      outputUris: filter.outputObjectVersionRefs,
      // traceId?: string;
      parentIds: filter.parentIds,
      // traceRootsOnly?: boolean;
      // callIds?: string[];
    }
  );
  return useMemo(() => {
    const result = (calls.result ?? []).map(run =>
      spanToCallSchema(entity, project, run)
    );
    if (calls.loading) {
      return {
        loading: true,
        result,
      };
    } else {
      return {
        loading: false,
        result,
      };
    }
  }, [entity, project, calls.loading, calls.result]);
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
    throw new Error('Invalid refUri: ' + refUri);
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

type OpCategory = 'train' | 'predict' | 'score' | 'evaluate' | 'tune';

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
  key: OpVersionKey
): Loadable<OpVersionSchema | null> => {
  const artifactVersionNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key.entity),
      project: constString(key.project),
    }),
    artifactName: constString(key.opId),
    artifactVersionAlias: constString(key.versionHash),
  });
  const dataNode = artifactVersionNodeToOpVersionDictNode(
    artifactVersionNode as any
  );
  const dataValue = useNodeValue(dataNode);
  return useMemo(() => {
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
      return {
        loading: false,
        result,
      };
    }
  }, [dataValue.loading, dataValue.result, key]);
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
  filter: OpVersionFilter
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

  const dataValue = useNodeValue(dataNode);

  return useMemo(() => {
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
      });

    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
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

export type ObjectCategory = 'model' | 'dataset';
export type ObjectVersionSchema = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  typeName: string;
  category: ObjectCategory | null;
  createdAtMs: number;
};

const typeNameToCategory = (typeName: string): ObjectCategory | null => {
  const categories = ['model', 'dataset'];
  for (const category of categories) {
    if (typeName.toLocaleLowerCase().includes(category)) {
      return category as ObjectCategory;
    }
  }
  return null;
};

const opNameToCategory = (opName: string): OpCategory | null => {
  const categories = ['train', 'predict', 'score', 'evaluate', 'tune'];
  for (const category of categories) {
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
  const dataValue = useNodeValue(dataNode);

  return useMemo(() => {
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
      return {
        loading: false,
        result,
      };
    }
  }, [dataValue.loading, dataValue.result, key]);
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
      });

    if (dataValue.loading) {
      return {
        loading: true,
        result,
      };
    } else {
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
