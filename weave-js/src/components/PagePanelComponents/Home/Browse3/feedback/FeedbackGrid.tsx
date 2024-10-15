import {Box} from '@mui/material';
import _ from 'lodash';
import React, {useEffect} from 'react';

import {useViewerInfo} from '../../../../../common/hooks/useViewerInfo';
import {TargetBlank} from '../../../../../common/util/links';
import {Alert} from '../../../../Alert';
import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {Empty} from '../pages/common/Empty';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {FeedbackGridInner} from './FeedbackGridInner';

type FeedbackGridProps = {
  entity: string;
  project: string;
  weaveRef: string;
  objectType?: string;
};

export const FeedbackGrid = ({
  entity,
  project,
  weaveRef,
  objectType,
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

  if (!query.result || !query.result.length) {
    return (
      <Empty
        size="small"
        icon="add-reaction"
        heading="No feedback yet"
        description="You can provide feedback directly within the Weave UI or through the API."
        moreInformation={
          <>
            Learn how to{' '}
            <TargetBlank href="http://wandb.me/weave_feedback">
              add feedback
            </TargetBlank>
            .
          </>
        }
      />
    );
  }

  // Group by feedback on this object vs. descendent objects
  const grouped = _.groupBy(query.result, f =>
    f.weave_ref.substring(weaveRef.length)
  );
  const paths = Object.keys(grouped).sort();

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
            />
          </div>
        );
      })}
    </Tailwind>
  );
};
