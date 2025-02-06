import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {SmallArtifactRef} from './SmallArtifactRef';
import {SmallWeaveRef} from './SmallWeaveRef';
import {WFDBTableType} from './types';

export const SmallRef: FC<{
  objRef: ObjectRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
}> = ({objRef, wfTable, iconOnly = false}) => {
  if (isWeaveObjectRef(objRef)) {
    return (
      <SmallWeaveRef objRef={objRef} wfTable={wfTable} iconOnly={iconOnly} />
    );
  }
  if (isWandbArtifactRef(objRef)) {
    return <SmallArtifactRef objRef={objRef} />;
  }
  return <div>[Error: non wandb ref]</div>;
};
