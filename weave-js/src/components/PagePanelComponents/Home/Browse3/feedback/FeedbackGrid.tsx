import {Box} from '@mui/material';
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
import {HUMAN_ANNOTATION_BASE_TYPE} from './StructuredFeedback/humanAnnotationTypes';
import {RUNNABLE_FEEDBACK_TYPE_PREFIX} from './StructuredFeedback/runnableFeedbackTypes';

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
          <Button
            variant="secondary"
            icon="add-new"
            onClick={onOpenFeedbackSidebar}>
            Create annotation
          </Button>
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
