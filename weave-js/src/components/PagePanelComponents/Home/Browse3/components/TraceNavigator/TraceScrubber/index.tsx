import React from 'react';

import {BaseScrubberProps} from './components/BaseScrubber';
import {
  PeerScrubber,
  SiblingScrubber,
  StackScrubber,
  TimelineScrubber,
} from './components/scrubbers';
import {Container} from './styles';

const TraceScrubber: React.FC<BaseScrubberProps> = props => {
  return (
    <Container>
      <TimelineScrubber {...props} />
      <PeerScrubber {...props} />
      <SiblingScrubber {...props} />
      <StackScrubber {...props} />
    </Container>
  );
};

export default TraceScrubber;
