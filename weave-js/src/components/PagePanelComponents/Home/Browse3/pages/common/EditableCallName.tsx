import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useEffect, useRef, useState} from 'react';

import {StyledTextArea} from '../../StyledTextarea';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {opNiceName} from './opNiceName';

export const EditableCallName: React.FC<{
  call: CallSchema;
}> = ({call}) => {
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

  // Create a ref so we can manually call adjustHeight().
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrNameToDisplay(nameToDisplay);
  }, [nameToDisplay]);

  useEffect(() => {
    // Fire height recalculation specifically when going from isEditing.
    if (isEditing && textAreaRef.current) {
      const el = textAreaRef.current;
      // Fixes issue with size refreshing too quickly since we use scrollHeight for autoGrow.
      setTimeout(() => {
        el.style.height = 'auto';
        const newHeight = el.scrollHeight;
        el.style.height = `${newHeight}px`;
        el.style.overflowY = 'hidden';
        // Focus and move the cursor to the end of the text content
        el.focus();
        const textLength = el.value.length;
        el.setSelectionRange(textLength, textLength);
      }, 0);
    }
  }, [isEditing]);

  const saveName = useCallback(
    (newName: string) => {
      // In the case that `newName` is empty or equal to the default name,
      // then we want to set the name to empty string.
      if (newName === '' || newName === defaultDisplayName) {
        setCurrNameToDisplay(defaultDisplayName);
        if (!displayNameIsEmpty) {
          callRename({
            entity: call.entity,
            project: call.project,
            callID: call.callId,
            newName: '',
          });
        }
      } else if (newName !== call.displayName) {
        // Else, update the name only if it is different from the current name.
        setCurrNameToDisplay(newName);
        callRename({
          entity: call.entity,
          project: call.project,
          callID: call.callId,
          newName,
        });
      }
      setIsEditing(false);
    },
    [defaultDisplayName, call, displayNameIsEmpty, callRename]
  );

  useEffect(() => {
    if (!isEditing) {
      return;
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        saveName(currNameToDisplay);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isEditing, saveName, currNameToDisplay]);

  if (!isEditing) {
    return (
      <Tailwind>
        <div className="group flex items-center">
          <div
            title={`Click to edit: ${currNameToDisplay}`}
            className="flex min-w-[150px] cursor-pointer items-center overflow-hidden rounded px-[8px] py-[4px] hover:bg-moon-100 dark:hover:bg-moon-800"
            style={{
              display: '-webkit-box',
              WebkitBoxOrient: 'vertical',
              WebkitLineClamp: 2,
              lineClamp: 2 /* Not supported in all browsers yet, but added for future compatibility */,
            }}
            onClick={() => setIsEditing(true)}>
            {currNameToDisplay}
          </div>
          <div>
            <Icon
              name="pencil-edit"
              width={16}
              height={16}
              className="ml-[8px] min-w-[16px] text-moon-500 opacity-0 group-hover:opacity-100"
            />
          </div>
        </div>
      </Tailwind>
    );
  }

  return (
    <Tailwind>
      <div className="w-full" ref={containerRef}>
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
          className="w-full min-w-[150px] px-[8px] py-[4px]"
        />
      </div>
    </Tailwind>
  );
};
