import React from 'react';

import {TraceTreeFlat} from '../../types';
import {Container} from './styles';
import {StackContextProvider} from './context';
import {StackScrubber} from './components/StackScrubber';
import {StackBreadcrumb} from './components/StackBreadcrumb';
import {
  TimelineScrubber,
  PeerScrubber,
  SiblingScrubber,
} from './components/scrubbers';

interface TraceScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

export const TraceScrubber: React.FC<TraceScrubberProps> = (props) => {
  return (
    <StackContextProvider traceTreeFlat={props.traceTreeFlat}>
      <Container>
        <TimelineScrubber {...props} />
        <PeerScrubber {...props} />
        <SiblingScrubber {...props} />
        <StackScrubber {...props} />
        <StackBreadcrumb {...props} />
      </Container>
    </StackContextProvider>
  );
}; 