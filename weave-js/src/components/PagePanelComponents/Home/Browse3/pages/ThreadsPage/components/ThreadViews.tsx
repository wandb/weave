import React from 'react';

import {Button} from '../../../../../../Button';

interface ThreadViewProps {
  onTraceSelect: (traceId: string) => void;
  traces: string[];
  loading: boolean;
  error: Error | null;
}

export const ThreadListView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  loading,
  error,
}) => {
  if (loading) {
    return <div className="p-4">Loading traces...</div>;
  }
  if (error) {
    return <div className="p-4 text-red-500">Error: {error.message}</div>;
  }
  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">Thread List View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant="ghost"
              onClick={() => onTraceSelect(traceId)}
              className="w-full justify-start">
              <span className="truncate">{traceId}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

export const ThreadTimelineView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  loading,
  error,
}) => {
  if (loading) {
    return <div className="p-4">Loading traces...</div>;
  }
  if (error) {
    return <div className="p-4 text-red-500">Error: {error.message}</div>;
  }
  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">Thread Timeline View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant="ghost"
              onClick={() => onTraceSelect(traceId)}
              className="w-full justify-start">
              <span className="truncate">{traceId}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};
