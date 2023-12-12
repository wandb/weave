import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';

export const refPageUrl = (objectType: string, refS: string) => {
  const ref = parseRef(refS);
  if (!isWandbArtifactRef(ref)) {
    throw new Error('Not a wandb artifact ref: ' + refS);
  }
  // const res = `/${ref.entityName}/${ref.projectName}/${objectType}/${ref.artifactName}/${ref.artifactVersion}`;
  const res = `/${ref.entityName}/${ref.projectName}/objects/${ref.artifactName}/versions/${ref.artifactVersion}`;
  return res;
};
