import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';

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
