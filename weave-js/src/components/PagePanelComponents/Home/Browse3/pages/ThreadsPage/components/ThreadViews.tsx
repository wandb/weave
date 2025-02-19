import React from 'react';

import {Button} from '../../../../../../Button';
import {ThreadViewProps} from '../types';

export const ThreadListView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  selectedTraceId,
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
      <div className="h-[100%] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant={traceId === selectedTraceId ? 'secondary' : 'ghost'}
              active={traceId === selectedTraceId}
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
  selectedTraceId,
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
      <div className="h-[100%] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant={traceId === selectedTraceId ? 'primary' : 'ghost'}
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
