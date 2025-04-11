import {Box} from '@mui/material';
import {Popover} from '@mui/material';
import EmojiPicker, {SkinTonePickerLocation} from 'emoji-picker-react';
import _ from 'lodash';
import React, {useEffect, useMemo} from 'react';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {Alert} from '../../../../Alert';
import {Button} from '../../../../Button';
import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {Empty} from '../pages/common/Empty';
import {EMPTY_PROPS_FEEDBACK} from '../pages/common/EmptyContent';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {FeedbackGridInner} from './FeedbackGridInner';
import {Notes} from './Notes';
import {HUMAN_ANNOTATION_BASE_TYPE} from './StructuredFeedback/humanAnnotationTypes';
import {RUNNABLE_FEEDBACK_TYPE_PREFIX} from './StructuredFeedback/runnableFeedbackTypes';
import {WeaveEmojiPicker} from './WeaveEmojiPicker';

const ANNOTATION_PREFIX = `${HUMAN_ANNOTATION_BASE_TYPE}.`;

type FeedbackGridProps = {
  entity: string;
  project: string;
  weaveRef: string;
  objectType?: string;
  onOpenFeedbackSidebar?: () => void;
};

export const FeedbackGrid = ({
  entity,
  project,
  weaveRef,
  objectType,
  onOpenFeedbackSidebar,
}: FeedbackGridProps) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const [showThumbsEmojiPicker, setShowThumbsEmojiPicker] =
    React.useState(false);
  const [showNoteInput, setShowNoteInput] = React.useState(false);
  const [note, setNote] = React.useState('');
  const [showCompleteEmojiPicker, setShowCompleteEmojiPicker] =
    React.useState(false);
  const emojiButtonRef = React.useRef<HTMLButtonElement>(null);
  const noteButtonRef = React.useRef<HTMLButtonElement>(null);

  const {useFeedback} = useWFHooks();
  const query = useFeedback({
    entity,
    project,
    weaveRef,
  });

  const getTsClient = useGetTraceServerClientContext();
  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(weaveRef, query.refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const hasAnnotationFeedback = query.result?.some(f =>
    f.feedback_type.startsWith(ANNOTATION_PREFIX)
  );

  // Group by feedback on this object vs. descendent objects
  const grouped = useMemo(() => {
    // Exclude runnables as they are presented in a different tab
    const withoutRunnables = (query.result ?? []).filter(
      f => !f.feedback_type.startsWith(RUNNABLE_FEEDBACK_TYPE_PREFIX)
    );
    // Combine annotation feedback on (feedback_type, creator)
    const combined = _.groupBy(
      withoutRunnables.filter(f =>
        f.feedback_type.startsWith(ANNOTATION_PREFIX)
      ),
      f => `${f.feedback_type}-${f.creator}`
    );
    // only keep the most recent feedback for each (feedback_type, creator)
    const combinedFiltered = Object.values(combined).map(
      fs =>
        fs.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )[0]
    );
    // add the non-annotation feedback to the combined object
    combinedFiltered.push(
      ...withoutRunnables.filter(
        f => !f.feedback_type.startsWith(ANNOTATION_PREFIX)
      )
    );

    // Group by feedback on this object vs. descendent objects
    return _.groupBy(combinedFiltered, f =>
      f.weave_ref.substring(weaveRef.length)
    );
  }, [query.result, weaveRef]);

  const paths = useMemo(() => Object.keys(grouped).sort(), [grouped]);

  const onAddEmoji = (emoji: string) => {
    const req = {
      project_id: `${entity}/${project}`,
      weave_ref: weaveRef,
      creator: null,
      feedback_type: 'wandb.reaction.1',
      payload: {emoji},
    };
    getTsClient().feedbackCreate(req);
    setShowThumbsEmojiPicker(false);
  };

  const onAddNote = () => {
    if (note.trim()) {
      const req = {
        project_id: `${entity}/${project}`,
        weave_ref: weaveRef,
        creator: null,
        feedback_type: 'wandb.note.1',
        payload: {note: note.trim()},
      };
      getTsClient().feedbackCreate(req);
      setNote('');
      setShowNoteInput(false);
    }
  };

  if (query.loading || loadingUserInfo) {
    return (
      <Box
        sx={{
          height: '38px',
          width: '100%',
        }}>
        <Loading centered size={25} />
      </Box>
    );
  }
  if (query.error) {
    return (
      <div className="m-16 flex flex-col gap-8">
        <Alert severity="error">
          Error: {query.error.message ?? JSON.stringify(query.error)}
        </Alert>
      </div>
    );
  }

  if (!paths.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center">
        <div className="mx-8 flex flex-col items-center gap-16">
          <Empty size="small" {...EMPTY_PROPS_FEEDBACK} />
          <div className="flex gap-8">
            <div>
              <Button
                ref={emojiButtonRef}
                variant="secondary"
                icon="add-reaction"
                onClick={() => setShowThumbsEmojiPicker(true)}>
                Reaction
              </Button>
              <Popover
                open={showThumbsEmojiPicker}
                anchorEl={emojiButtonRef.current}
                onClose={() => {
                  setShowThumbsEmojiPicker(false);
                  // Requires 100ms to complete animation before changing state to minimal-picker
                  setTimeout(() => {
                    setShowCompleteEmojiPicker(false);
                  }, 100);
                }}
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
                {!showCompleteEmojiPicker && (
                  <WeaveEmojiPicker
                    onEmojiClick={emojiData => onAddEmoji(emojiData.emoji)}
                    skinTonesDisabled={true}
                    reactionsDefaultOpen={true}
                    skinTonePickerLocation={SkinTonePickerLocation.PREVIEW}
                    reactions={[
                      '1f44d', // thumbs up
                      '1f44e', // thumbs down
                    ]}
                    onPlusButtonClick={() => {
                      setShowCompleteEmojiPicker(true);
                    }}
                  />
                )}
                {showCompleteEmojiPicker && (
                  <EmojiPicker
                    onEmojiClick={emojiData => onAddEmoji(emojiData.emoji)}
                    skinTonesDisabled={true}
                    skinTonePickerLocation={SkinTonePickerLocation.PREVIEW}
                    previewConfig={{
                      defaultEmoji: '1f44d',
                      defaultCaption: 'Hover for emoji name',
                    }}
                  />
                )}
              </Popover>
            </div>
            <div>
              <Button
                ref={noteButtonRef}
                variant="secondary"
                icon="forum-chat-bubble"
                onClick={() => setShowNoteInput(true)}>
                Note
              </Button>
              <Popover
                open={showNoteInput}
                anchorEl={noteButtonRef.current}
                onClose={() => setShowNoteInput(false)}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'left',
                }}>
                <Notes
                  notes={[]}
                  readonly={false}
                  note={note}
                  setNote={setNote}
                  onNoteAdded={onAddNote}
                  onClose={() => setShowNoteInput(false)}
                />
              </Popover>
            </div>
            <Button
              variant="secondary"
              icon="marker"
              onClick={onOpenFeedbackSidebar}>
              Annotation
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const currentViewerId = userInfo ? userInfo.id : null;
  return (
    <Tailwind>
      {paths.map(path => {
        return (
          <div key={path}>
            {path && <div className="text-sm text-moon-500">On {path}</div>}
            <FeedbackGridInner
              feedback={grouped[path]}
              currentViewerId={currentViewerId}
              showAnnotationName={hasAnnotationFeedback}
            />
          </div>
        );
      })}
    </Tailwind>
  );
};
