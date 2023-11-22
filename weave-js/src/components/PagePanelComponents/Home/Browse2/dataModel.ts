import {
  constString,
  opArtifactVersionFile,
  opFileContents,
  opProjectArtifactVersion,
  opRootProject,
} from '@wandb/weave/core';
import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';

export const refUnderlyingArtifactNode = (uri: string) => {
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

export const opDefCodeNode = (uri: string) => {
  const artifactVersionNode = refUnderlyingArtifactNode(uri);
  const objPyFileNode = opArtifactVersionFile({
    artifactVersin: artifactVersionNode,
    path: constString('obj.py'),
  });
  return opFileContents({file: objPyFileNode});
};

export const opDisplayName = (opName: string) => {
  if (opName.startsWith('wandb-artifact:')) {
    const ref = parseRef(opName);
    if (isWandbArtifactRef(ref)) {
      let refOpName = ref.artifactName;
      if (refOpName.startsWith('op-')) {
        refOpName = refOpName.slice(3);
      }
      return refOpName + ':' + ref.artifactVersion;
    }
  }
  return opName;
};
