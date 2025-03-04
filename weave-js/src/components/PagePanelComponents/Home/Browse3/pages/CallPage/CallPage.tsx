import Box from '@mui/material/Box';
import {urlPrefixed} from '@wandb/weave/config';
import {useViewTraceEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {makeRefCall} from '../../../../../../util/refs';
import {Button} from '../../../../../Button';
import {Tailwind} from '../../../../../Tailwind';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
import {TraceNavigator} from '../../components/TraceNavigator/TraceNavigator';
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
import {PaginationControls} from './PaginationControls';
import {TabUseCall} from './TabUseCall';

export const CallPage: FC<{
  entity: string;
  project: string;
  callId: string;
  setCallId: (callId: string) => void;
  path?: string;
}> = props => {
  const {useCall} = useWFHooks();

  const call = useCall({
    entity: props.entity,
    project: props.project,
    callId: props.callId,
  });
  // TODO: CLean this up!
  const lastResult = useRef(call.result);
  useEffect(() => {
    if (call.result) {
      lastResult.current = call.result;
    }
  }, [call.result]);

  if (!call.loading) {
    if (call.result === null) {
      return <NotFoundPanel title="Call not found" />;
    } else {
      return (
        <CallPageInnerVertical
          {...props}
          call={call.result}
          setCallById={props.setCallId}
        />
      );
    }
  } else {
    if (lastResult.current === null) {
      return <CenteredAnimatedLoader />;
    } else {
      return (
        <CallPageInnerVertical
          {...props}
          call={lastResult.current}
          setCallById={props.setCallId}
        />
      );
    }
  }
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
  callId: string;
  setCallById: (callId: string) => void;
  path?: string;
}> = ({call, callId, setCallById: setCallId, path}) => {
  useViewTraceEvent(call);

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
        callId,
        path,
        !showTraceTree,
        showFeedbackExpand ? true : undefined
      )
    );
  }, [
    callId,
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
        callId,
        path,
        showTraceTree,
        !showFeedbackExpand ? true : undefined
      )
    );
  }, [
    history,
    currentRouter,
    call.entity,
    call.project,
    call.traceId,
    callId,
    path,
    showTraceTree,
    showFeedbackExpand,
  ]);
  const {humanAnnotationSpecs, specsLoading} = useHumanAnnotationSpecs(
    call.entity,
    call.project
  );

  // TODO: remove this or understand it
  // const tree = useCallFlattenedTraceTree(call, path ?? null);
  // const {loading, selectedCall} = tree;
  const selectedCall = call;
  const callComplete = selectedCall;
  // useCall({
  //   entity: selectedCall.entity,
  //   project: selectedCall.project,
  //   callId: selectedCall.callId,
  // });
  const callCompleteWithCosts = callComplete;
  // useMemo(() => {
  //   if (callComplete.result?.traceCall == null) {
  //     return callComplete.result;
  //   }
  //   return {
  //     ...callComplete.result,
  //     traceCall: {
  //       ...callComplete.result?.traceCall,
  //       summary: {
  //         ...callComplete.result?.traceCall?.summary,
  //         weave: {
  //           ...callComplete.result?.traceCall?.summary?.weave,
  //           // Only selectedCall has costs, injected when creating
  //           // the trace tree
  //           costs: selectedCall.traceCall?.summary?.weave?.costs,
  //         },
  //       },
  //     },
  //   };
  // }, [callComplete.result, selectedCall]);

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
              callID={callId}
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
            <TraceNavigator
              entity={currentCall.entity}
              project={currentCall.project}
              selectedTraceId={currentCall.traceId}
              selectedCallId={callId}
              setSelectedCallId={setCallId}
            />
          </div>
        </Tailwind>
      }
      tabs={callTabs}
    />
  );
};
