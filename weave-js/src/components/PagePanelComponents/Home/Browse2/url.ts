import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';

import {useWeaveflowRouteContext} from '../Browse3/context';

export const useRefPageUrl = () => {
  const {baseRouter} = useWeaveflowRouteContext();
  const refPageUrl = (objectType: string, refS: string) => {
    const ref = parseRef(refS);
    if (!isWandbArtifactRef(ref)) {
      throw new Error('Not a wandb artifact ref: ' + refS);
    }

    return baseRouter.refUIUrl(objectType, {
      scheme: ref.scheme,
      entityName: ref.entityName,
      projectName: ref.projectName,
      artifactName: ref.artifactName,
      artifactVersion: ref.artifactVersion,
      artifactPath: '',
    });
  };
  return refPageUrl;
};
