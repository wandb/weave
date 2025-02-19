import React, {useMemo} from 'react';

import {Button} from '../../../../../../Button';
import {TraceTreeFlat} from '../types';

interface TraceViewProps {
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}

export const TraceListView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  onCallSelect,
}) => {
  const sortedCalls = useMemo(() => {
    return Object.values(traceTreeFlat).sort((a, b) => {
      const aStartedAt = Date.parse(a.call.started_at);
      const bStartedAt = Date.parse(b.call.started_at);
      return bStartedAt - aStartedAt;
    });
  }, [traceTreeFlat]);

  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">List View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {sortedCalls.map(({call}) => (
            <Button
              key={call.id}
              variant="ghost"
              onClick={() => onCallSelect(call.id)}
              className="w-full justify-start text-left">
              <div className="flex w-full flex-col gap-1 overflow-hidden">
                <div className="truncate font-medium">
                  {call.display_name || call.op_name}
                </div>
                <div className="truncate text-xs text-moon-500">
                  Started: {new Date(call.started_at).toLocaleString()}
                  {call.ended_at &&
                    ` • Duration: ${(
                      (Date.parse(call.ended_at) -
                        Date.parse(call.started_at)) /
                      1000
                    ).toFixed(2)}s`}
                </div>
              </div>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

export const TraceTimelineView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  onCallSelect,
}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Timeline View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        timeline
      </pre>
    </div>
  );
};

export const TraceTreeView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  onCallSelect,
}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Tree View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        tree
      </pre>
    </div>
  );
};

export const TraceTableView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  onCallSelect,
}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Table View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        table
      </pre>
    </div>
  );
};
