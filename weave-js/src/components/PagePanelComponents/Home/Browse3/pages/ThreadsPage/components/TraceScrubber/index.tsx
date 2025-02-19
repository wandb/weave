import React from 'react';

import {TraceTreeFlat} from '../../types';
import {
  PeerScrubber,
  SiblingScrubber,
  TimelineScrubber,
} from './components/scrubbers';
import {StackBreadcrumb} from './components/StackBreadcrumb';
import {StackScrubber} from './components/StackScrubber';
import {StackContextProvider} from './context';
import {Container} from './styles';

interface TraceScrubberProps {
  traceTreeFlat: TraceTreeFlat;
  selectedCallId?: string;
  onCallSelect: (callId: string) => void;
}

export const TraceScrubber: React.FC<TraceScrubberProps> = props => {
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
