import {useScrollIntoView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/hooks/scrollIntoView';
import React from 'react';

import {getCallDisplayName} from '../../TraceViews/utils';
import {useStackContext} from '../context';
import {
  BreadcrumbContainer,
  BreadcrumbItem,
  BreadcrumbSeparator,
} from '../styles';
import {BaseScrubberProps} from '../types';

export const StackBreadcrumb: React.FC<BaseScrubberProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const {stackState} = useStackContext();
  const selectedItemRef = React.useRef<HTMLButtonElement>(null);

  useScrollIntoView(selectedItemRef, Boolean(selectedCallId), {
    behavior: 'smooth',
    block: 'center',
    inline: 'nearest',
  });

  if (!selectedCallId || !stackState) {
    return null;
  }

  const stack = stackState.stack.map(id => {
    const call = traceTreeFlat[id]?.call;
    return {
      id,
      name: call ? getCallDisplayName(call) : id,
    };
  });

  if (stack.length <= 1) {
    return null;
  }

  return (
    <BreadcrumbContainer>
      {stack.map((node, index) => (
        <React.Fragment key={node.id}>
          {index > 0 && <BreadcrumbSeparator>{'/'}</BreadcrumbSeparator>}
          <BreadcrumbItem
            ref={node.id === selectedCallId ? selectedItemRef : undefined}
            $active={node.id === selectedCallId}
            onClick={() => onCallSelect(node.id)}
            title={node.name}>
            {node.name}
          </BreadcrumbItem>
        </React.Fragment>
      ))}
    </BreadcrumbContainer>
  );
};
