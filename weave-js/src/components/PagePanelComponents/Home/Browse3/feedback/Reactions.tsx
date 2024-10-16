import React, {useEffect, useState} from 'react';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {parseRef} from '../../../../../react';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {
  Feedback,
  SortBy,
} from '../pages/wfReactInterface/traceServerClientTypes';
import {ReactionsLoaded} from './ReactionsLoaded';

type ReactionsProps = {
  weaveRef: string;
  readonly?: boolean;

  // By default show controls on mouse over or if feedback exists.
  // This prop forces controls to be visible in all cases.
  forceVisible?: boolean;

  twWrapperStyles?: React.CSSProperties;
};

const SORT_BY: SortBy[] = [{field: 'created_at', direction: 'asc'}];

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

  const {useFeedback} = useWFHooks();
  const query = useFeedback(
    {
      entity,
      project,
      weaveRef,
    },
    SORT_BY
  );
  const getTsClient = useGetTraceServerClientContext();
  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(weaveRef, query.refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (query.result) {
      setFeedback(query.result);
    }
  }, [query.result]);

  const onAddEmoji = (emoji: string) => {
    const req = {
      project_id: projectId,
      weave_ref: weaveRef,
      creator: null,
      feedback_type: 'wandb.reaction.1',
      payload: {emoji},
    };
    getTsClient().feedbackCreate(req);
  };
  const onAddNote = (note: string) => {
    const req = {
      project_id: projectId,
      weave_ref: weaveRef,
      creator: null,
      feedback_type: 'wandb.note.1',
      payload: {note},
    };
    getTsClient().feedbackCreate(req);
  };

  const onRemoveFeedback = (id: string) => {
    getTsClient().feedbackPurge({
      project_id: projectId,
      query: {
        $expr: {
          $eq: [{$getField: 'id'}, {$literal: id}],
        },
      },
    });
  };

  if (loadingUserInfo || feedback === null) {
    // TODO: Loading indicator?
    return null;
  }

  // Always readonly if anonymous.
  // TODO: Consider W&B admin privileges.
  const viewer = userInfo ? userInfo.id : null;
  const isReadonly = !viewer || !userInfo?.teams.includes(entity) || readonly;
  return (
    <ReactionsLoaded
      currentViewerId={viewer}
      reactions={feedback}
      onAddEmoji={onAddEmoji}
      onAddNote={onAddNote}
      onRemoveFeedback={onRemoveFeedback}
      readonly={isReadonly}
      forceVisible={forceVisible ?? false}
      twWrapperStyles={twWrapperStyles}
    />
  );
};
