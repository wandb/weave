import {Box} from '@material-ui/core';
import React, {FC, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {queryGetBoolean, queryToggleBoolean} from '../../urlQueryUtil';
import {CenteredAnimatedLoader} from '../common/Loader';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
  SimplePageLayoutWithHeader,
} from '../common/SimplePageLayout';
import {truncateID} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';
import {CallTraceView} from './CallTraceView';

// % of screen to give the trace view in horizontal mode
const TRACE_PCT = 40;

export const CallPage: FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const {useCall} = useWFHooks();

  const call = useCall({
    entity: props.entity,
    project: props.project,
    callId: props.callId,
  });
  const [verticalLayout, setVerticalLayout] = useState(true);
  if (call.loading) {
    return <CenteredAnimatedLoader />;
  } else if (call.result === null) {
    return <div>Call not found</div>;
  }
  if (verticalLayout) {
    return (
      <CallPageInnerVertical
        {...props}
        setVerticalLayout={setVerticalLayout}
        call={call.result}
      />
    );
  }
  return (
    <CallPageInnerHorizontal
      {...props}
      setVerticalLayout={setVerticalLayout}
      call={call.result}
    />
  );
};

const useCallTabs = (call: CallSchema) => {
  const codeURI = call.opVersionRef;
  return [
    {
      label: 'Call',
      content: <CallDetails call={call} />,
    },
    ...(codeURI
      ? [
          {
            label: 'Code',
            content: <Browse2OpDefCode uri={codeURI} />,
          },
        ]
      : []),
    {
      label: 'Summary',
      content: <CallSummary call={call} />,
    },
  ];
};

const CallPageInnerHorizontal: FC<{
  call: CallSchema;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const {traceId, callId, spanName} = call;

  const title = `${spanName}: ${truncateID(callId)}`;
  const traceTitle = `Trace: ${truncateID(traceId)}`;

  const callTabs = useCallTabs(call);

  return (
    <SimplePageLayout
      title={traceTitle}
      tabs={[
        {
          label: 'Trace',
          content: (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: '1 1 auto',
                overflow: 'hidden',
              }}>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  flex: `1 1 ${TRACE_PCT}%`,
                  height: TRACE_PCT,
                  overflow: 'hidden',
                }}>
                <CallTraceView call={call} />
              </Box>
              <Box
                sx={{
                  borderTop: '1px solid #e0e0e0',
                  display: 'flex',
                  flexDirection: 'column',
                  flex: `1 1 ${100 - TRACE_PCT}%`,
                  height: 100 - TRACE_PCT,
                  overflow: 'hidden',
                }}>
                <SimplePageLayoutContext.Provider value={{}}>
                  <SimplePageLayout
                    title={title}
                    // menuItems={callMenuItems}
                    tabs={callTabs}
                  />
                </SimplePageLayoutContext.Provider>
              </Box>
            </Box>
          ),
        },
      ]}
    />
  );
};

const CallPageInnerVertical: FC<{
  call: CallSchema;
  setVerticalLayout: (vertical: boolean) => void;
}> = ({call, setVerticalLayout}) => {
  const callTabs = useCallTabs(call);
  const history = useHistory();
  const showTraceTree = queryGetBoolean(history, 'tracetree', true);
  const onToggleTraceTree = () => {
    queryToggleBoolean(history, 'tracetree', true);
  };
  return (
    <SimplePageLayoutWithHeader
      headerExtra={
        <Box
          sx={{
            height: '47px',
          }}>
          <Button
            icon="layout-tabs"
            tooltip={`${showTraceTree ? 'Hide' : 'Show'} trace tree`}
            variant="ghost"
            active={showTraceTree ?? false}
            onClick={onToggleTraceTree}
          />
        </Box>
      }
      isSidebarOpen={showTraceTree}
      headerContent={<CallOverview call={call} />}
      leftSidebar={<CallTraceView call={call} />}
      tabs={callTabs}
    />
  );
};
