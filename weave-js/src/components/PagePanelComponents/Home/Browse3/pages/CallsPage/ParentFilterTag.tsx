/**
 * Show a Tag with information about the parent filter currently applied.
 * If a filter is not active, this component will not render anything.
 * The remove action, will clear the parent filter.
 * If the parent call is an evaluation, an additional button will allow
 * selecting an alternate evaluation.
 */

import {StyledTooltip} from '@wandb/weave/components/DraggablePopups';
import React, {useRef, useState} from 'react';

import {Button} from '../../../../../Button';
import {RemoveAction} from '../../../../../Tag';
import {RemovableTag} from '../../../../../Tag';
import {isEvaluateOp} from '../common/heuristics';
import {EvaluationSelector} from '../CompareEvaluationsPage/sections/ComparisonDefinitionSection/EvaluationSelector';
import {useWFHooks} from '../wfReactInterface/context';

type ParentFilterTagProps = {
  entity: string;
  project: string;
  parentId: string | null | undefined;
  onSetParentFilter: (parentId: string | undefined) => void;
};

export const ParentFilterTag = ({
  entity,
  project,
  parentId,
  onSetParentFilter,
}: ParentFilterTagProps) => {
  if (!parentId) {
    return null;
  }
  return (
    <ParentFilterTagInner
      entity={entity}
      project={project}
      parentId={parentId}
      onSetParentFilter={onSetParentFilter}
    />
  );
};

type ParentFilterTagInnerProps = {
  entity: string;
  project: string;
  parentId: string;
  onSetParentFilter: (parentId: string | undefined) => void;
};

export const ParentFilterTagInner = ({
  entity,
  project,
  parentId,
  onSetParentFilter,
}: ParentFilterTagInnerProps) => {
  const {useCall} = useWFHooks();
  const callKey = parentId
    ? {
        entity,
        project,
        callId: parentId,
      }
    : null;
  const {loading, result: parentCall} = useCall({key: callKey});

  const refBar = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const onClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : refBar.current);
  };
  const onClose = () => {
    setAnchorEl(null);
  };

  const onSelect = (callId: string) => {
    onSetParentFilter(callId);
    setAnchorEl(null);
  };

  if (loading || parentCall == null) {
    return null;
  }

  let buttonChangeEval = null;
  if (isEvaluateOp(parentCall.spanName)) {
    buttonChangeEval = (
      <div ref={refBar}>
        <Button
          variant="ghost"
          size="small"
          icon="baseline-alt"
          tooltip="Click to switch Evaluations"
          onClick={onClick}
          active={anchorEl !== null}
        />
        <EvaluationSelector
          entity={entity}
          project={project}
          anchorEl={anchorEl}
          onSelect={onSelect}
          onClose={onClose}
          excludeEvalIds={[parentCall.callId]}
        />
      </div>
    );
  }

  const truncatedId = parentCall.callId.slice(-4);
  const label = `Parent: ${parentCall.displayName} (${truncatedId})`;

  // Wrapper to prevent wrapping and ensure single line display
  const NoWrapWrapper: React.FC<{children: React.ReactNode}> = ({children}) => (
    <div
      style={{
        maxWidth: '300px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
      {children}
    </div>
  );

  return (
    <>
      {buttonChangeEval}
      <StyledTooltip enterDelay={500} title={label} placement="top" padding={8}>
        <span>
          <RemovableTag
            maxChars={48}
            truncatedPart="middle"
            color="moon"
            label={label}
            Wrapper={NoWrapWrapper}
            removeAction={
              <RemoveAction
                onClick={(e: React.SyntheticEvent) => {
                  e.stopPropagation();
                  onSetParentFilter(undefined);
                }}
              />
            }
          />
        </span>
      </StyledTooltip>
    </>
  );
};
