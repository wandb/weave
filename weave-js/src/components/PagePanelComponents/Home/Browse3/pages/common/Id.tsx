/**
 * Show truncated ID with full value in a tooltip.
 */

import {GREEN_600, MOON_150} from '@wandb/weave/common/css/color.styles';
import {IconCheckmark} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useState} from 'react';
import styled from 'styled-components';

const IdPanel = styled.div<{clickable?: boolean}>`
  padding: 0 4px;
  background-color: ${MOON_150};
  border-radius: 4px;
  margin-left: 4px;
  font-weight: 600;
  font-family: monospace;
  font-size: 10px;
  line-height: 20px;
  cursor: ${props => (props.clickable ? 'pointer' : 'default')};
`;
IdPanel.displayName = 'S.IdPanel';

const TooltipText = styled.span`
  white-space: nowrap;
`;
TooltipText.displayName = 'S.TooltipText';

const TooltipId = styled.span``;
TooltipId.displayName = 'S.TooltipId';

const CopiedPanel = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
`;
CopiedPanel.displayName = 'S.CopiedPanel';

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

export const CopyableId = ({id, type, className}: IdProps) => {
  const [isClicked, setIsClicked] = useState(false);
  const truncatedId = id.slice(-4);
  const onClick = useCallback(() => {
    copyToClipboard(id);
    setIsClicked(true);
  }, [id]);
  const onMouseLeave = useCallback(() => {
    setTimeout(() => {
      setIsClicked(false);
    }, 500);
  }, [setIsClicked]);
  const trigger = (
    <IdPanel
      clickable={true}
      className={className}
      onClick={onClick}
      onMouseLeave={onMouseLeave}>
      {truncatedId}
    </IdPanel>
  );
  const prefix = type ? `${type} ID` : 'ID';
  const content = isClicked ? (
    <CopiedPanel>
      <IconCheckmark color={GREEN_600} />
      ID copied!
    </CopiedPanel>
  ) : (
    <TooltipText>
      {prefix}: <TooltipId>{id}</TooltipId>
    </TooltipText>
  );
  return <Tooltip trigger={trigger} content={content} />;
};
