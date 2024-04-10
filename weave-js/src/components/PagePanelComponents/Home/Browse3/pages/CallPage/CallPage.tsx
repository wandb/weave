import {Box} from '@material-ui/core';
import {Loading} from '@wandb/weave/components/Loading';
import React, {FC, useCallback} from 'react';
import {useHistory} from 'react-router-dom';

import {Button} from '../../../../../Button';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {TRACETREE_PARAM, useWeaveflowCurrentRouteContext} from '../../context';
import {isEvaluateOp} from '../common/heuristics';
import {CenteredAnimatedLoader} from '../common/Loader';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {useURLSearchParamsDict} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';
import {CallTraceView, useCallFlattenedTraceTree} from './CallTraceView';
import {ExceptionDetails, getExceptionInfo} from './Exceptions';

export const CallPage: FC<{
  entity: string;
  project: string;
  callId: string;
  path?: string;
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
  const excInfo = getExceptionInfo(call.rawSpan.exception);
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
    ...('traceback' in excInfo
      ? [
          {
            label: 'Error details',
            content: <ExceptionDetails exceptionInfo={excInfo} />,
          },
        ]
      : []),
  ];
};

const CallPageInnerVertical: FC<{
  call: CallSchema;
  path?: string;
}> = ({call, path}) => {
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();

  const query = useURLSearchParamsDict();
  const showTraceTree =
    TRACETREE_PARAM in query
      ? query[TRACETREE_PARAM] === '1'
      : !isEvaluateOp(call.spanName);

  const onToggleTraceTree = useCallback(() => {
    history.replace(
      currentRouter.callUIUrl(
        call.entity,
        call.project,
        call.traceId,
        call.callId,
        path,
        !showTraceTree
      )
    );
  }, [
    call.callId,
    call.entity,
    call.project,
    call.traceId,
    currentRouter,
    history,
    path,
    showTraceTree,
  ]);

  const tree = useCallFlattenedTraceTree(call, path ?? null);
  const {rows, expandKeys, loading} = tree;
  let {selectedCall} = tree;

  const assumeCallIsSelectedCall = path == null || path === '';

  if (assumeCallIsSelectedCall) {
    // Allows us to bypass the loading state when the call is already selected.
    selectedCall = call;
  }

  const callTabs = useCallTabs(selectedCall);

  if (loading && !assumeCallIsSelectedCall) {
    return <Loading centered />;
  }

  return (
    <SimplePageLayoutWithHeader
      headerExtra={
        <Box
          sx={{
            height: '41px',
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
          <Loading centered />
        ) : (
          <CallTraceView
            call={call}
            selectedCall={selectedCall}
            rows={rows}
            forcedExpandKeys={expandKeys}
            path={path}
          />
        )
      }
      tabs={callTabs}
    />
  );
};
