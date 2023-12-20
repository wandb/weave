import React, {FC, useCallback} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../Browse3/context';
import {Browse2Trace} from './Browse2Trace';

interface Browse2TracePageParams {
  entity: string;
  project: string;
  traceId: string;
  spanId?: string;
}
export const Browse2TracePage: FC = () => {
  const params = useParams<Browse2TracePageParams>();
  return <Browse2TraceComponent params={params} />;
};

export const Browse2TraceComponent: FC<{params: Browse2TracePageParams}> = ({
  params,
}) => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();
  const setSelectedSpanId = useCallback(
    (spanId: string) =>
      history.push(
        peekingRouter.callUIUrl(
          params.entity,
          params.project,
          params.traceId,
          spanId
        )
      ),
    [history, params.entity, params.project, params.traceId, peekingRouter]
  );
  return (
    <Browse2Trace
      streamId={{
        entityName: params.entity,
        projectName: params.project,
        streamName: 'stream',
      }}
      traceId={params.traceId}
      spanId={params.spanId}
      setSelectedSpanId={setSelectedSpanId}
    />
  );
};
