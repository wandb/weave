/**
 * Show truncated ID with full value in a tooltip.
 */

import {MOON_150} from '@wandb/weave/common/css/color.styles';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback} from 'react';
import styled from 'styled-components';

import {toast} from '../../../../../../common/components/elements/Toast';

const IdPanel = styled.div`
  padding: 0 4px;
  background-color: ${MOON_150};
  border-radius: 4px;
  margin-left: 4px;
  font-weight: 600;
  font-family: monospace;
  font-size: 10px;
  line-height: 20px;
`;
IdPanel.displayName = 'S.IdPanel';

const TooltipText = styled.span`
  white-space: nowrap;
`;
TooltipText.displayName = 'S.TooltipText';

const TooltipId = styled.span``;
TooltipId.displayName = 'S.TooltipId';

type IdProps = {
  id: string;

  type?: string;

  // This is useful for e.g. call ids in the grid where we want to add some highlighting
  // on parent mouseover.
  className?: string;
};

export const Id = ({id, type, className}: IdProps) => {
  const truncatedId = id.slice(-4);
  const trigger = <IdPanel className={className}>{truncatedId}</IdPanel>;
  const prefix = type ? `${type} ID` : 'ID';
  const content = (
    <TooltipText>
      {prefix}: <TooltipId>{id}</TooltipId>
    </TooltipText>
  );
  return <Tooltip trigger={trigger} content={content} />;
};

export const CopyableId = (props: IdProps) => {
  const copy = useCallback(() => {
    copyToClipboard(props.id);
    toast('Copied to clipboard');
  }, [props.id]);

  return (
    <span
      className="cursor-pointer"
      onClick={e => {
        e.stopPropagation();
        copy();
      }}>
      <Id {...props} />
    </span>
  );
};
