import EditableField from '@wandb/weave/common/components/EditableField';
import React, {useCallback} from 'react';
import {useEffect, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';

export const EditableCallName: React.FC<{
  opName: string;
  entity: string;
  project: string;
  callId: string;
}> = ({opName, entity, project, callId}) => {
  const {useCallRenameFunc} = useWFHooks();
  const callRename = useCallRenameFunc();
  const [curOpName, setCurOpName] = useState(opName);

  // Listen to changes in provided opName, for components that are not unmounted
  // before the opName changes.
  useEffect(() => {
    setCurOpName(opName);
  }, [opName]);

  const saveName = useCallback(
    (newName: string) => {
      callRename(entity, project, callId, newName);
      setCurOpName(newName);
    },
    [callRename, entity, project, callId]
  );

  return (
    <EditableField
      value={curOpName}
      onFinish={saveName}
      placeholder={curOpName}
      updateValue={true}
    />
  );
};
