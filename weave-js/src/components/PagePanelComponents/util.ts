import getConfig from '../../config';
import {getCookie} from '@wandb/weave/common/util/cookie';
import {NodeOrVoidNode, Type, isAssignableTo} from '@wandb/weave/core';
import fetch from 'isomorphic-unfetch';
import {useEffect, useRef, useState} from 'react';

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

// TODO: currently deprecated, but works in all browsers
declare function btoa(s: string): string;

export const useIsAuthenticated = (skip: boolean = false) => {
  const [isAuth, setIsAuth] = useState<boolean | undefined>(undefined);
  const [authenticationError, setAuthenticationError] = useState<string | null>(
    null
  );
  const anonApiKey = getCookie('anon_api_key');

  const isMounted = useRef(true);

  useEffect(() => {
    if (skip) {
      setIsAuth(false);
    }
    const additionalHeaders: Record<string, string> = {};
    if (anonApiKey != null && anonApiKey !== '') {
      additionalHeaders['x-wandb-anonymous-auth-id'] = btoa(anonApiKey);
    }
    // eslint-disable-next-line wandb/no-unprefixed-urls
    fetch(getConfig().backendWeaveViewerUrl(), {
      credentials: 'include',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...additionalHeaders,
      },
    })
      .then(res => {
        if (!isMounted.current) {
          return;
        }
        if (res.status !== 200) {
          setIsAuth(false);
          setAuthenticationError(`Authentication error: ${res.statusText}`);
          return;
        } else {
          return res.json();
        }
      })
      .then(json => {
        if (!isMounted.current) {
          return;
        }
        const auth = !!(json?.authenticated ?? false);
        setIsAuth(auth);
      })
      .catch(err => {
        if (!isMounted.current) {
          return;
        }
        setIsAuth(false);
      });

    return () => {
      isMounted.current = false;
    };
  }, [anonApiKey, skip]);
  return {isAuthenticated: isAuth, authenticationError};
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
