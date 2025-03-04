import React from 'react';

import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';

interface CallDetailSectionProps {
  call: TraceCallSchema | undefined;
  sectionTitle: string;
}

export const CallDetailSection: React.FC<CallDetailSectionProps> = ({
  call,
  sectionTitle,
}) => {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="truncate text-sm font-semibold">{sectionTitle}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-8">
        {call ? (
          <pre className="overflow-x-auto whitespace-pre-wrap text-sm text-moon-500">
            {JSON.stringify(call, null, 2)}
          </pre>
        ) : (
          <div className="text-moon-500">No call selected</div>
        )}
      </div>
    </div>
  );
};
