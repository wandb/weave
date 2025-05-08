import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
} from '@wandb/weave/react';
import React, {FC} from 'react';

import {SmallArtifactRef} from './SmallArtifactRef';
import {SmallOpVersionsRef} from './SmallOpVersionsRef';
import {SmallObjectVersionsRef, SmallWeaveRef} from './SmallWeaveRef';

export const SmallRef: FC<{
  objRef: ObjectRef;
  iconOnly?: boolean;
  noLink?: boolean;
}> = ({objRef, iconOnly = false, noLink = false}) => {
  if (isWeaveObjectRef(objRef)) {
    if (objRef.artifactVersion === '*') {
      if (objRef.weaveKind === 'op') {
        return <SmallOpVersionsRef objRef={objRef} />;
      } else {
        return (
          <SmallObjectVersionsRef
            objRef={objRef}
            iconOnly={iconOnly}
            noLink={noLink}
          />
        );
      }
    } else {
      return (
        <SmallWeaveRef objRef={objRef} iconOnly={iconOnly} noLink={noLink} />
      );
    }
  }
  if (isWandbArtifactRef(objRef)) {
    return <SmallArtifactRef objRef={objRef} />;
  }
  return <div>[Error: non wandb ref]</div>;
};
