import {IconNames} from '@wandb/weave/components/Icon';
import {useWeaveflowRouteContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {SmallRefLoaded} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRefLoaded';
import {getObjectVersionLabel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallWeaveRef';
import {WeaveObjectRef} from '@wandb/weave/react';
import React from 'react';

export const SmallOpVersionsRef = ({objRef}: {objRef: WeaveObjectRef}) => {
  const {peekingRouter} = useWeaveflowRouteContext();
  const url = peekingRouter.opVersionsUIUrl(
    objRef.entityName,
    objRef.projectName,
    {
      opName: objRef.artifactName,
    }
  );
  const label = getObjectVersionLabel(objRef, -1);
  return (
    <SmallRefLoaded
      icon={IconNames.JobProgramCode}
      label={label}
      url={url}
      error={null}
    />
  );
};
