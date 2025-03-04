import {useScrollIntoView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/hooks/scrollIntoView';
import React from 'react';

import {getCallDisplayName} from '../../TraceViews/utils';
import {
  BreadcrumbContainer,
  BreadcrumbItem,
  BreadcrumbSeparator,
} from '../styles';
import {BaseScrubberProps} from './BaseScrubber';

export const StackBreadcrumb: React.FC<BaseScrubberProps> = props => {
  const selectedItemRef = React.useRef<HTMLButtonElement>(null);
  
  useScrollIntoView(selectedItemRef, Boolean(props.selectedCallId));

  if (!props.selectedCallId) {
    return null;
  }

  const stack = props.stack.map(id => {
    const call = props.traceTreeFlat[id]?.call;
    return {
      id,
      name: call ? getCallDisplayName(call) : id,
    };
  });

  return (
    <BreadcrumbContainer>
      {stack.map((node, index) => (
        <React.Fragment key={node.id}>
          {index > 0 && <BreadcrumbSeparator>{'/'}</BreadcrumbSeparator>}
          <BreadcrumbItem
            ref={node.id === props.selectedCallId ? selectedItemRef : undefined}
            $active={node.id === props.selectedCallId}
            onClick={() => props.onCallSelect(node.id)}
            title={node.name}>
            {node.name}
          </BreadcrumbItem>
        </React.Fragment>
      ))}
    </BreadcrumbContainer>
  );
};
