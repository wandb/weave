import Box from '@mui/material/Box';
import {Loading} from '@wandb/weave/components/Loading';
import {urlPrefixed} from '@wandb/weave/config';
import {useViewTraceEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {makeRefCall} from '../../../../../../util/refs';
import {Button} from '../../../../../Button';
import {Tailwind} from '../../../../../Tailwind';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
import {
  FEEDBACK_EXPAND_PARAM,
  TRACETREE_PARAM,
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {FeedbackGrid} from '../../feedback/FeedbackGrid';
import {ScorerFeedbackGrid} from '../../feedback/ScorerFeedbackGrid';
import {FeedbackSidebar} from '../../feedback/StructuredFeedback/FeedbackSidebar';
import {useHumanAnnotationSpecs} from '../../feedback/StructuredFeedback/tsHumanFeedback';
import {NotFoundPanel} from '../../NotFoundPanel';
import {isCallChat} from '../ChatView/hooks';
import {isEvaluateOp} from '../common/heuristics';
import {CenteredAnimatedLoader} from '../common/Loader';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../common/SimplePageLayout';
import {CompareEvaluationsPageContent} from '../CompareEvaluationsPage/CompareEvaluationsPage';
import {useURLSearchParamsDict} from '../util';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallChat} from './CallChat';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';
import {CallTraceView, useCallFlattenedTraceTree} from './CallTraceView';
import {PaginationControls} from './PaginationControls';
import {TabUseCall} from './TabUseCall';

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

export const useShowRunnableUI = () => {
  return false;
  // Uncomment to re-enable
  // const viewerInfo = useViewerInfo();
  // return viewerInfo.loading ? false : viewerInfo.userInfo?.admin;
};

const useCallTabs = (call: CallSchema) => {
  const codeURI = call.opVersionRef;
  const {entity, project, callId} = call;
  const weaveRef = makeRefCall(entity, project, callId);

  const {isPeeking} = useContext(WeaveflowPeekContext);
  const showTryInPlayground =
    !isPeeking || !window.location.toString().includes('/weave/playground');

  const handleOpenInPlayground = () => {
    window.open(
      urlPrefixed(`/${entity}/${project}/weave/playground/${callId}`),
      '_blank'
    );
  };

  return [
    // Disabling Evaluation tab until it's better for single evaluation
    ...(false && isEvaluateOp(call.spanName)
      ? [
          {
            label: 'Evaluation',
            content: (
              <CompareEvaluationsPageContent
                entity={call.entity}
                project={call.project}
                evaluationCallIds={[call.callId]}
                // Dont persist metric selection in the URL
                selectedMetrics={{}}
                setSelectedMetrics={() => {}}
                // Dont persist changes to evaluationCallIds in the URL
                onEvaluationCallIdsUpdate={() => {}}
              />
            ),
          },
        ]
      : []),
    ...(isCallChat(call)
      ? [
          {
            label: 'Chat',
            content: (
              <>
                {showTryInPlayground && (
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'flex-end',
                      width: '100%',
                      padding: '8px 16px',
                    }}>
                    <Button
                      variant="ghost"
                      startIcon="robot-service-member"
                      onClick={handleOpenInPlayground}>
                      Try in playground
                    </Button>
                  </Box>
                )}
                <ScrollableTabContent>
                  <Tailwind>
                    <CallChat call={call.traceCall!} />
                  </Tailwind>
                </ScrollableTabContent>
              </>
            ),
          },
        ]
      : []),
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
      label: 'Scores',
      content: (
        <Tailwind style={{height: '100%', overflow: 'auto'}}>
          <ScorerFeedbackGrid
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
      content: (
        <Tailwind style={{height: '100%', overflow: 'auto'}}>
          <CallSummary call={call} />
        </Tailwind>
      ),
    },
    {
      label: 'Use',
      content: (
        <ScrollableTabContent>
          <Tailwind>
            <TabUseCall call={call} />
          </Tailwind>
        </ScrollableTabContent>
      ),
    },
  ];
};

