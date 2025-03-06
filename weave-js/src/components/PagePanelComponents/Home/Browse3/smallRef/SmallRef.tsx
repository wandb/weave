import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {SmallArtifactRef} from './SmallArtifactRef';
import {SmallWeaveRef} from './SmallWeaveRef';

export const SmallRef: FC<{
  objRef: ObjectRef;
  iconOnly?: boolean;
  noLink?: boolean;
}> = ({objRef, iconOnly = false, noLink = false}) => {
  if (isWeaveObjectRef(objRef)) {
    return (
      <SmallWeaveRef objRef={objRef} iconOnly={iconOnly} noLink={noLink} />
    );
  }
  if (isWandbArtifactRef(objRef)) {
    return <SmallArtifactRef objRef={objRef} />;
  }
  return <div>[Error: non wandb ref]</div>;
};
