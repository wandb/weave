import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import {URL_BROWSE2} from '@wandb/weave/urls';

export const refPageUrl = (objectType: string, refS: string) => {
  const ref = parseRef(refS);
  if (!isWandbArtifactRef(ref)) {
    throw new Error('Not a wandb artifact ref: ' + refS);
  }
  const res = `/${URL_BROWSE2}/${ref.entityName}/${ref.projectName}/${objectType}/${ref.artifactName}/${ref.artifactVersion}`;
  return res;
};
export const opPageUrl = (opUri: string) => {
  const parsed = parseRef(opUri);
  if (!isWandbArtifactRef(parsed)) {
    throw new Error('non wandb artifact ref not yet handled');
  }
  return `/${URL_BROWSE2}/${parsed.entityName}/${parsed.projectName}/OpDef/${parsed.artifactName}/${parsed.artifactVersion}`;
};
