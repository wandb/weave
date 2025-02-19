import React, {useMemo} from 'react';

import {Button} from '../../../../../../../Button';
import {TraceViewProps} from '../../types';
import {formatDuration, formatTimestamp} from './utils';

export const TreeView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const sortedCalls = useMemo(() => {
    return Object.values(traceTreeFlat).sort((a, b) => {
      return a.dfsOrder - b.dfsOrder;
    });
  }, [traceTreeFlat]);

  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">List View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {sortedCalls.map(({id, call}) => {
            const duration = call.ended_at
              ? Date.parse(call.ended_at) - Date.parse(call.started_at)
              : Date.now() - Date.parse(call.started_at);

            return (
              <Button
                key={id}
                variant={id === selectedCallId ? 'secondary' : 'ghost'}
                active={id === selectedCallId}
                onClick={() => onCallSelect(id)}
                className="w-full justify-start text-left">
                <div className="flex w-full flex-col gap-1 overflow-hidden">
                  <div className="truncate font-medium">
                    {call.display_name || call.op_name}
                  </div>
                  <div className="truncate text-xs text-moon-500">
                    Started: {formatTimestamp(call.started_at)}
                    {call.ended_at &&
                      ` • Duration: ${formatDuration(duration)}`}
                  </div>
                </div>
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
