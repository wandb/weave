import {
  constNone,
  callOpVeryUnsafe,
  constString,
  maybe,
  typedDict,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';
import {BranchPointType, isLocalURI} from './util';

export const useBranchPointFromURIString = (
  uri: string | null
): null | BranchPointType => {
  const hasRemoteNode = useMemo(
    () =>
      uri == null || !isLocalURI(uri)
        ? constNone()
        : (callOpVeryUnsafe(
            'Ref-branch_point',
            {
              ref: callOpVeryUnsafe(
                'ref',
                {
                  uri: constString(uri),
                },
                {type: 'FilesystemArtifactRef' as any}
              ),
            },
            maybe(typedDict({}))
          ) as any),
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
