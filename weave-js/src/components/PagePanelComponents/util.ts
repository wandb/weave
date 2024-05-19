import {isAssignableTo, NodeOrVoidNode, Type} from '@wandb/weave/core';

export const REMOTE_URI_PREFIX = 'wandb-artifact:///';
export const LOCAL_URI_PREFIX = 'local-artifact:///';

export type RemoteURIType = string;
type LocalURIType = string;

export const isRemoteURI = (uri: string): uri is RemoteURIType =>
  uri.startsWith(REMOTE_URI_PREFIX);
export const isLocalURI = (uri: string): uri is LocalURIType =>
  uri.startsWith(LOCAL_URI_PREFIX);

export type BranchPointType = {
  commit: string;
  n_commits: number;
  original_uri: string;
};

export const inJupyterCell = () => {
  return window.location.toString().includes('weave_jupyter');
};

export const isServedLocally = () => {
  return (
    window.location.hostname === 'localhost' ||
    window.location.hostname.endsWith('colab.googleusercontent.com')
  );
};

export const uriFromNode = (node: NodeOrVoidNode): string | null => {
  if (node.nodeType === 'output') {
    if (node.fromOp.name === 'get') {
      const uriNode = node.fromOp.inputs.uri;
      if (uriNode.nodeType === 'const') {
        const uriVal = uriNode.val;
        if (typeof uriVal === 'string') {
          return uriVal;
        }
      }
    }
  }
  return null;
};

export const branchPointIsRemote = (branchPoint: BranchPointType | null) => {
  return branchPoint?.original_uri.startsWith(REMOTE_URI_PREFIX) ?? false;
};

export const weaveTypeIsPanel = (weaveType?: Type) => {
  return isAssignableTo(weaveType || ('any' as const), {
    type: 'Panel' as any,
  });
};

export const weaveTypeIsPanelGroup = (weaveType?: Type) => {
  return isAssignableTo(weaveType || ('any' as const), {
    type: 'Group' as any,
  });
};

export const toArtifactSafeName = (name: string) =>
  name.replace(/[^a-zA-Z0-9-.]/g, '_');

const entityNameFromRemoteURI = (uri: RemoteURIType) => {
  const parts = uri.split(REMOTE_URI_PREFIX)[1].split('/');
  return {
    entity: parts[0],
    project: parts[1],
  };
};

export const determineURISource = (
  uri: string | null,
  branchPoint: BranchPointType | null
) => {
  if (branchPoint != null && isRemoteURI(branchPoint.original_uri)) {
    return entityNameFromRemoteURI(branchPoint.original_uri);
  } else if (uri != null && isRemoteURI(uri)) {
    return entityNameFromRemoteURI(uri);
  } else {
    return null;
  }
};

export const determineURIIdentifier = (uri: string | null) => {
  // uri = uri?.split('/obj')[0];
  const currNameParts = uri?.split(':');

  const currNamePart = currNameParts
    ? currNameParts[currNameParts.length - 2].split('/')
    : null;
  const currentVersion = currNameParts
    ? currNameParts[currNameParts.length - 1].split('/')[0]
    : null;

  const currName = currNamePart ? currNamePart[currNamePart.length - 1] : null;

  return {
    name: currName,
    version: currentVersion,
  };
};

export const getPathFromURI = (uri: string) => {
  const uriParts = uri.split(':');
  const partContainingVersion = uriParts[uriParts.length - 1];
  const versionParts = partContainingVersion.split('/');
  if (versionParts.length === 1) {
    return null;
  }
  versionParts.shift();
  return versionParts.join('/');
};
