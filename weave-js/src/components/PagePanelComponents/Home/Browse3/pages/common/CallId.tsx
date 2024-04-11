/**
 * Show truncated Call ID with full value in a tooltip.
 */

import {MOON_150} from '@wandb/weave/common/css/color.styles';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';
import styled from 'styled-components';

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

const TooltipCallId = styled.span``;
TooltipCallId.displayName = 'S.TooltipCallId';

type CallIdProps = {
  callId: string;
};

export const CallId = ({callId}: CallIdProps) => {
  const truncatedId = callId.slice(-4);
  const trigger = <IdPanel className="callId">{truncatedId}</IdPanel>;
  const content = (
    <TooltipText>
      Call ID: <TooltipCallId>{callId}</TooltipCallId>
    </TooltipText>
  );
  return <Tooltip trigger={trigger} content={content} />;
};
