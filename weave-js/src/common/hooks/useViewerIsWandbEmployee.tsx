import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import {opRootViewer, opUserEmail} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';

export const useIsViewerWandbEmployee = () => {
  // Temp hack to avoid making authenticated queries without needing to
  // We should make the server handle this more gracefully
  const isAuthed = useIsAuthenticated();
  const viewerOp = opRootViewer({});
  const emailOp = opUserEmail({user: viewerOp});

  const {result: viewerEmail} = useNodeValue(emailOp, {skip: !isAuthed});

  if (!viewerEmail || !isAuthed) {
    return false;
  }

  const wandbDomains = ['wandb.ai', 'wandb.com'];
  return !!wandbDomains.find(domain => viewerEmail.endsWith(`@${domain}`));
};
