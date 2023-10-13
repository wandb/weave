import {
  constNone,
  callOpVeryUnsafe,
  constString,
  maybe,
  typedDict,
  opRef,
  opRefBranchPoint,
} from '@wandb/weave/core';
import {useClientContext, useNodeValue} from '@wandb/weave/react';
import {useCallback, useMemo, useState} from 'react';
import {BranchPointType, isLocalURI} from './util';

export const useBranchPointFromURIString = (
  uri: string | null
): null | BranchPointType => {
  const hasRemoteNode = useMemo(
    () =>
      uri == null || !isLocalURI(uri)
        ? constNone()
        : (opRefBranchPoint(
            {
              ref: opRef(
                {
                  uri: constString(uri),
                },
              ),
            },
          )),
    [uri]
  );
  const hasRemoteVal = useNodeValue(hasRemoteNode);
  return hasRemoteVal.loading ? null : hasRemoteVal.result;
};

export const usePreviousVersionFromURIString = (
  uri: string | null
): null | string => {
  const previousURINode = useMemo(
    () =>
      uri == null || !isLocalURI(uri)
        ? constNone()
        : (callOpVeryUnsafe(
            'FilesystemArtifact-previousURI',
            {
              artifact: callOpVeryUnsafe(
                'FilesystemArtifact-rootFromURI',
                {
                  uri: constString(uri),
                },
                {type: 'FilesystemArtifact' as any}
              ) as any,
            },
            {type: 'string' as any}
          ) as any),
    [uri]
  );
  const hasRemoteVal = useNodeValue(previousURINode);
  return hasRemoteVal.loading ? null : hasRemoteVal.result;
};

const useGetCodeFromURI = (uri: string | null) => {
  const context = useClientContext();
  const client = context.client;
  if (client == null) {
    throw new Error('client not initialized!');
  }

  return useCallback(() => {
    const codeStringNode =
      uri == null
        ? constNone()
        : (callOpVeryUnsafe(
            '__internal__-generateCodeForObject',
            {
              uri: callOpVeryUnsafe(
                'get',
                {
                  uri: constString(uri),
                },
                'any' as const
              ),
            },
            'string' as const
          ) as any);
    return client.query(codeStringNode);
  }, [client, uri]);
};

export const useCopyCodeFromURI = (maybeUri: string | null) => {
  const getCode = useGetCodeFromURI(maybeUri);
  const [copyStatus, setCopyStatus] = useState<
    'ready' | 'loading' | 'success' | 'error'
  >('ready');
  const onCopy = useCallback(() => {
    setCopyStatus('loading');
    return getCode()
      .then(codeString => navigator.clipboard.writeText(codeString))
      .then(() => {
        setCopyStatus('success');
      })
      .catch(e => {
        setCopyStatus('error');
        console.error(e);
      })
      .finally(() => {
        setTimeout(() => {
          setCopyStatus('ready');
        }, 750);
      });
  }, [getCode]);

  return {
    copyStatus,
    onCopy,
  };
};
