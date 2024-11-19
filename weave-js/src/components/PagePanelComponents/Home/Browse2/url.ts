import {checkRegistryProject} from '@wandb/weave/common/util/artifacts';
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

export type ArtifactRefURLInfo = {
  entityName: string;
  projectName: string;
  artifactName: string;
  artifactVersion: string;
  artifactType: string;
  orgName: string;
};

// Keep somewhat in sync with
// https://github.com/wandb/core/blob/master/frontends/app/src/util/urls/paths.ts
export function fetchArtifactRefPageUrl(ref: ArtifactRefURLInfo): string {
  // Handle registry artifact
  const {isRegistryProject, registryName} = checkRegistryProject(
    ref.projectName
  );
  if (isRegistryProject && registryName) {
    return buildRegistryArtifactUrl(ref, registryName);
  }

  // Handle old team level model registry artifact
  if (isModelRegistryArtifact(ref)) {
    return buildTeamModelRegistryUrl(ref);
  }

  // Handle regular artifact
  return buildRegularArtifactUrl(ref);
}

function isModelRegistryArtifact(ref: ArtifactRefURLInfo): boolean {
  return (
    ref.artifactType.toLowerCase().includes('model') &&
    ref.projectName === 'model-registry'
  );
}

function buildRegistryArtifactUrl(
  ref: ArtifactRefURLInfo,
  registryName: string
): string {
  const path = `orgs/${ref.orgName}/registry/${registryName}`;
  const params = new URLSearchParams({
    selectionPath: `${ref.entityName}/${ref.projectName}/${encodeURIComponent(
      ref.artifactName
    )}`,
    view: 'membership',
    version: ref.artifactVersion,
  });

  return `${window.location.origin}/${path}?${params.toString()}`;
}

function buildRegularArtifactUrl(ref: ArtifactRefURLInfo): string {
  return `${window.location.origin}/${ref.entityName}/${
    ref.projectName
  }/artifacts/${encodeURIComponent(ref.artifactType)}/${encodeURIComponent(
    ref.artifactName
  )}/${ref.artifactVersion}`;
}

function buildTeamModelRegistryUrl(ref: ArtifactRefURLInfo): string {
  const path = `${ref.entityName}/registry/model`;
  const params = new URLSearchParams({
    selectionPath: `${ref.entityName}/model-registry/${encodeURIComponent(
      ref.artifactName
    )}`,
    view: 'membership',
    version: ref.artifactVersion,
  });

  return `${window.location.origin}/${path}?${params.toString()}`;
}
