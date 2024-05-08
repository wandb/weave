import React, {useEffect, useState} from 'react';

import {useViewerUserInfo2} from '../../../../../common/hooks/useViewerUserInfo';
import {parseRef} from '../../../../../react';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {ReactionsLoaded} from './ReactionsLoaded';

type ReactionsProps = {
  weaveRef: string;
  readonly?: boolean;
};

export const Reactions = ({weaveRef, readonly = false}: ReactionsProps) => {
  const {loading: loadingUserInfo, userInfo} = useViewerUserInfo2();
  const [feedback, setFeedback] = useState<Feedback[] | null>(null);

  const parsedRef = parseRef(weaveRef);
  const {entityName: entity, projectName: project} = parsedRef;
  const projectId = `${entity}/${project}`;

  const getTsClient = useGetTraceServerClientContext();

  useEffect(() => {
    if (parsedRef.scheme !== 'weave') {
      throw new Error('Invalid ref ' + weaveRef);
    }
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
        if ('result' in res) {
          setFeedback(res.result);
        }
      });
  }, [weaveRef]);

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
        if (!feedback) {
          return;
        }
        const newReaction = {
          ...req,
          ...res,
        };
        console.log({req, res, newReaction});
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
        if (!feedback) {
          return;
        }
        const newReaction = {
          ...req,
          ...res,
        };
        console.log({req, res, newReaction});
        const newFeedback = [...feedback, newReaction];
        setFeedback(newFeedback);
      });
  };

  const onRemoveFeedback = (id: string) => {
    getTsClient()
      .feedbackPurge({
        project_id: projectId,
        id,
      })
      .then(res => {
        if (!feedback) {
          return;
        }
        const newFeedback = feedback.filter(f => f.id !== id);
        setFeedback(newFeedback);
      });
  };

  if (loadingUserInfo || feedback === null) {
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
    />
  );
};
