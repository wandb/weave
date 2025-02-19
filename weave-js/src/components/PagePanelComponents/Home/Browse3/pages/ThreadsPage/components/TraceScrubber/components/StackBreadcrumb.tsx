import React from 'react';

import {BaseScrubberProps} from '../types';
import {useStackContext} from '../context';
import {
  BreadcrumbContainer,
  BreadcrumbItem,
  BreadcrumbSeparator,
} from '../styles';

export const StackBreadcrumb: React.FC<BaseScrubberProps> = ({
  traceTreeFlat,
  selectedCallId,
  onCallSelect,
}) => {
  const {stackState} = useStackContext();
  
  if (!selectedCallId || !stackState) return null;

  const stack = stackState.stack.map(id => ({
    id,
    name: traceTreeFlat[id]?.call.display_name || 
          traceTreeFlat[id]?.call.op_name.split('/').pop() || 
          id,
  }));

  if (stack.length <= 1) return null;

  return (
    <BreadcrumbContainer>
      {stack.map((node, index) => (
        <React.Fragment key={node.id}>
          {index > 0 && <BreadcrumbSeparator>/</BreadcrumbSeparator>}
          <BreadcrumbItem
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