import Box from '@mui/material/Box';
import {urlPrefixed} from '@wandb/weave/config';
import {useViewTraceEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {FC, useCallback, useContext, useEffect, useRef} from 'react';

import {makeRefCall} from '../../../../../../util/refs';
import {Button} from '../../../../../Button';
import {Tailwind} from '../../../../../Tailwind';
import {Browse2OpDefCode} from '../../../Browse2/Browse2OpDefCode';
import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
import {TraceNavigator} from '../../components/TraceNavigator/TraceNavigator';
import {WeaveflowPeekContext} from '../../context';
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
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CallChat} from './CallChat';
import {CallDetails} from './CallDetails';
import {CallOverview} from './CallOverview';
import {CallSummary} from './CallSummary';
import {PaginationControls} from './PaginationControls';
import {TabUseCall} from './TabUseCall';

type CallPageProps = {
  entity: string;
  project: string;
  rootCallId: string;
  setRootCallId: (callId: string) => void;
  descendentCallId?: string;
  setDescendentCallId: (descendentCallId: string | undefined) => void;
  hideTraceTree?: boolean;
  setHideTraceTree: (hideTraceTree: boolean | undefined) => void;
  showFeedback?: boolean;
  setShowFeedback: (showFeedback: boolean | undefined) => void;
};

type CallPageInnerProps = CallPageProps & {
  descendentCallId: string;
  setDescendentCallId: (descendentCallId: string) => void;
  descendentCall: CallSchema;
  callIsStale: boolean;
};

export const CallPage: FC<CallPageProps> = props => {
  const {useCall} = useWFHooks();

  const descendentCallId = props.descendentCallId ?? props.rootCallId;

  // Note to future devs: We could delay the cost (and i/o) fetching. This is
  // just needed to validate that the call truly exists.
  const call = useCall(
    {
      entity: props.entity,
      project: props.project,
      callId: descendentCallId,
    },
    {includeCosts: true}
  );

  // This is a little hack, but acceptable for now.
  // We don't want the entire page to re-render when the call result is updated.
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
          descendentCallId={descendentCallId}
          descendentCall={call.result}
          callIsStale={call.result.callId !== descendentCallId}
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
          descendentCallId={descendentCallId}
          descendentCall={lastResult.current}
          callIsStale={lastResult.current.callId !== descendentCallId}
        />
      );
    }
  }
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

const CallPageInnerVertical: FC<CallPageInnerProps> = ({
  descendentCall: call,
  descendentCallId: callId,
  setRootCallId: setCallId,
  setHideTraceTree,
  setShowFeedback,
  showFeedback,
  hideTraceTree,
  callIsStale,
}) => {
  useViewTraceEvent(call);

  const hideTraceTreeDefault = isEvaluateOp(call.spanName);
  const showFeedbackDefault = false;
  const hideTraceTreeActual =
    hideTraceTree != null ? hideTraceTree : hideTraceTreeDefault;
  const showFeedbackActual =
    showFeedback != null ? showFeedback : showFeedbackDefault;

  const onToggleTraceTree = useCallback(() => {
    const targetValue = !hideTraceTreeActual;
    if (targetValue === hideTraceTreeDefault) {
      setHideTraceTree(undefined);
    } else {
      setHideTraceTree(targetValue);
    }
  }, [hideTraceTreeActual, hideTraceTreeDefault, setHideTraceTree]);
  const onToggleFeedbackExpand = useCallback(() => {
    const targetValue = !showFeedbackActual;
    if (targetValue === showFeedbackDefault) {
      setShowFeedback(undefined);
    } else {
      setShowFeedback(targetValue);
    }
  }, [setShowFeedback, showFeedbackDefault, showFeedbackActual]);

  const {humanAnnotationSpecs, specsLoading} = useHumanAnnotationSpecs(
    call.entity,
    call.project
  );

  const {rowIdsConfigured} = useContext(TableRowSelectionContext);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const showPaginationControls = isPeeking && rowIdsConfigured;

  const callTabs = useCallTabs(call);

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
            <PaginationControls call={call} setRootCallId={setCallId} />
          )}
          <Box sx={{marginLeft: showPaginationControls ? 0 : 'auto'}}>
            <Button
              icon="layout-tabs"
              tooltip={`${!hideTraceTreeActual ? 'Hide' : 'Show'} trace tree`}
              variant="ghost"
              active={!hideTraceTreeActual}
              onClick={onToggleTraceTree}
            />
            <Button
              icon="marker"
              tooltip={`${showFeedbackActual ? 'Hide' : 'Show'} feedback`}
              variant="ghost"
              active={showFeedbackActual ?? false}
              onClick={onToggleFeedbackExpand}
              className="ml-4"
            />
          </Box>
        </Box>
      }
      isRightSidebarOpen={showFeedbackActual}
      rightSidebarContent={
        <Tailwind style={{display: 'contents'}}>
          <div className="flex h-full flex-col">
            <FeedbackSidebar
              humanAnnotationSpecs={humanAnnotationSpecs}
              specsLoading={specsLoading}
              callID={callId}
              entity={call.entity}
              project={call.project}
            />
          </div>
        </Tailwind>
      }
      headerContent={<CallOverview call={call} />}
      isLeftSidebarOpen={!hideTraceTreeActual}
      leftSidebarContent={
        <Tailwind style={{display: 'contents'}}>
          <div className="h-full bg-moon-50">
            <TraceNavigator
              entity={call.entity}
              project={call.project}
              selectedTraceId={call.traceId}
              selectedCallId={callId}
              setSelectedCallId={setCallId}
            />
          </div>
        </Tailwind>
      }
      tabs={callTabs}
      dimMainContent={callIsStale}
    />
  );
};
