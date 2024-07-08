import EditableField from '@wandb/weave/common/components/EditableField';
import React, {useCallback, useEffect, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {opNiceName} from './Links';

export const EditableCallName: React.FC<{
  call: CallSchema;
  editableFieldRef: React.RefObject<EditableField>;
}> = ({call, editableFieldRef}) => {
  const defaultDisplayName = opNiceName(call.spanName);
  const displayNameIsEmpty =
    call.displayName == null || call.displayName === '';
  // The name to display is the displayName if it is not empty, otherwise
  // it is the defaultDisplayName.
  const nameToDisplay = displayNameIsEmpty
    ? defaultDisplayName
    : call.displayName!;

  const {useCallUpdateFunc: useCallRenameFunc} = useWFHooks();
  const callRename = useCallRenameFunc();
  const [currNameToDisplay, setCurrNameToDisplay] = useState(nameToDisplay);

  // Listen to changes in provided opName, for components that are not unmounted
  // before the opName changes.
  useEffect(() => {
    setCurrNameToDisplay(nameToDisplay);
  }, [nameToDisplay]);

  const saveName = useCallback(
    (newName: string) => {
      // In the case that `newName` is empty or equal to the default name,
      // then we want to set the name to empty string.
      if (newName === '' || newName === defaultDisplayName) {
        setCurrNameToDisplay(defaultDisplayName);
        if (!displayNameIsEmpty) {
          callRename(call.entity, call.project, call.callId, '');
        }
      } else if (newName !== call.displayName) {
        // Else, update the name only if it is different from the current name.
        setCurrNameToDisplay(newName);
        callRename(call.entity, call.project, call.callId, newName);
      }
    },
    [defaultDisplayName, call, displayNameIsEmpty, callRename]
  );

  return (
    <EditableField
      ref={editableFieldRef}
      value={currNameToDisplay}
      onFinish={saveName}
      placeholder={defaultDisplayName}
      updateValue={true}
    />
  );
};
