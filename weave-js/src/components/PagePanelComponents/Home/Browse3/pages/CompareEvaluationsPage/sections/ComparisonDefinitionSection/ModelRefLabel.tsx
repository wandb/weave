/**
 * Takes a ref string like "weave:///entity/project/op/op_name:digest"
 * and displays the model name and numeric version.
 */

import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useMemo} from 'react';

import {useWFHooks} from '../../../wfReactInterface/context';
import {ObjectVersionKey} from '../../../wfReactInterface/wfDataModelHooksInterface';

export const ModelRefLabel: React.FC<{modelRef: string}> = props => {
  const {useObjectVersion} = useWFHooks();
  const objRef = useMemo(
    () => parseRef(props.modelRef) as WeaveObjectRef,
    [props.modelRef]
  );
  const objVersionKey = useMemo(() => {
    return {
      scheme: 'weave',
      entity: objRef.entityName,
      project: objRef.projectName,
      weaveKind: objRef.weaveKind,
      objectId: objRef.artifactName,
      versionHash: objRef.artifactVersion,
      path: '',
      refExtra: objRef.artifactRefExtra,
    } as ObjectVersionKey;
  }, [
    objRef.artifactName,
    objRef.artifactRefExtra,
    objRef.artifactVersion,
    objRef.entityName,
    objRef.projectName,
    objRef.weaveKind,
  ]);
  const objectVersion = useObjectVersion({key: objVersionKey});
  return (
    <span className="ml-2">
      {objectVersion.result?.objectId}:v{objectVersion.result?.versionIndex}
    </span>
  );
};
