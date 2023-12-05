import {Box, Button} from '@mui/material';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {FC, useCallback} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {Browse2Trace} from './Browse2Trace';
import {PageEl} from './CommonLib';
import {PageHeader} from './CommonLib';
import {useWeaveflowRouteContext} from './context';

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
  const routeContext = useWeaveflowRouteContext();
  const setSelectedSpanId = useCallback(
    (spanId: string) =>
      history.push(
        routeContext.callUIUrl(
          params.entity,
          params.project,
          params.traceId,
          spanId
        )
      ),
    [history, params.entity, params.project, params.traceId, routeContext]
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
  // return (
  //   // <PageEl>
  //     {/* <PageHeader
  //       objectType="Trace"
  //       objectName={
  //         params.traceId + params.spanId != null ? '/' + params.spanId : ''
  //       }
  //       actions={
  //         <Box display="flex" alignItems="flex-start">
  //           <Button
  //             variant="outlined"
  //             sx={{marginRight: 3, backgroundColor: globals.lightYellow}}
  //             onClick={() => console.log('new board trace')}>
  //             Open in board
  //           </Button>
  //           <Button
  //             variant="outlined"
  //             sx={{backgroundColor: globals.lightYellow, marginRight: 3}}>
  //             Compare
  //           </Button>
  //         </Box>
  //       }
  //     /> */}

  //     <Browse2Trace
  //       streamId={{
  //         entityName: params.entity,
  //         projectName: params.project,
  //         streamName: 'stream',
  //       }}
  //       traceId={params.traceId}
  //       spanId={params.spanId}
  //       setSelectedSpanId={setSelectedSpanId}
  //     />
  //   // </PageEl>
  // );
};
