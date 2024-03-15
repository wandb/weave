import {Box} from '@material-ui/core';
import React, {FC} from 'react';
import {useHistory} from 'react-router-dom';
import {Loader} from 'semantic-ui-react';

import {Button} from '../../../../../Button';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {PATH_PARAM, TRACETREE_PARAM} from '../../context';
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
  // Note: use of history in this component is a sign that we are leaking
  // the concept of URL query parameters into the component. This is a
  // violation of the separation of concerns. We should refactor this
  // component to accept props for the query parameters it needs. History
  // consumption should only be in the top-level component that is responsible
  // for routing and URL query parameters.
  const history = useHistory();
  const showTraceTree = queryGetBoolean(history, TRACETREE_PARAM, true);
  const onToggleTraceTree = () => {
    queryToggleBoolean(history, TRACETREE_PARAM, true);
  };

  const path = queryGetString(history, PATH_PARAM);
  const tree = useCallFlattenedTraceTree(call, path);
  const {rows, expandKeys, loading} = tree;
  let {selectedCall} = tree;

  const assumeCallIsSelectedCall = path == null || path === '';

  if (assumeCallIsSelectedCall) {
    // Allows us to bypass the loading state when the call is already selected.
    selectedCall = call;
  }

  const callTabs = useCallTabs(selectedCall);

  if (loading && !assumeCallIsSelectedCall) {
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
        loading ? (
          <Loader active />
        ) : (
          <CallTraceView
            call={call}
            selectedCall={selectedCall}
            rows={rows}
            forcedExpandKeys={expandKeys}
          />
        )
      }
      tabs={callTabs}
    />
  );
};
