import {opRootViewer, opUserEmail} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';

export const useIsViewerWandbEmployee = () => {
  const viewerOp = opRootViewer({});
  const emailOp = opUserEmail({user: viewerOp});
  const {result: viewerEmail} = useNodeValue(emailOp);

  if (!viewerEmail) {
    return false;
  }

  const wandbDomains = ['wandb.ai', 'wandb.com'];
  return !!wandbDomains.find(domain => viewerEmail.endsWith(`@${domain}`));
};
