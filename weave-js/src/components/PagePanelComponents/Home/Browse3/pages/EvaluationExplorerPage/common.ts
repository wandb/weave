import {parseWeaveRef} from '@wandb/weave/react';

export const refStringToName = (ref: string) => {
  const parsedRef = parseWeaveRef(ref);
  return `${parsedRef.artifactName} (${parsedRef.artifactVersion.slice(0, 4)})`;
};
