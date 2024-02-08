import _ from 'lodash';
import {useMemo} from 'react';

import {
  constFunction,
  constString,
  opArray,
  opArtifactLastMembership,
  opArtifactMembershipArtifactVersion,
  opArtifactTypeArtifacts,
  opArtifactVersionHash,
  opArtifactVersionIsWeaveObject,
  opArtifactVersionMetadata,
  opArtifactVersionName,
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
} from '../../../../../../core';
import {useNodeValue} from '../../../../../../react';
import {Call as CallTreeSpan} from '../../../Browse2/callTree';
import {useRuns} from '../../../Browse2/callTreeHooks';

const PROJECT_CALL_STREAM_NAME = 'stream';
const WANDB_ARTIFACT_REF_PREFIX = 'wandb-artifact:///';

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
    spanName: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? refUriToOpVersionKey(span.name).opId
      : span.name,
    opVersionRef: span.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? span.name
      : null,
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
  //   opVersionRefs?: string[];
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
      // opUris?: string[];
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
  return `wandb-artifact:///${key.entity}/${key.project}/${key.opId}:${key.versionHash}/obj`;
};

type MVPOpCategory = 'train' | 'predict' | 'score' | 'evaluate' | 'tune';

type OpVersionSchema = OpVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
};

export const useOpVersion = (
  key: OpVersionKey
): Loadable<OpVersionSchema | null> => {
  const artifactNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key.entity),
      project: constString(key.project),
    }),
    artifactName: constString(key.opId),
    artifactVersionAlias: constString(key.versionHash),
  });
  const versionIndexNode = opArtifactVersionVersionId({
    artifactVersion: artifactNode,
  });
  //   const metadataNode = opArtifactVersionMetadata({
  //     artifactVersion: artifactNode,
  //   });
  //   const typeNameNode = opPick({
  //     obj: metadataNode,
  //     key: constString('_weave_meta.type_name'),
  //   });
  const dataNode = opDict({
    missing: opIsNone({val: artifactNode}),
    // typeName: typeNameNode,
    versionIndex: versionIndexNode,
  } as any);
  const dataValue = useNodeValue(dataNode);
  return useMemo(() => {
    const result =
      dataValue.result == null || dataValue.result.missing
        ? null
        : {
            ...key,
            versionIndex: dataValue.result.versionIndex as number,
            // typeName: dataValue.result.typeName as string,
            // category: typeNameToCategory(dataValue.result.typeName as string),
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
  category?: MVPOpCategory[];
  opRefs?: string[];
  latestOnly?: boolean;
};
export const useOpVersions = (
  entity: string,
  project: string,
  filter: OpVersionFilter
): Loadable<OpVersionKey[]> => {
  throw new Error('Not implemented');
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
  return `wandb-artifact:///${key.entity}/${key.project}/${key.objectId}:${
    key.versionHash
  }/${key.path}${key.refExtra ? '#' + key.refExtra : ''}`;
};

export type MVPObjectCategory = 'model' | 'dataset';
export type ObjectVersionSchema = ObjectVersionKey & {
  // TODO: Add more fields & FKs
  versionIndex: number;
  typeName: string;
  category: MVPObjectCategory | null;
};

const typeNameToCategory = (typeName: string): MVPObjectCategory | null => {
  const categories = ['model', 'dataset'];
  for (const category of categories) {
    if (typeName.toLocaleLowerCase().includes(category)) {
      return category as MVPObjectCategory;
    }
  }
  return null;
};

export const useObjectVersion = (
  key: ObjectVersionKey
): Loadable<ObjectVersionSchema | null> => {
  const artifactNode = opProjectArtifactVersion({
    project: opRootProject({
      entity: constString(key.entity),
      project: constString(key.project),
    }),
    artifactName: constString(key.objectId),
    artifactVersionAlias: constString(key.versionHash),
  });
  const versionIndexNode = opArtifactVersionVersionId({
    artifactVersion: artifactNode,
  });
  const metadataNode = opArtifactVersionMetadata({
    artifactVersion: artifactNode,
  });
  const typeNameNode = opPick({
    obj: metadataNode,
    key: constString('_weave_meta.type_name'),
  });
  const dataNode = opDict({
    missing: opIsNone({val: artifactNode}),
    typeName: typeNameNode,
    versionIndex: versionIndexNode,
  } as any);
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
  //   category?: MVPObjectCategory[];
  objectIds?: string[];
  latestOnly?: boolean;
};

export const useRootObjectVersions = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter
  // Question: Should this return the entire schema or just the key?
): Loadable<ObjectVersionKey[]> => {
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
        objectId: opArtifactVersionName({artifactVersion: row}),
        versionHash: opArtifactVersionHash({artifactVersion: row}),
      } as any);
    }),
  });

  const dataValue = useNodeValue(dataNode);

  return useMemo(() => {
    const result = (dataValue.result ?? []).map((row: any) => ({
      entity,
      project,
      objectId: row.objectId as string,
      versionHash: row.versionHash as string,
      path: 'obj',
      refExtra: null,
    }));
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
  }, [dataValue.loading, dataValue.result, entity, project]);
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
