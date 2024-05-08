import {Popover} from '@mui/material';
import Tooltip, {tooltipClasses, TooltipProps} from '@mui/material/Tooltip';
import * as Colors from '@wandb/weave/common/css/color.styles';
import EmojiPicker, {
  EmojiClickData,
  SkinTonePickerLocation,
} from 'emoji-picker-react';
import _ from 'lodash';
import React, {useRef, useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../Button';
import {Tailwind} from '../../../../Tailwind';
import {Tooltip as WeaveTooltip} from '../../../../Tooltip';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {EmojiButton} from './EmojiButton';
import {Notes} from './Notes';

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

type ReactionsLoadedProps = {
  viewer: string;
  reactions: Feedback[];
  onAddEmoji: (emoji: string) => void;
  onAddNote: (note: string) => void;
  onRemoveFeedback: (id: string) => void;
  readonly: boolean;
};

export const ReactionsLoaded = ({
  viewer,
  reactions,
  onAddEmoji,
  onAddNote,
  onRemoveFeedback,
  readonly,
}: ReactionsLoadedProps) => {
  const groupedByType = _.groupBy(reactions, r => r.feedback_type);
  const emojis = groupedByType['wandb.reaction.1'] ?? [];
  const notes = groupedByType['wandb.note.1'] ?? [];
  const groupedByDetone = _.groupBy(
    emojis,
    r => r.payload.detoned ?? r.payload.emoji
  );
  const groupedByUser = _.groupBy(emojis, r => r.wb_user_id);

  const refAddReaction = useRef<HTMLButtonElement>(null);
  const refViewNotes = useRef<HTMLButtonElement>(null);
  const [anchorElReactions, setAnchorElReactions] =
    useState<null | HTMLElement>(null);
  const [anchorElNotes, setAnchorElNotes] = useState<null | HTMLElement>(null);
  const onAddReactionClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorElReactions(anchorElReactions ? null : refAddReaction.current);
  };
  const openNotes = () => {
    setAnchorElNotes(anchorElReactions ? null : refViewNotes.current);
  };
  const onViewNotesClick = (event: React.MouseEvent<HTMLElement>) => {
    openNotes();
  };

  const isOpenReactions = Boolean(anchorElReactions);
  const idReactions = isOpenReactions ? 'simple-popper' : undefined;
  const isOpenNotes = Boolean(anchorElNotes);
  const idNotes = isOpenNotes ? 'simple-popper' : undefined;

  const onToggleEmoji = (emoji: string) => {
    console.log('on toggle emoji', emoji);
    const reactions = groupedByUser[viewer];
    const existing = _.find(reactions, r => r.payload.emoji === emoji);
    if (existing) {
      onRemoveFeedback(existing.id);
    } else {
      onAddEmoji(emoji);
    }
  };

  // User selects an emoji from popup. Matches Slack behavior of toggling.
  const onEmojiClick = (emojiData: EmojiClickData, event: MouseEvent) => {
    console.log({emojiData});
    onToggleEmoji(emojiData.emoji);
    setAnchorElReactions(null);
  };

  const [note, setNote] = useState('');
  const noteLabel = notes.length > 0 ? `${notes.length.toLocaleString()}` : '';
  const onChange = (value: string) => {
    // const onChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setNote(value);
  };

  // const onKeyDown = (key: string) => {
  //   // const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
  //   if (key === 'Enter') {
  //     onNoteA
  //     onAddNote(note);
  //     setNote('');
  //   }
  // };
  const onNoteAdded = () => {
    onAddNote(note);
    setNote('');
  };
  const onCloseNotes = () => setAnchorElNotes(null);

  const notePreview = isOpenNotes ? undefined : notes.length > 0 ? (
    <Notes notes={notes} onClick={openNotes} />
  ) : (
    <div>Click to add notes</div>
  );

  return (
    <Tailwind style={{overflow: 'auto'}}>
      <div className="flex items-center gap-4">
        {Object.entries(groupedByDetone).map(([group, reactions]) => {
          return (
            <EmojiButton
              key={group}
              viewer={viewer}
              reactions={reactions}
              onToggleEmoji={onToggleEmoji}
              readonly={readonly}
            />
          );
        })}
        {!readonly && (
          <>
            <WeaveTooltip
              content="Add reaction..."
              trigger={
                <Button
                  ref={refAddReaction}
                  icon="add-reaction"
                  variant="ghost"
                  size="small"
                  onClick={onAddReactionClick}
                />
              }
            />
            <Popover
              id={idReactions}
              open={isOpenReactions}
              anchorEl={anchorElReactions}
              onClose={() => setAnchorElReactions(null)}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
              }}
              slotProps={{
                paper: {
                  sx: {
                    backgroundColor: 'transparent',
                    boxShadow: 'none',
                  },
                },
              }}>
              <EmojiPicker
                onEmojiClick={onEmojiClick}
                skinTonePickerLocation={SkinTonePickerLocation.PREVIEW}
                reactionsDefaultOpen={true}
                reactions={[
                  '1f44d', // thumbs up
                  '1f44e', // thumbs down
                ]}
              />
            </Popover>
          </>
        )}
        <StyledTooltip enterDelay={500} title={notePreview}>
          <Button
            ref={refViewNotes}
            icon="forum-chat-bubble"
            variant="ghost"
            size="small"
            onClick={onViewNotesClick}>
            {noteLabel}
          </Button>
        </StyledTooltip>
        <Popover
          id={idNotes}
          open={isOpenNotes}
          anchorEl={anchorElNotes}
          onClose={() => setAnchorElNotes(null)}
          anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'left',
          }}
          // slotProps={{
          //   paper: {
          //     sx: {
          //       backgroundColor: 'transparent',
          //       boxShadow: 'none',
          //     },
          //   },
          // }}
        >
          <Notes
            viewer={viewer}
            notes={notes}
            note={note}
            setNote={setNote}
            onNoteAdded={onNoteAdded}
            onClose={onCloseNotes}
          />
        </Popover>
      </div>
    </Tailwind>
  );
};
