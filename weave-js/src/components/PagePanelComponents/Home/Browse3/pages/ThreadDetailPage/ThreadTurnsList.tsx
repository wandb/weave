import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import React, {FC, useMemo} from 'react';
import {clsx} from 'yet-another-react-lightbox';

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
  const handleTurnClick = (index: number) => {
    if (onTurnSelect) {
      onTurnSelect(index);
    }
  };

  const turns = useMemo(() => {
    if (turnsState.loading || !turnsState.value) {
      return [];
    }

    return turnsState.value.map((traceCall): Turn => {
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
      {turns.map((turn, index) => {
        const isSelected = turn.id === selectedTurnId;
        return (
          <div
            key={turn.id}
            className={clsx(
              'h-64 cursor-pointer border border-b border-solid border-moon-150 p-12 px-8 py-7 transition-colors',
              isSelected && 'bg-moon-100',
              !isSelected && 'hover:bg-moon-100'
            )}
            onClick={() => handleTurnClick(index)}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6 text-sm text-moon-800">
                <span className=" flex h-18 w-18 items-center justify-center rounded-[20px] bg-moon-200 font-bold ">
                  {index + 1}
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
          </div>
        );
      })}
    </div>
  );
};
