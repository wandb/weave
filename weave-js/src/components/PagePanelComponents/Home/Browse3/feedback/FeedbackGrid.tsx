import {Box} from '@mui/material';
import _ from 'lodash';
import React from 'react';

import {Alert} from '../../../../Alert';
import {Loading} from '../../../../Loading';
import {Tailwind} from '../../../../Tailwind';
import {useWFHooks} from '../pages/wfReactInterface/context';
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
  const {useFeedback} = useWFHooks();
  const query = useFeedback({
    entity,
    project,
    weaveRef,
    includeExtra: true,
  });

  if (query.loading) {
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
    const obj = objectType ?? 'object';
    return (
      <div className="m-16 flex flex-col gap-8">
        <Alert>No feedback added to this {obj}.</Alert>
      </div>
    );
  }

  // Group by feedback on this object vs. descendent objects
  const grouped = _.groupBy(query.result, f =>
    f.weave_ref.substring(weaveRef.length)
  );
  const paths = Object.keys(grouped).sort();

  return (
    <Tailwind>
      {paths.map(path => {
        return (
          <div key={path}>
            {path && <div className="text-sm text-moon-500">On {path}</div>}
            <FeedbackGridInner feedback={grouped[path]} />
          </div>
        );
      })}
    </Tailwind>
  );
};
