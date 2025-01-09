import React, {useCallback, useEffect, useRef,useState} from 'react';

import {StyledTextArea} from '../PlaygroundPage/StyledTextarea';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {opNiceName} from './Links';

export const EditableCallName: React.FC<{
  call: CallSchema;
  onEditingChange?: (isEditing: boolean) => void;
}> = ({call, onEditingChange}) => {
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
  const [isEditing, setIsEditing] = useState(false);

  // 1) Create a ref so we can manually call adjustHeight().
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setCurrNameToDisplay(nameToDisplay);
  }, [nameToDisplay]);

  useEffect(() => {
    onEditingChange?.(isEditing);

    // 2) Fire your height recalculation specifically when going from
    //    !isEditing to isEditing (or vice versa).
    if (isEditing && textAreaRef.current) {
      const el = textAreaRef.current;
      // Fixed height for the text area, firing the effect too early.
      setTimeout(() => {
        el.style.height = 'auto';
        const newHeight = el.scrollHeight;

        el.style.height = `${newHeight}px`;
        el.style.overflowY = 'hidden';
      }, 0);
    }
  }, [isEditing, onEditingChange]);

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
      setIsEditing(false);
    },
    [defaultDisplayName, call, displayNameIsEmpty, callRename]
  );

  if (!isEditing) {
    return (
      <div
        className="cursor-pointer hover:bg-moon-100 dark:hover:bg-moon-800 px-2 py-1 rounded"
        onClick={() => setIsEditing(true)}>
        {currNameToDisplay}
      </div>
    );
  }

  return (
    <div className='w-full'>
      <StyledTextArea
        ref={textAreaRef}
        value={currNameToDisplay}
        onChange={e => setCurrNameToDisplay(e.target.value)}
        onBlur={() => saveName(currNameToDisplay)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            saveName(currNameToDisplay);
          } else if (e.key === 'Escape') {
            setIsEditing(false);
            setCurrNameToDisplay(nameToDisplay);
          }
        }}
        placeholder={defaultDisplayName}
        autoGrow={true}
        rows={1}
        className='w-full'
      />
    </div>
  );
};
