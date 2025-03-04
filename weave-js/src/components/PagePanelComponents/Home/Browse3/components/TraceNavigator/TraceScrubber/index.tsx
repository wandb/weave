import React from 'react';

import {BaseScrubberProps} from './components/BaseScrubber';
import {
  PeerScrubber,
  SiblingScrubber,
  StackScrubber,
  TimelineScrubber,
} from './components/scrubbers';
import {Container} from './styles';

export type ScrubberOption = 'timeline' | 'peer' | 'sibling' | 'stack';

const TraceScrubber: React.FC<
  BaseScrubberProps & {
    allowedScrubbers?: ScrubberOption[];
  }
> = props => {
  const showScrubber = (scrubber: ScrubberOption) => {
    if (!props.allowedScrubbers) {
      return true;
    }
    return props.allowedScrubbers.includes(scrubber);
  };
  return (
    <Container>
      {showScrubber('timeline') && <TimelineScrubber {...props} />}
      {showScrubber('peer') && <PeerScrubber {...props} />}
      {showScrubber('sibling') && <SiblingScrubber {...props} />}
      {showScrubber('stack') && <StackScrubber {...props} />}
    </Container>
  );
};

export default TraceScrubber;
