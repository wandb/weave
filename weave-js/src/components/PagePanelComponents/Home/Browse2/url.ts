import {isWandbArtifactRef, parseRef} from '@wandb/weave/react';

import {useWeaveflowRouteContext} from '../Browse3/context';
import { fetchRegistryName, isArtifactRegistryProject } from '@wandb/weave/common/util/artifacts';

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

export type ArtifactRefURLInfo = {
  entityName: string;
  projectName: string;
  artifactName: string;
  artifactVersion: string;
  artifactType: string;
  orgName: string;
}

export function fetchArtifactRefPageUrl(ref: ArtifactRefURLInfo): string {
  // Registry artifact
  if (isArtifactRegistryProject(ref.projectName)) {
    let res = `orgs/${ref.orgName}/registry/${fetchRegistryName(ref.projectName)}`
    const urlParams = new URLSearchParams();
    urlParams.set(
      'selectionPath',
      `${ref.entityName}/${ref.projectName}/${ref.artifactName}`
    );
    urlParams.set('view', 'membership');
    urlParams.set('version', ref.artifactVersion);
    if (Array.from(urlParams.keys()).length > 0) {
      res += `?${urlParams.toString()}`;
    }
    return `${window.location.origin}/${res}`;
  }

  // Old model registry artifact
  if (ref.artifactType.toLowerCase().includes('model') && ref.projectName === 'model-registry') {
    let res = `${ref.entityName}/registry/model`
    const urlParams = new URLSearchParams();
    urlParams.set('selectionPath', `${ref.entityName}/model-registry/${ref.artifactName}`);
    urlParams.set('view', 'membership');
    urlParams.set('version', ref.artifactVersion);
    if (Array.from(urlParams.keys()).length > 0) {
      res += `?${urlParams.toString()}`;
    }
    return `${window.location.origin}/${res}`;
  }

  // Regular artifact
  return `${window.location.origin}/${ref.entityName}/${ref.projectName}/artifacts/${ref.artifactType}/${ref.artifactName}/${ref.artifactVersion}`
}
