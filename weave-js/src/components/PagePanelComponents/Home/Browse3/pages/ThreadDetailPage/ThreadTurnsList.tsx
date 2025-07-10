import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {FC, useCallback, useContext, useMemo} from 'react';
import {useHistory} from 'react-router-dom';
import {clsx} from 'yet-another-react-lightbox';

import {
  useEntityProject,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StatusChip} from '../common/StatusChip';
import {ComputedCallStatusType} from '../wfReactInterface/traceServerClientTypes';
import {
  parseSpanName,
  traceCallStatusCode,
  useThreadTurns,
} from '../wfReactInterface/tsDataModelHooks';

export interface Turn {
  id: string;
  status: ComputedCallStatusType;
  input?: string;
  opName: string;
}

export interface ThreadTurnsListProps {
  turnsState: ReturnType<typeof useThreadTurns>['turnsState'];
  selectedTurnId?: string;
  onTurnSelect?: (index: number) => void;
}

/**
 * ThreadTurnsList displays a list of turns in a thread.
 *
 * Shows each turn with its number, status, and input preview.
 * Supports selection and click handlers for turn navigation.
 *
 * @param turnsState - State object containing turns data from useThreadTurns hook
 * @param selectedTurnId - ID of the currently selected turn
 * @param onTurnSelect - Callback when a turn is selected, receives the turn index
 *
 * @example
 * <ThreadTurnsList
 *   turnsState={turnsState}
 *   selectedTurnId="turn_1"
 *   onTurnSelect={(index) => console.log('Selected turn index:', index)}
 * />
 */
export const ThreadTurnsList: FC<ThreadTurnsListProps> = ({
  turnsState,
  selectedTurnId,
  onTurnSelect,
}) => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const {entity, project} = useEntityProject();
  const {setPreviousUrl, isPeeking} = useContext(WeaveflowPeekContext);
  const history = useHistory();

  const handleTurnClick = useCallback(
    (index: number) => {
      if (onTurnSelect) {
        onTurnSelect(index);
      }
    },
    [onTurnSelect]
  );

  const handleTraceClick = useCallback(
    (e: React.MouseEvent, turnId: string) => {
      e.stopPropagation(); // Prevent triggering the turn click

      if (setPreviousUrl && isPeeking) {
        // Only store previousUrl if we're in a peek view
        const currentUrl = window.location.pathname + window.location.search;
        setPreviousUrl(currentUrl);
      }

      // If we're already in a peek view, use peekingRouter to open another peek
      // If we're not in a peek view, use baseRouter for normal navigation
      const router = isPeeking ? peekingRouter : baseRouter;
      const link = router.callUIUrl(
        entity,
        project,
        '',
        turnId,
        turnId,
        false,
        false
      );

      history.push(link);
    },
    [
      setPreviousUrl,
      isPeeking,
      peekingRouter,
      baseRouter,
      entity,
      project,
      history,
    ]
  );

  const turns = useMemo(() => {
    if (turnsState.loading || !turnsState.value) {
      return [];
    }

    return turnsState.value.turnCalls.map((traceCall): Turn => {
      // Convert inputs object to a string preview
      const inputPreview = traceCall.inputs
        ? JSON.stringify(traceCall.inputs).substring(0, 100) + '...'
        : undefined;

      return {
        id: traceCall.id,
        status: traceCallStatusCode(traceCall),
        input: inputPreview,
        opName: parseSpanName(traceCall.op_name),
      };
    });
  }, [turnsState]);

  const firstTurnIndex = useMemo(() => {
    if (turnsState.value) {
      const totalTurns = turnsState.value.thread.turn_count;
      const firstTurnIndex = totalTurns - turnsState.value.turnCalls.length;
      return firstTurnIndex;
    }
    return 0;
  }, [turnsState]);

  // Show a loading state if the turnsState is loading
  if (turnsState.loading) {
    return (
      <div className="flex w-full items-center justify-center">
        <LoadingDots />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      {firstTurnIndex !== 0 && (
        <div className="flex items-center justify-center text-sm text-moon-800">
          ... Turn 1 to {firstTurnIndex} are omitted ...
        </div>
      )}
      {turns.map((turn, index) => {
        const isSelected = turn.id === selectedTurnId;

        return (
          <div
            key={turn.id}
            className={clsx(
              'group relative h-64 cursor-pointer border border-b border-solid border-moon-150 p-12 px-8 py-7 transition-colors',
              isSelected && 'bg-moon-100',
              !isSelected && 'hover:bg-moon-100'
            )}
            onClick={() => handleTurnClick(index)}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6 text-sm text-moon-800">
                <span className=" flex h-18 w-18 items-center justify-center rounded-[20px] bg-moon-200 font-bold ">
                  {firstTurnIndex + index + 1}
                </span>
                <span className="truncate font-semibold">{turn.opName}</span>
              </div>
              <div>
                <StatusChip value={turn.status} iconOnly />
              </div>
            </div>
            {turn.input && (
              <div className="text-gray-500 mt-4 truncate text-sm">
                {turn.input}
              </div>
            )}

            {/* Floating button - only visible on hover */}
            <Button
              size="small"
              variant="secondary"
              className="absolute bottom-2 right-2 bg-moon-150 opacity-0 shadow-lg transition-opacity duration-200 hover:bg-blue-300 group-hover:opacity-100"
              onClick={e => handleTraceClick(e, turn.id)}
              title="Turn actions"
              endIcon={'open-new-tab'}>
              Trace
            </Button>
          </div>
        );
      })}
    </div>
  );
};
