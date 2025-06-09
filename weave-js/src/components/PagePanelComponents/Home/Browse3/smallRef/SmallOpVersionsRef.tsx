import {IconNames} from '@wandb/weave/components/Icon';
import {useWeaveflowRouteContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {SmallRefLoaded} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRefLoaded';
import {getObjectVersionLabel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallWeaveRef';
import {WeaveObjectRef} from '@wandb/weave/react';
import React, {useMemo} from 'react';

export const SmallOpVersionsRef = ({objRef}: {objRef: WeaveObjectRef}) => {
  const {peekingRouter} = useWeaveflowRouteContext();

  const url = useMemo(
    () =>
      peekingRouter.opVersionsUIUrl(objRef.entityName, objRef.projectName, {
        opName: objRef.artifactName,
      }),
    [objRef, peekingRouter]
  );

  const label = useMemo(() => getObjectVersionLabel(objRef, -1), [objRef]);

  return (
    <SmallRefLoaded
      icon={IconNames.JobProgramCode}
      label={label}
      url={url}
      error={null}
    />
  );
};
