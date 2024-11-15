import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {FC, useCallback, useContext, useEffect} from 'react';
import {useHistory} from 'react-router-dom';

import {TableRowSelectionContext} from '../../../Browse3';
import {TRACETREE_PARAM, useWeaveflowCurrentRouteContext} from '../../context';
import {isEvaluateOp} from '../common/heuristics';
import {useURLSearchParamsDict} from '../util';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const PaginationControls: FC<{
  call: CallSchema;
  path?: string;
}> = ({call, path}) => {
  // Call navigation by arrow keys and buttons
  const {getNextRowId, getPreviousRowId, rowIdInTable} = useContext(
    TableRowSelectionContext
  );
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const query = useURLSearchParamsDict();
  const showTraceTree =
    TRACETREE_PARAM in query
      ? query[TRACETREE_PARAM] === '1'
      : !isEvaluateOp(call.spanName);

  const onNextCall = useCallback(() => {
    const nextCallId = getNextRowId?.(call.callId);
    if (nextCallId) {
      history.replace(
        currentRouter.callUIUrl(
          call.entity,
          call.project,
          call.traceId,
          nextCallId,
          path,
          showTraceTree
        )
      );
    }
  }, [call, currentRouter, history, path, showTraceTree, getNextRowId]);
  const onPreviousCall = useCallback(() => {
    const previousRowId = getPreviousRowId?.(call.callId);
    if (previousRowId) {
      history.replace(
        currentRouter.callUIUrl(
          call.entity,
          call.project,
          call.traceId,
          previousRowId,
          path,
          showTraceTree
        )
      );
    }
  }, [call, currentRouter, history, path, showTraceTree, getPreviousRowId]);
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

  const disabled = !rowIdInTable(call.callId);
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
