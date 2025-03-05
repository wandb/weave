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
          <BreadCrumbItemWithScroll {...props} node={node} />
        </React.Fragment>
      ))}
    </BreadcrumbContainer>
  );
};

const BreadCrumbItemWithScroll: React.FC<
  BaseScrubberProps & {node: {id: string; name: string}}
> = props => {
  const isSelected = props.node.id === props.selectedCallId;
  const selectedItemRef = React.useRef<HTMLButtonElement>(null);
  useScrollIntoView(selectedItemRef, isSelected);
  return (
    <BreadcrumbItem
      ref={selectedItemRef}
      $active={isSelected}
      onClick={() => props.onCallSelect(props.node.id)}
      title={props.node.name}>
      {props.node.name}
    </BreadcrumbItem>
  );
};
