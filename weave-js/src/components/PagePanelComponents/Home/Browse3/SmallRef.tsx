/**
 * Display a link to a Weave op/object.
 */
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
} from '@wandb/weave/react';
import React from 'react';

import {WFDBTableType} from './context';
import {SmallRefObject} from './SmallRefObject';

type SmallRefProps = {
  objRef: ObjectRef;
  wfTable?: WFDBTableType;
  iconOnly?: boolean;
};

export const SmallRef = ({
  objRef,
  wfTable,
  iconOnly = false,
}: SmallRefProps) => {
  if (isWandbArtifactRef(objRef)) {
    // TODO
    return null;
  }
  if (isWeaveObjectRef(objRef)) {
    return (
      <SmallRefObject objRef={objRef} wfTable={wfTable} iconOnly={iconOnly} />
    );
  }
  return <span>[Error: non wandb ref]</span>;
};
