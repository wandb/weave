import React, {useEffect, useState} from 'react';
import {v4 as uuidv4} from 'uuid';

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
  feedbackData?: Feedback[];
  readonly?: boolean;

  // By default show controls on mouse over or if feedback exists.
  // This prop forces controls to be visible in all cases.
  forceVisible?: boolean;

  twWrapperStyles?: React.CSSProperties;
};

const SORT_BY: SortBy[] = [{field: 'created_at', direction: 'asc'}];

export const Reactions = ({
  weaveRef,
  feedbackData,
  readonly = false,
  forceVisible,
  twWrapperStyles = {},
}: ReactionsProps) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const [feedback, setFeedback] = useState<Feedback[] | null>(
    feedbackData ?? []
  );
  const [useServerState, setUseServerState] = useState(false);

  const parsedRef = parseRef(weaveRef);
  if (parsedRef.scheme !== 'weave') {
    throw new Error('Reactions are only valid on weave refs');
  }
  const {entityName: entity, projectName: project} = parsedRef;
  const projectId = `${entity}/${project}`;

  const {useFeedback} = useWFHooks();
  const query = useFeedback({
    key: {
      entity,
      project,
      weaveRef,
    },
    skip: feedbackData !== undefined && !useServerState,
    sortBy: SORT_BY,
  });
  const getTsClient = useGetTraceServerClientContext();

  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(weaveRef, query.refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle initial data setup and server state management
  useEffect(() => {
    if (useServerState) {
      // In server mode, use query result directly
      if (query.result !== undefined) {
        setFeedback(query.result);
      }
    } else {
      // In initial mode
      if (feedbackData !== undefined) {
        // Use provided feedbackData
        setFeedback(feedbackData);
      } else if (query.result !== undefined) {
        // No feedbackData provided, use query result
        setFeedback(query.result);
      }
    }
  }, [query.result, feedbackData, useServerState]);

  const createFeedbackOptimistically = async (
    feedbackType: string,
    payload: Record<string, any>
  ) => {
    // Switch to server state mode on first mutation
    if (!useServerState) {
      setUseServerState(true);
    }

    // Create optimistic feedback item
    // @ts-ignore - wb_user_id will be filled by server response
    const optimisticFeedback: Feedback = {
      id: uuidv4(),
      project_id: projectId,
      weave_ref: weaveRef,
      creator: null,
      created_at: new Date().toISOString(),
      feedback_type: feedbackType,
      payload,
    };

    // Optimistically update local state
    setFeedback(prevFeedback =>
      prevFeedback
        ? [...prevFeedback, optimisticFeedback]
        : [optimisticFeedback]
    );

    // Make API call
    try {
      const req = {
        project_id: projectId,
        weave_ref: weaveRef,
        creator: null,
        feedback_type: feedbackType,
        payload,
      };
      await getTsClient().feedbackCreate(req);

      // The server state will be updated via the query refetch triggered by the feedback listener
      // We don't need to manually update the state here as the useEffect will handle it
    } catch (error) {
      // Revert optimistic update on error
      setFeedback(
        prevFeedback =>
          prevFeedback?.filter(f => f.id !== optimisticFeedback.id) || null
      );
      console.error('Failed to create feedback:', error);
    }
  };

  const onAddEmoji = async (emoji: string) => {
    await createFeedbackOptimistically('wandb.reaction.1', {emoji});
  };

  const onAddNote = async (note: string) => {
    await createFeedbackOptimistically('wandb.note.1', {note});
  };

  const onRemoveFeedback = async (id: string) => {
    // Switch to server state mode on first mutation
    if (!useServerState) {
      setUseServerState(true);
    }

    // Store the item being removed for potential rollback
    const itemToRemove = feedback?.find(f => f.id === id);

    // Optimistically remove from local state
    setFeedback(prevFeedback => prevFeedback?.filter(f => f.id !== id) || null);

    // Make API call
    try {
      await getTsClient().feedbackPurge({
        project_id: projectId,
        query: {
          $expr: {
            $eq: [{$getField: 'id'}, {$literal: id}],
          },
        },
      });

      // The server state will be updated via the query refetch triggered by the feedback listener
      // We don't need to manually update the state here as the useEffect will handle it
    } catch (error) {
      // Revert optimistic update on error
      if (itemToRemove) {
        setFeedback(prevFeedback =>
          prevFeedback ? [...prevFeedback, itemToRemove] : [itemToRemove]
        );
      }
      console.error('Failed to remove feedback:', error);
    }
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
