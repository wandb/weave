import {Button} from '@wandb/weave/components/Button';
import {useScrollIntoView} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/hooks/scrollIntoView';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useMemo} from 'react';

import {getCallDisplayName} from '../../TraceViews/utils';
import {
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbNavigationButtons,
  BreadcrumbSeparator,
  BreadcrumbWrapper,
} from '../styles';
import {BaseScrubberProps} from './BaseScrubber';

export const StackBreadcrumb: React.FC<
  BaseScrubberProps & {
    rootParentId: string | undefined;
    traceRootCallId: string | undefined;
  }
> = props => {
  const stack = useMemo(
    () =>
      props.stack.map(id => {
        const call = props.traceTreeFlat[id]?.call;
        return {
          id,
          name: call ? getCallDisplayName(call) : id,
        };
      }),
    [props.stack, props.traceTreeFlat]
  );

  if (!props.focusedCallId) {
    return null;
  }

  return (
    <BreadcrumbWrapper>
      <BreadcrumbNavigationButtons>
        <Tooltip
          content={'Reveal root call'}
          trigger={
            <Button
              variant={'ghost'}
              disabled={
                !props.traceRootCallId ||
                props.rootCallId === props.traceRootCallId
              }
              onClick={() => {
                if (props.traceRootCallId) {
                  props.setRootCallId(props.traceRootCallId);
                }
              }}
              icon={'chevron-up'}
              size="small"
            />
          }
        />
        <Tooltip
          content={'Reveal parent call'}
          trigger={
            <Button
              variant={'ghost'}
              disabled={
                !props.rootParentId || props.rootCallId === props.rootParentId
              }
              onClick={() => {
                if (props.rootParentId) {
                  props.setRootCallId(props.rootParentId);
                }
              }}
              icon={'parent-back-up'}
              size="small"
            />
          }
        />
      </BreadcrumbNavigationButtons>

      <BreadcrumbList>
        {stack.map((node, index) => (
          <React.Fragment key={node.id}>
            {index > 0 && <BreadcrumbSeparator>{'/'}</BreadcrumbSeparator>}
            <BreadCrumbItemWithScroll {...props} node={node} />
          </React.Fragment>
        ))}
      </BreadcrumbList>
    </BreadcrumbWrapper>
  );
};

const BreadCrumbItemWithScroll: React.FC<
  BaseScrubberProps & {node: {id: string; name: string}}
> = props => {
  const isSelected = props.node.id === props.focusedCallId;
  const selectedItemRef = React.useRef<HTMLButtonElement>(null);
  useScrollIntoView(selectedItemRef, isSelected);
  return (
    <BreadcrumbItem
      ref={selectedItemRef}
      $active={isSelected}
      onClick={() => props.setFocusedCallId(props.node.id)}
      title={props.node.name}>
      {props.node.name}
    </BreadcrumbItem>
  );
};
