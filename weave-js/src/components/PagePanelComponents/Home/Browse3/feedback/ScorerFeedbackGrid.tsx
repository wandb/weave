import {Box} from '@mui/material';
import _ from 'lodash';
import React, {useEffect, useMemo} from 'react';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {TargetBlank} from '../../../../../common/util/links';
import {Alert} from '../../../../Alert';
import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {Empty} from '../pages/common/Empty';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {ScoresFeedbackGridInner} from './ScoresFeedbackGridInner';
import {RUNNABLE_FEEDBACK_TYPE_PREFIX} from './StructuredFeedback/runnableFeedbackTypes';

type FeedbackGridProps = {
  entity: string;
  project: string;
  weaveRef: string;
  objectType?: string;
};

export const ScorerFeedbackGrid = ({
  entity,
  project,
  weaveRef,
  objectType,
}: FeedbackGridProps) => {
  /**
   * This component is very similar to `FeedbackGrid`, but it only shows scores.
   * While some of the code is duplicated, it is kept separate to make it easier
   * to modify in the future.
   */
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();

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

  // Group by feedback on this object vs. descendent objects
  const grouped = useMemo(() => {
    // Exclude runnables as they are presented in a different tab
    const onlyRunnables = (query.result ?? []).filter(f =>
      f.feedback_type.startsWith(RUNNABLE_FEEDBACK_TYPE_PREFIX)
    );

    // Group by feedback on this object vs. descendent objects
    return _.groupBy(onlyRunnables, f =>
      f.weave_ref.substring(weaveRef.length)
    );
  }, [query.result, weaveRef]);

  const paths = useMemo(() => Object.keys(grouped).sort(), [grouped]);

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
      <Empty
        size="small"
        icon="add-reaction"
        heading="No scores yet"
        description="Calls are scored by running Evaluations."
        moreInformation={
          <>
            Learn how to{' '}
            <TargetBlank href="http://wandb.me/weave_eval_tut">
              run evaluations
            </TargetBlank>
            .
          </>
        }
        // Need to add this additional detail once the new API is released.
        // description="You can add scores to calls by using the `Call.apply_scorer` method."
      />
    );
  }

  const currentViewerId = userInfo ? userInfo.id : null;
  return (
    <Tailwind>
      {paths.map(path => {
        return (
          <div key={path}>
            {path && <div className="text-sm text-moon-500">On {path}</div>}
            <ScoresFeedbackGridInner
              feedback={grouped[path]}
              currentViewerId={currentViewerId}
            />
          </div>
        );
      })}
    </Tailwind>
  );
};
