import {Icon} from '@wandb/weave/components/Icon';
import React, {useState, useMemo} from 'react';

import {BaseScrubberProps} from './components/BaseScrubber';
import {
  CodePathScrubber,
  PeerScrubber,
  SiblingScrubber,
  StackScrubber,
  TimelineScrubber,
} from './components/scrubbers';
import {CollapseButton, CollapseWrapper, Container} from './styles';

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

  // Count how many scrubbers are visible
  // Only show collapse functionality if there are 4 or more scrubbers
  const visibleScrubberCount = useMemo(() => {
    const scrubberOptions: ScrubberOption[] = ['timeline', 'peer', 'codePath', 'sibling', 'stack'];
    return scrubberOptions.filter(scrubber => showScrubber(scrubber)).length;
  }, [props.allowedScrubbers]);
  const showCollapseButton = visibleScrubberCount >= 4;
  
  return (
    <CollapseWrapper>
      {showCollapseButton && (
        <CollapseButton onClick={() => setIsCollapsed(!isCollapsed)}>
          <Icon
            name={isCollapsed ? 'chevron-up' : 'chevron-down'}
            size="small"
            className="max-w-14 max-h-14"
          />
        </CollapseButton>
      )}
      <Container $isCollapsed={showCollapseButton ? isCollapsed : false}>
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
