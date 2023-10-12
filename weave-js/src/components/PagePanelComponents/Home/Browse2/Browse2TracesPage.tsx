import React, {FC} from 'react';
import {useParams} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import {CallFilter, StreamId, TraceSpan} from './callTree';
import {Link} from './CommonLib';
import {useTraceSummaries} from './callTreeHooks';
import {PageEl} from './CommonLib';
import {useQuery} from './CommonLib';

const Browse2Traces: FC<{
  streamId: StreamId;
  selectedSpan?: TraceSpan;
}> = ({streamId, selectedSpan}) => {
  const traces = useTraceSummaries(streamId);
  return (
    <div>
      {traces.map(trace => (
        <div>
          <Link
            to={`/${URL_BROWSE2}/${streamId.entityName}/${streamId.projectName}/trace/${trace.trace_id}`}>
            {trace.trace_id}
          </Link>
          : {trace.span_count}
        </div>
      ))}
    </div>
  );
};
interface Browse2TracesPageParams {
  entity: string;
  project: string;
}
export const Browse2TracesPage: FC = () => {
  const params = useParams<Browse2TracesPageParams>();
  const filters: CallFilter = {};
  const query = useQuery();
  let selectedSpan: TraceSpan | undefined = undefined;
  query.forEach((val, key) => {
    if (key === 'op') {
      filters.opUri = val;
    } else if (key === 'inputUri') {
      if (filters.inputUris == null) {
        filters.inputUris = [];
      }
      filters.inputUris.push(val);
    } else if (key === 'traceSpan') {
      const [traceId, spanId] = val.split(',', 2);
      selectedSpan = {traceId, spanId};
    }
  });
  return (
    <PageEl>
      <Browse2Traces
        streamId={{
          entityName: params.entity,
          projectName: params.project,
          streamName: 'stream',
        }}
        selectedSpan={selectedSpan}
      />
    </PageEl>
  );
};
