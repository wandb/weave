import React, {useState} from 'react';
import {Icon} from '@wandb/weave/components/Icon';

import {BaseScrubberProps} from './components/BaseScrubber';
import {
  CodePathScrubber,
  PeerScrubber,
  SiblingScrubber,
  StackScrubber,
  TimelineScrubber,
} from './components/scrubbers';
import {Container, CollapseButton, CollapseWrapper} from './styles';

export type ScrubberOption =
  | 'timeline'
  | 'peer'
  | 'sibling'
  | 'stack'
  | 'codePath';

const TraceScrubber: React.FC<
  BaseScrubberProps & {
    allowedScrubbers?: ScrubberOption[];
  }
> = props => {
  const [isCollapsed, setIsCollapsed] = useState(true);

  const showScrubber = (scrubber: ScrubberOption) => {
    if (!props.allowedScrubbers) {
      return true;
    }
    return props.allowedScrubbers.includes(scrubber);
  };

  return (
    <CollapseWrapper>
      <CollapseButton onClick={() => setIsCollapsed(!isCollapsed)}>
        <Icon name={isCollapsed ? 'chevron-up' : 'chevron-down'} size="small" />
      </CollapseButton>
      <Container $isCollapsed={isCollapsed}>
        {showScrubber('timeline') && <TimelineScrubber {...props} />}
        {showScrubber('peer') && <PeerScrubber {...props} />}
        {showScrubber('codePath') && <CodePathScrubber {...props} />}
        {showScrubber('sibling') && <SiblingScrubber {...props} />}
        {showScrubber('stack') && <StackScrubber {...props} />}
      </Container>
    </CollapseWrapper>
  );
};

export default TraceScrubber;
