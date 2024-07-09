/**
 * A button that displays an emoji (possibly with several skin tones) and a count.
 */
import Tooltip, {tooltipClasses, TooltipProps} from '@mui/material/Tooltip';
import * as Colors from '@wandb/weave/common/css/color.styles';
import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {Button} from '../../../../Button';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';
import {EmojiDetails} from './EmojiDetails';

type EmojiButtonProps = {
  viewer: string | null;
  reactions: Feedback[];
  onToggleEmoji: (emoji: string) => void;
  readonly: boolean;
};

export const StyledTooltip = styled(
  ({className, padding, ...props}: TooltipProps & {padding?: number}) => (
    <Tooltip {...props} classes={{popper: className}} />
  )
)(({theme, padding}) => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: '#fff',
    color: Colors.MOON_700,
    border: `1px solid ${Colors.MOON_300}`,
    maxWidth: 600,
    padding,
  },
}));

export const EmojiButton = ({
  viewer,
  reactions,
  onToggleEmoji,
  readonly,
}: EmojiButtonProps) => {
  const emojis = reactions.map(r => r.payload.emoji);
  const emoji = _.uniq(emojis).join('');
  const count = reactions.length;
  const includesUser = reactions.some(r => r.wb_user_id === viewer);

  const title = <EmojiDetails viewer={viewer} reactions={reactions} />;
  const onClick = readonly
    ? undefined
    : () => {
        onToggleEmoji(emojis[0]);
      };
  return (
    <StyledTooltip enterDelay={500} title={title} padding={8}>
      <Button
        size="small"
        variant="secondary"
        className={readonly ? 'cursor-default' : undefined}
        active={includesUser}
        onClick={onClick}>{`${emoji} ${count}`}</Button>
    </StyledTooltip>
  );
};
