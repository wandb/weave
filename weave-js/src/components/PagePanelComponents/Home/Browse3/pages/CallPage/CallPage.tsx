import {Box} from '@material-ui/core';
import React, {FC} from 'react';
import {useHistory} from 'react-router-dom';
import {Loader} from 'semantic-ui-react';

import {Button} from '../../../../../Button';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {
  queryGetBoolean,
  queryGetString,
  queryToggleBoolean,
} from '../../urlQueryUtil';
import {CenteredAnimatedLoader} from '../common/Loader';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';
import {CallTraceView, useCallFlattenedTraceTree} from './CallTraceView';

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
  if (call.loading) {
    return <CenteredAnimatedLoader />;
  } else if (call.result === null) {
    return <div>Call not found</div>;
  }
  return <CallPageInnerVertical {...props} call={call.result} />;
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

const CallPageInnerVertical: FC<{
  call: CallSchema;
}> = ({call}) => {
  const history = useHistory();
  const showTraceTree = queryGetBoolean(history, 'tracetree', true);
  const onToggleTraceTree = () => {
    queryToggleBoolean(history, 'tracetree', true);
  };

  const path = queryGetString(history, 'path');
  const {rows, selectedCall, expandKeys, loading} = useCallFlattenedTraceTree(
    call,
    path
  );

  const callTabs = useCallTabs(selectedCall);

  if (loading) {
    return <Loader active />;
  }

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
      headerContent={<CallOverview call={selectedCall} />}
      leftSidebar={
        <CallTraceView
          call={call}
          selectedCall={selectedCall}
          rows={rows}
          forcedExpandKeys={expandKeys}
        />
      }
      tabs={callTabs}
    />
  );
};
