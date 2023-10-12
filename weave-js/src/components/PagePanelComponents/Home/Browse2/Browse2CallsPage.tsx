import React, {FC} from 'react';
import {useParams} from 'react-router-dom';
import {CallFilter, TraceSpan} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {Browse2Calls} from './Browse2Calls';
import {useQuery} from './CommonLib';

export const Browse2CallsPage: FC = () => {
  const params = useParams<Browse2RootObjectVersionItemParams>();
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
  console.log('URL SEL SPAN', selectedSpan);
  return (
    <Browse2Calls
      streamId={{
        entityName: params.entity,
        projectName: params.project,
        streamName: 'stream',
      }}
      filters={filters}
    />
  );
};
