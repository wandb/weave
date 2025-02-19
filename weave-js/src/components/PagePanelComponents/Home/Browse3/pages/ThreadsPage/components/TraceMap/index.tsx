import React from 'react';

import {TraceTreeFlat} from '../../types';
import {Container} from './styles';

interface TraceMapProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

export const TraceMap: React.FC<TraceMapProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  return (
    <Container>
      <div className="flex items-center justify-between border-b border-moon-250 px-4 py-2">
        <h3 className="text-sm font-medium">Trace Map</h3>
        <div className="text-xs text-moon-500">
          {Object.keys(traceTreeFlat).length} nodes
        </div>
      </div>
      <div className="h-[200px] overflow-hidden p-4">
        {/* Visualization will go here */}
        <div className="flex h-full items-center justify-center text-moon-500">
          Trace visualization coming soon...
        </div>
      </div>
    </Container>
  );
}; 