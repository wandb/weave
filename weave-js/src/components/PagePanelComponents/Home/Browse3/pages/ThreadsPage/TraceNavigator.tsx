import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

import {TraceScrubber} from './components/TraceScrubber';
import {StackBreadcrumb} from './components/TraceScrubber/components/StackBreadcrumb';
import {StackContextProvider} from './components/TraceScrubber/context';
import {TraceTreeFlat} from './types';
import {getTraceView, traceViews} from './viewRegistry';

export const TraceNavigator = ({
  traceTreeFlat,
  selectedCallId,
  setSelectedCallId,
}: {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId: string | undefined;
  setSelectedCallId: React.Dispatch<React.SetStateAction<string | undefined>>;
}) => {
  const [traceViewId, setTraceViewId] = useState(traceViews[0].id);
  const TraceViewComponent = getTraceView(traceViewId).component;
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="truncate text-sm font-semibold">Trace View</h2>
        <div className="flex items-center gap-3">
          {traceViews.map(view => (
            <Button
              key={view.id}
              variant={traceViewId === view.id ? 'primary' : 'ghost'}
              onClick={() => setTraceViewId(view.id)}
              icon={view.icon}
              size="small"
              className="!p-3"
              title={view.label}>
              <span className="sr-only">{view.label}</span>
            </Button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col">
          {Object.keys(traceTreeFlat).length > 0 && (
            <StackContextProvider
              traceTreeFlat={traceTreeFlat}
              selectedCallId={selectedCallId}>
              <StackBreadcrumb
                traceTreeFlat={traceTreeFlat}
                selectedCallId={selectedCallId}
                onCallSelect={setSelectedCallId}
              />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex-1 overflow-auto">
                  <TraceViewComponent
                    traceTreeFlat={traceTreeFlat}
                    selectedCallId={selectedCallId}
                    onCallSelect={setSelectedCallId}
                  />
                </div>
                {getTraceView(traceViewId).showScrubber && (
                  <TraceScrubber
                    traceTreeFlat={traceTreeFlat}
                    selectedCallId={selectedCallId}
                    onCallSelect={setSelectedCallId}
                  />
                )}
              </div>
            </StackContextProvider>
          )}
        </div>
      </div>
    </div>
  );
};