const CallPageInnerVertical: FC<{
  call: CallSchema;
  path?: string;
}> = ({call, path}) => {
  useViewTraceEvent(call);

  const {useCall} = useWFHooks();
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();

  const query = useURLSearchParamsDict();
  const showTraceTree =
    TRACETREE_PARAM in query
      ? query[TRACETREE_PARAM] === '1'
      : !isEvaluateOp(call.spanName);
  const showFeedbackExpand =
    FEEDBACK_EXPAND_PARAM in query
      ? query[FEEDBACK_EXPAND_PARAM] === '1'
      : false;

  const onToggleTraceTree = useCallback(() => {
    history.replace(
      currentRouter.callUIUrl(
        call.entity,
        call.project,
        call.traceId,
        call.callId,
        path,
        !showTraceTree,
        showFeedbackExpand ? true : undefined
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
    showFeedbackExpand,
  ]);
  const onToggleFeedbackExpand = useCallback(() => {
    history.replace(
      currentRouter.callUIUrl(
        call.entity,
        call.project,
        call.traceId,
        call.callId,
        path,
        showTraceTree,
        !showFeedbackExpand ? true : undefined
      )
    );
  }, [currentRouter, history, path, showTraceTree, call, showFeedbackExpand]);
  const {humanAnnotationSpecs, specsLoading} = useHumanAnnotationSpecs(
    call.entity,
    call.project
  );

  const tree = useCallFlattenedTraceTree(call, path ?? null);
  const {rows, expandKeys, loading, costLoading, selectedCall} = tree;
  const callComplete = useCall({
    entity: selectedCall.entity,
    project: selectedCall.project,
    callId: selectedCall.callId,
  });
  const callCompleteWithCosts = useMemo(() => {
    if (callComplete.result?.traceCall == null) {
      return callComplete.result;
    }
    return {
      ...callComplete.result,
      traceCall: {
        ...callComplete.result?.traceCall,
        summary: {
          ...callComplete.result?.traceCall?.summary,
          weave: {
            ...callComplete.result?.traceCall?.summary?.weave,
            // Only selectedCall has costs, injected when creating
            // the trace tree
            costs: selectedCall.traceCall?.summary?.weave?.costs,
          },
        },
      },
    };
  }, [callComplete.result, selectedCall]);

  const assumeCallIsSelectedCall = path == null || path === '';
  const [currentCall, setCurrentCall] = useState(call);

  useEffect(() => {
    if (assumeCallIsSelectedCall) {
      setCurrentCall(selectedCall);
    }
  }, [assumeCallIsSelectedCall, selectedCall]);

  useEffect(() => {
    if (callCompleteWithCosts != null) {
      setCurrentCall(callCompleteWithCosts);
    }
  }, [callCompleteWithCosts]);

  const {rowIdsConfigured} = useContext(TableRowSelectionContext);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const showPaginationControls = isPeeking && rowIdsConfigured;

  const callTabs = useCallTabs(currentCall);

  if (loading && !assumeCallIsSelectedCall) {
    return <Loading centered />;
  }

  return (
    <SimplePageLayoutWithHeader
      headerExtra={
        <Box
          sx={{
            display: 'flex',
            width: '100%',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
          {showPaginationControls && (
            <PaginationControls call={call} path={path} />
          )}
          <Box sx={{marginLeft: showPaginationControls ? 0 : 'auto'}}>
            <Button
              icon="layout-tabs"
              tooltip={`${showTraceTree ? 'Hide' : 'Show'} trace tree`}
              variant="ghost"
              active={showTraceTree ?? false}
              onClick={onToggleTraceTree}
            />
            <Button
              icon="marker"
              tooltip={`${showFeedbackExpand ? 'Hide' : 'Show'} feedback`}
              variant="ghost"
              active={showFeedbackExpand ?? false}
              onClick={onToggleFeedbackExpand}
              className="ml-4"
            />
          </Box>
        </Box>
      }
      isRightSidebarOpen={showFeedbackExpand}
      rightSidebarContent={
        <Tailwind style={{display: 'contents'}}>
          <div className="flex h-full flex-col">
            <FeedbackSidebar
              humanAnnotationSpecs={humanAnnotationSpecs}
              specsLoading={specsLoading}
              callID={currentCall.callId}
              entity={currentCall.entity}
              project={currentCall.project}
            />
          </div>
        </Tailwind>
      }
      headerContent={<CallOverview call={currentCall} />}
      isLeftSidebarOpen={showTraceTree}
      leftSidebarContent={
        <Tailwind style={{display: 'contents'}}>
          <div className="h-full bg-moon-50">
            {loading ? (
              <Loading centered />
            ) : (
              <CallTraceView
                call={call}
                selectedCall={currentCall}
                rows={rows}
                forcedExpandKeys={expandKeys}
                path={path}
                costLoading={costLoading}
              />
            )}
          </div>
        </Tailwind>
      }
      tabs={callTabs}
    />
  );
};
