import React, {useEffect, useState} from 'react';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {parseRef} from '../../../../../react';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {ReactionsLoaded} from './ReactionsLoaded';

type ReactionsProps = {
  weaveRef: string;
  readonly?: boolean;

  // By default show controls on mouse over or if feedback exists.
  // This prop forces controls to be visible in all cases.
  forceVisible?: boolean;

  twWrapperStyles?: React.CSSProperties;
};

export const Reactions = ({
  weaveRef,
  readonly = false,
  forceVisible,
  twWrapperStyles = {},
}: ReactionsProps) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const [feedback, setFeedback] = useState<Feedback[] | null>(null);

  const parsedRef = parseRef(weaveRef);
  if (parsedRef.scheme !== 'weave') {
    throw new Error('Reactions are only valid on weave refs');
  }
  const {entityName: entity, projectName: project} = parsedRef;
  const projectId = `${entity}/${project}`;

  const getTsClient = useGetTraceServerClientContext();

  useEffect(() => {
    let mounted = true;
    getTsClient()
      .feedbackQuery({
        project_id: projectId,
        query: {
          $expr: {
            $eq: [{$getField: 'weave_ref'}, {$literal: weaveRef}],
          },
        },
        sort_by: [{field: 'created_at', direction: 'asc'}],
      })
      .then(res => {
        if (!mounted) {
          return;
        }
        if ('result' in res) {
          setFeedback(res.result);
        }
      });
    return () => {
      mounted = false;
    };
  }, [getTsClient, projectId, weaveRef]);

  const onAddEmoji = (emoji: string) => {
    const req = {
      project_id: projectId,
      weave_ref: weaveRef,
      creator: null,
      feedback_type: 'wandb.reaction.1',
      payload: {emoji},
    };
    getTsClient()
      .feedbackCreate(req)
      .then(res => {
        if (feedback === null) {
          return;
        }
        if ('detail' in res) {
          return;
        }
        const newReaction = {
          ...req,
          id: res.id,
          created_at: res.created_at,
          wb_user_id: res.wb_user_id,
          payload: res.payload,
        };
        const newFeedback = [...feedback, newReaction];
        setFeedback(newFeedback);
      });
  };
  const onAddNote = (note: string) => {
    const req = {
      project_id: projectId,
      weave_ref: weaveRef,
      creator: null,
      feedback_type: 'wandb.note.1',
      payload: {note},
    };
    getTsClient()
      .feedbackCreate(req)
      .then(res => {
        if (feedback === null) {
          return;
        }
        if ('detail' in res) {
          return;
        }
        const newReaction = {
          ...req,
          id: res.id,
          created_at: res.created_at,
          wb_user_id: res.wb_user_id,
        };
        const newFeedback = [...feedback, newReaction];
        setFeedback(newFeedback);
      });
  };

  const onRemoveFeedback = (id: string) => {
    getTsClient()
      .feedbackPurge({
        project_id: projectId,
        query: {
          $expr: {
            $eq: [{$getField: 'id'}, {$literal: id}],
          },
        },
      })
      .then(res => {
        if (!feedback) {
          return;
        }
        const newFeedback = feedback.filter(f => f.id !== id);
        setFeedback(newFeedback);
      });
  };

  if (loadingUserInfo || feedback === null || userInfo == null) {
    // TODO: Loading indicator?
    return null;
  }
  return (
    <ReactionsLoaded
      viewer={userInfo.username}
      reactions={feedback}
      onAddEmoji={onAddEmoji}
      onAddNote={onAddNote}
      onRemoveFeedback={onRemoveFeedback}
      readonly={readonly}
      forceVisible={forceVisible ?? false}
      twWrapperStyles={twWrapperStyles}
    />
  );
};
