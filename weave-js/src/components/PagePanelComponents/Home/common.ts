import {constString, Node, opRootArtifactVersion} from '@wandb/weave/core';

export type NavigateToExpressionType = (expression: Node) => void;
export type SetPreviewNodeType = (
  node: React.ReactNode,
  requestedWidth?: string
) => void;

export const WANDB_ARTIFACT_SCHEME = 'wandb-artifact:';

export const getArtifactVersionNodeFromUri = (
  uri: string,
  artifactTypeName: string
): Node<'artifactVersion'> => {
  const url = new URL(uri);
  if (url.protocol !== WANDB_ARTIFACT_SCHEME) {
    throw new Error(`Expected ${WANDB_ARTIFACT_SCHEME} got ${url.protocol}`);
  }
  const [entityName, projectName, artifactVersionName] = url.pathname
    .replace(/^\/+/, '')
    .split('/');
  const artifactVersionNode = opRootArtifactVersion({
    entityName: constString(entityName),
    projectName: constString(projectName),
    artifactTypeName: constString(artifactTypeName),
    artifactVersionName: constString(artifactVersionName),
  });

  return artifactVersionNode;
};
