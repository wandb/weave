/**
 * A button that displays an emoji (possibly with several skin tones) and a count.
 */
import Tooltip, {tooltipClasses, TooltipProps} from '@mui/material/Tooltip';
import * as Colors from '@wandb/weave/common/css/color.styles';
import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {Button} from '../../../../Button';
import {Feedback} from '../pages/wfReactInterface/traceServerClientTypes';
import {EmojiDetails} from './EmojiDetails';

type EmojiButtonProps = {
  currentViewerId: string | null;
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
  currentViewerId,
  reactions,
  onToggleEmoji,
  readonly,
}: EmojiButtonProps) => {
  const emojis = reactions.map(r => r.payload.emoji);
  const emoji = _.uniq(emojis).join('');
  const count = reactions.length;

  // TODO (Tim): After https://github.com/wandb/core/pull/22947 is deployed,
  // Remove `includesUserLegacy`
  const {loading: userInfoLoading, userInfo} = useViewerInfo();
  const includesUserLegacy = reactions.some(
    r => !userInfoLoading && r.wb_user_id === userInfo?.username
  );

  const includesUser =
    reactions.some(r => r.wb_user_id === currentViewerId) || includesUserLegacy;

  const title = (
    <EmojiDetails currentViewerId={currentViewerId} reactions={reactions} />
  );
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
