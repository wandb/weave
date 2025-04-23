import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useMemo, useState} from 'react';

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

  const isScrubberShown = useCallback(
    (scrubber: ScrubberOption) => {
      if (!props.allowedScrubbers) {
        return true;
      }
      return props.allowedScrubbers.includes(scrubber);
    },
    [props.allowedScrubbers]
  );

  // Count how many scrubbers are visible
  // Only show collapse functionality if there are 4 or more scrubbers
  const visibleScrubberCount = useMemo(() => {
    const scrubberOptions: ScrubberOption[] = [
      'timeline',
      'peer',
      'codePath',
      'sibling',
      'stack',
    ];
    return scrubberOptions.filter(scrubber => isScrubberShown(scrubber)).length;
  }, [isScrubberShown]);
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
        {isScrubberShown('timeline') && <TimelineScrubber {...props} />}
        {isScrubberShown('peer') && <PeerScrubber {...props} />}
        {isScrubberShown('codePath') && <CodePathScrubber {...props} />}
        {isScrubberShown('sibling') && <SiblingScrubber {...props} />}
        {isScrubberShown('stack') && <StackScrubber {...props} />}
      </Container>
    </CollapseWrapper>
  );
};

export default TraceScrubber;
