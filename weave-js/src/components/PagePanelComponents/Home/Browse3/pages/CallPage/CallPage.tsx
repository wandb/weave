import Box from '@mui/material/Box';
import {Loading} from '@wandb/weave/components/Loading';
import {useViewTraceEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {FC, useCallback} from 'react';
import {useHistory} from 'react-router-dom';

import {makeRefCall} from '../../../../../../util/refs';
import {Button} from '../../../../../Button';
import {Tailwind} from '../../../../../Tailwind';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {TRACETREE_PARAM, useWeaveflowCurrentRouteContext} from '../../context';
import {FeedbackGrid} from '../../feedback/FeedbackGrid';
import {NotFoundPanel} from '../../NotFoundPanel';
import {isEvaluateOp} from '../common/heuristics';
import {CenteredAnimatedLoader} from '../common/Loader';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {TabUseCall} from '../TabUseCall';
import {useURLSearchParamsDict} from '../util';
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
    return <NotFoundPanel title="Call not found" />;
  }
  return <CallPageInnerVertical {...props} call={call.result} />;
};

const useCallTabs = (call: CallSchema) => {
  const codeURI = call.opVersionRef;
  const {entity, project, callId} = call;
  const weaveRef = makeRefCall(entity, project, callId);
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
      label: 'Feedback',
      content: (
        <Tailwind style={{height: '100%', overflow: 'auto'}}>
          <FeedbackGrid
            entity={entity}
            project={project}
            weaveRef={weaveRef}
            objectType="call"
          />
        </Tailwind>
      ),
    },
    {
      label: 'Summary',
      content: <CallSummary call={call} />,
    },
    {
      label: 'Use',
      content: <TabUseCall call={call} />,
    },
  ];
};

const CallPageInnerVertical: FC<{
  call: CallSchema;
  path?: string;
}> = ({call, path}) => {
  useViewTraceEvent(call);

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
