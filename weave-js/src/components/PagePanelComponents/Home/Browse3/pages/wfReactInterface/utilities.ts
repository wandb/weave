/**
 * This file contains the utilities that relate to working with the
 * wfReactInterface. Importantly, these should never make direct calls down to
 * the data providers - they should always go through the interface exposed via
 * the context.
 */

import {parseRef, WeaveKind} from '../../../../../../react';
import {WANDB_ARTIFACT_SCHEME} from '../../../common';
import {
  KNOWN_BASE_OBJECT_CLASSES,
  OP_CATEGORIES,
  WANDB_ARTIFACT_REF_PREFIX,
  WANDB_ARTIFACT_REF_SCHEME,
  WEAVE_REF_PREFIX,
  WEAVE_REF_SCHEME,
} from './constants';
import {useWFHooks} from './context';
import {
  KnownBaseObjectClassType,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpCategory,
  OpVersionKey,
} from './wfDataModelHooksInterface';
import {CallSchema, Loadable} from './wfDataModelHooksInterface';

type RefUri = string;

export const refUriToOpVersionKey = (refUri: RefUri): OpVersionKey => {
  const refDict = refStringToRefDict(refUri);
  if (
    refDict.scheme === WANDB_ARTIFACT_REF_PREFIX &&
    (refDict.filePathParts.length !== 1 ||
      refDict.refExtraTuples.length !== 0 ||
      refDict.filePathParts[0] !== 'obj')
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
  return `${WEAVE_REF_PREFIX}${key.entity}/${key.project}/op/${key.opId}:${key.versionHash}`;
  // return `${WANDB_ARTIFACT_REF_PREFIX}${key.entity}/${key.project}/${key.opId}:${key.versionHash}/obj`;
};

export const refUriToObjectVersionKey = (refUri: RefUri): ObjectVersionKey => {
  const refDict = refStringToRefDict(refUri);
  if (refDict.scheme === WANDB_ARTIFACT_REF_SCHEME) {
    return {
      scheme: refDict.scheme,
      entity: refDict.entity,
      project: refDict.project,
      objectId: refDict.artifactName,
      versionHash: refDict.versionCommitHash,
      path: refDict.filePathParts.join('/'),
      refExtra: refDict.refExtraTuples
        .map(t => `${t.edgeType}/${t.edgeName}`)
        .join('/'),
    };
  } else if (refDict.scheme === WEAVE_REF_SCHEME) {
    if (refDict.weaveKind == null) {
      throw new Error('Invalid weaveKind: ' + refDict.weaveKind);
    }
    return {
      scheme: refDict.scheme,
      entity: refDict.entity,
      project: refDict.project,
      weaveKind: refDict.weaveKind,
      objectId: refDict.artifactName,
      versionHash: refDict.versionCommitHash,
      path: refDict.filePathParts.join('/'),
      refExtra: refDict.refExtraTuples
        .map(t => `${t.edgeType}/${t.edgeName}`)
        .join('/'),
    };
  } else {
    throw new Error(
      'Invalid scheme: ' + refDict.scheme + ' for uri: ' + refUri
    );
  }
};

export const objectVersionKeyToRefUri = (key: ObjectVersionKey): RefUri => {
  if (key.scheme === WANDB_ARTIFACT_REF_SCHEME) {
    return `${WANDB_ARTIFACT_REF_PREFIX}${key.entity}/${key.project}/${
      key.objectId
    }:${key.versionHash}/${key.path}${key.refExtra ? '#' + key.refExtra : ''}`;
  } else if (key.scheme === WEAVE_REF_SCHEME) {
    let res = `${WEAVE_REF_PREFIX}${key.entity}/${key.project}/object/${key.objectId}:${key.versionHash}`;
    if (key.refExtra != null && key.refExtra !== '') {
      res += `/${key.refExtra}`;
    }
    return res;
  }
  throw new Error('Invalid scheme: ' + key);
};

type WFNaiveRefDict = {
  scheme: string;
  entity: string;
  project: string;
  weaveKind?: WeaveKind;
  artifactName: string;
  versionCommitHash: string;
  filePathParts: string[];
  refExtraTuples: Array<{
    edgeType: string;
    edgeName: string;
  }>;
};

export const refStringToRefDict = (uri: string): WFNaiveRefDict => {
  if (uri.startsWith(WANDB_ARTIFACT_REF_PREFIX)) {
    return wandbArtifactRefStringToRefDict(uri);
  } else if (uri.startsWith(WEAVE_REF_PREFIX)) {
    return weaveRefStringToRefDict(uri);
  }
  throw new Error('Invalid uri: ' + uri);
};

const wandbArtifactRefStringToRefDict = (uri: string): WFNaiveRefDict => {
  const scheme = WANDB_ARTIFACT_SCHEME;
  if (!uri.startsWith(WANDB_ARTIFACT_REF_PREFIX)) {
    throw new Error('Invalid uri: ' + uri);
  }
  const uriWithoutScheme = uri.slice(WANDB_ARTIFACT_REF_PREFIX.length);
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
  const filePathParts = filePath?.split('/') ?? [];

  return {
    scheme,
    entity,
    project,
    artifactName,
    versionCommitHash,
    filePathParts,
    refExtraTuples,
  };
};

const weaveRefStringToRefDict = (uri: string): WFNaiveRefDict => {
  const parsed = parseRef(uri);
  if (parsed.scheme !== WEAVE_REF_SCHEME) {
    throw new Error('Invalid uri: ' + uri);
  }
  const {
    scheme,
    entityName: entity,
    projectName: project,
    weaveKind,
    artifactRefExtra,
  } = parsed;
  let {artifactName, artifactVersion: versionCommitHash} = parsed;
  if (parsed.weaveKind === 'table') {
    artifactName = versionCommitHash;
    versionCommitHash = '';
  }
  const refExtraTuples: WFNaiveRefDict['refExtraTuples'] = [];
  if (artifactRefExtra) {
    const refExtraParts = artifactRefExtra.split('/');
    if (refExtraParts.length % 2 !== 0) {
      throw new Error('Invalid uri: ' + uri + '. got: ' + refExtraParts);
    }
    for (let i = 0; i < refExtraParts.length; i += 2) {
      refExtraTuples.push({
        edgeType: refExtraParts[i],
        edgeName: refExtraParts[i + 1],
      });
    }
  }

  return {
    scheme,
    entity,
    project,
    weaveKind,
    artifactName,
    versionCommitHash,
    filePathParts: [],
    refExtraTuples,
  };
};

export const opVersionRefOpName = (opVersionRef: string) => {
  return refUriToOpVersionKey(opVersionRef).opId;
};

// This one is a huge hack b/c it is based on the name. Once this is added to
// the data model, we will need to make a query wherever this is used! Action:
// Remove all uses of this function other than the use in the compute graph
// interface (for which the datamodel is unlikely to every capture this
// information). opCategory should be moved to the CallSchema and/or the
// OpVersionSchema. If it is inferred, then that should be hidden from the
// caller. The fact that this is imported in the RunsTable is a smell of leaking
// abstraction.
export const opVersionRefOpCategory = (opVersionRef: string) => {
  return opNameToCategory(opVersionRefOpName(opVersionRef));
};

export const opNameToCategory = (opName: string): OpCategory | null => {
  for (const category of OP_CATEGORIES) {
    if (opName.toLocaleLowerCase().includes(category)) {
      return category as OpCategory;
    }
  }
  return null;
};

export const typeNameToCategory = (
  typeName: string
): KnownBaseObjectClassType | null => {
  for (const category of KNOWN_BASE_OBJECT_CLASSES) {
    if (typeName.toLocaleLowerCase().includes(category)) {
      return category as KnownBaseObjectClassType;
    }
  }
  return null;
};

export const objectVersionNiceString = (ov: ObjectVersionSchema) => {
  let result = ov.objectId;
  if (ov.versionHash === '*') {
    return result;
  }
  result += `:v${ov.versionIndex}`;
  if (ov.path !== 'obj') {
    result += `/${ov.path}`;
  }
  if (ov.refExtra) {
    result += `#${ov.refExtra}`;
  }
  return result;
};

/// Hooks ///

export const useParentCall = (
  call: CallSchema | null
): Loadable<CallSchema | null> => {
  const {useCall} = useWFHooks();
  let parentCall = null;
  if (call && call.parentId) {
    parentCall = {
      entity: call.entity,
      project: call.project,
      callId: call.parentId,
    };
  }
  return useCall(parentCall);
};
