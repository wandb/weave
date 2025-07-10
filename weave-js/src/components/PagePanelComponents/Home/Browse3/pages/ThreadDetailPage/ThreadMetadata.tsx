import React, {FC, useMemo} from 'react';

import {useThreadTurns} from '../wfReactInterface/tsDataModelHooks';

export interface ThreadMetadataProps {
  turnsState: ReturnType<typeof useThreadTurns>['turnsState'];
}

/**
 * ThreadMetadata displays calculated metrics for a thread.
 *
 * Shows turn count, p50 latency, and p99 latency in a clean grid layout.
 *
 * @param turnsState - State object containing turns data from useThreadTurns hook
 *
 * @example
 * <ThreadMetadata turnsState={turnsState} />
 */
export const ThreadMetadata: FC<ThreadMetadataProps> = ({turnsState}) => {
  const metrics = useMemo(() => {
    if (!turnsState.value || turnsState.loading) {
      return {
        turnCount: 0,
        p50Latency: '-',
        p99Latency: '-',
      };
    }

    const turns = turnsState.value;
    const turnCount = turns.thread.turn_count;

    const p50Latency = `${(
      (turns.thread.p50_turn_duration_ms ?? 0) / 1e3
    ).toFixed(3)}s`;
    const p99Latency = `${(
      (turns.thread.p99_turn_duration_ms ?? 0) / 1e3
    ).toFixed(3)}s`;

    return {
      turnCount,
      p50Latency,
      p99Latency,
    };
  }, [turnsState]);

  return (
    <div className="grid h-72 w-fit flex-shrink-0 grid-flow-col grid-cols-[auto_auto_auto] grid-rows-2 gap-x-24 border-b border-solid border-moon-150 px-16 py-12">
      <span className="text-sm font-medium text-moon-600">Turns</span>
      <span className="truncate text-base font-semibold text-moon-800">
        {metrics.turnCount}
      </span>
      <span className="text-sm font-medium text-moon-600">p50 latency</span>
      <span className="truncate text-base font-semibold text-moon-800">
        {metrics.p50Latency}
      </span>
      <span className="text-sm font-medium text-moon-600">p99 latency</span>
      <span className="truncate text-base font-semibold text-moon-800">
        {metrics.p99Latency}
      </span>
    </div>
  );
};
