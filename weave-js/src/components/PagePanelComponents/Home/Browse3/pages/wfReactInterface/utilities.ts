/**
 * This file contains the utilities that relate to working with the
 * wfReactInterface. Importantly, these should never make direct calls down to
 * the data providers - they should always go through the interface exposed via
 * the context.
 */

import {OP_CATEGORIES, WANDB_ARTIFACT_REF_PREFIX} from './constants';
import {useWFHooks} from './context';
import {
  ObjectVersionKey,
  ObjectVersionSchema,
  OpCategory,
  OpVersionKey,
} from './interface';
import {CallSchema, Loadable} from './interface';

type RefUri = string;

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
