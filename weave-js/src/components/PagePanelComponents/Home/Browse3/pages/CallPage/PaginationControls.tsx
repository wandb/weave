import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {FC, useCallback, useContext, useEffect} from 'react';

import {TableRowSelectionContext} from '../../../TableRowSelectionContext';

export const PaginationControls: FC<{
  callId: string;
  setRootCallId: (callId: string) => void;
}> = ({callId, setRootCallId}) => {
  // Call navigation by arrow keys and buttons
  const {getNextRowId, getPreviousRowId, rowIdInTable} = useContext(
    TableRowSelectionContext
  );

  const onNextCall = useCallback(() => {
    const nextCallId = getNextRowId?.(callId);
    if (nextCallId) {
      setRootCallId(nextCallId);
    }
  }, [getNextRowId, callId, setRootCallId]);
  const onPreviousCall = useCallback(() => {
    const previousRowId = getPreviousRowId?.(callId);
    if (previousRowId) {
      setRootCallId(previousRowId);
    }
  }, [getPreviousRowId, callId, setRootCallId]);
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'ArrowDown' && event.shiftKey) {
        onNextCall();
      } else if (event.key === 'ArrowUp' && event.shiftKey) {
        onPreviousCall();
      }
    },
    [onNextCall, onPreviousCall]
  );
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);

  const disabled = !rowIdInTable(callId);
  const disabledMsg = 'Paging is disabled after navigating to a parent call';

  return (
    <Box>
      <Button
        icon="sort-ascending"
        tooltip={disabled ? disabledMsg : 'Previous call. (Shift + Arrow Up)'}
        variant="ghost"
        onClick={onPreviousCall}
        className="mr-2"
        disabled={disabled}
      />
      <Button
        icon="sort-descending"
        tooltip={disabled ? disabledMsg : 'Next call. (Shift + Arrow Down)'}
        variant="ghost"
        onClick={onNextCall}
        disabled={disabled}
      />
    </Box>
  );
};
