import React from 'react';

import {TraceViewProps} from '../../types';

export const TimelineView: React.FC<TraceViewProps> = ({
  traceTreeFlat,
  selectedCallId,
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