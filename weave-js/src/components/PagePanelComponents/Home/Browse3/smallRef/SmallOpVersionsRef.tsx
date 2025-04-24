import {IconNames} from '@wandb/weave/components/Icon';
import React from 'react';

import {WeaveObjectRef} from '../../../../../react';
import {useWeaveflowRouteContext} from '../context';
import {SmallRefLoaded} from './SmallRefLoaded';
import {getObjectVersionLabel} from './SmallWeaveRef';

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
