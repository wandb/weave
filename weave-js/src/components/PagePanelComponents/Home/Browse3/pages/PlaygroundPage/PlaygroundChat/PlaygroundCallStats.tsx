import {Button} from '@wandb/weave/components/Button';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../../context';
import {Reactions} from '../../../feedback/Reactions';
import {addCostsToCallResults} from '../../CallPage/cost/costUtils';
import {TraceCostStats} from '../../CallPage/cost/TraceCostStats';
import {useWFHooks} from '../../wfReactInterface/context';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {CallSchema} from '../../wfReactInterface/wfDataModelHooksInterface';

type StatusCode = 'OK' | 'ERROR';
const traceCallStatusCode = (call: TraceCallSchema): StatusCode => {
  return call.exception ? 'ERROR' : 'OK';
};

export const PlaygroundCallStats = ({call}: {call: TraceCallSchema}) => {
  const {useCalls} = useWFHooks();
  const [entityName, projectName] = call?.project_id?.split('/') || [];
  const callId = call?.id || '';

  // Convert TraceCallSchema to CallSchema
  const callSchema: CallSchema = useMemo(() => ({
    entity: entityName,
    project: projectName,
    callId,
    traceId: call.trace_id,
    parentId: call.parent_id ?? null,
    userId: call.wb_user_id ?? null,
    runId: call.wb_run_id ?? null,
    spanName: call.op_name ?? '',
    displayName: call.display_name ?? null,
    opVersionRef: call.op_name ?? null,
    rawSpan: {
      name: call.op_name,
      inputs: call.inputs,
      output: call.output ?? {},
      status_code: traceCallStatusCode(call),
      exception: call.exception,
      attributes: call.attributes,
      summary: {
        ...call.summary ?? {},
        latency_s: (call.summary?.weave?.latency_ms ?? 0) / 1000,
      },
      span_id: call.id,
      trace_id: call.trace_id,
      parent_id: call.parent_id ?? undefined,
      timestamp: new Date(call.started_at).getTime(),
      start_time_ms: new Date(call.started_at).getTime(),
      end_time_ms: call.ended_at ? new Date(call.ended_at).getTime() : undefined,
    },
    traceCall: call
  }), [call, entityName, projectName, callId]);

  // Fetch cost data
  const costCols = useMemo(() => ['id'], []);
  const costs = useCalls(
    entityName,
    projectName,
    {
      callIds: [callId],
    },
    undefined,
    undefined,
    undefined,
    undefined,
    costCols,
    undefined,
    {
      includeCosts: true,
    }
  );

  // Merge cost data with the call
  const callWithCosts = useMemo(() => {
    if (!costs.result || costs.result.length === 0) {
      return callSchema;
    }
    const [updatedCall] = addCostsToCallResults([callSchema], costs.result);
    return updatedCall;
  }, [callSchema, costs.result]);

  const latency = callWithCosts?.traceCall?.summary?.weave?.latency_ms ?? 0;
  const usageData = callWithCosts?.traceCall?.summary?.usage;
  const costData = callWithCosts?.traceCall?.summary?.weave?.costs;

  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  if (!callId) {
    return null;
  }

  const weaveRef = makeRefCall(entityName, projectName, callId);
  const callLink = peekingRouter.callUIUrl(
    entityName,
    projectName,
    '',
    callId,
    null,
    false
  );

  return (
    <Tailwind>
      <div className="flex w-full items-center justify-center gap-8 py-8">
        <TraceCostStats 
          usageData={usageData}
          costData={costData}
          latency_ms={latency}
          costLoading={costs.loading}
        />
        {(call.output as any)?.choices?.[0]?.finish_reason && (
          <Tooltip
            content="Finish Reason"
            trigger={
              <span>
                <Pill
                  icon="checkmark-circle"
                  label={(call.output as any).choices[0].finish_reason}
                  color="moon"
                  className="-ml-[8px] bg-transparent text-moon-500 dark:bg-transparent dark:text-moon-500"
                />
              </span>
            }
          />
        )}
        {callLink && (
          <Button
            size="small"
            variant="quiet"
            icon="open-new-tab"
            onClick={() => {
              history.push(callLink);
            }}
            tooltip="Open in new tab">
            View trace
          </Button>
        )}
        {weaveRef && <Reactions weaveRef={weaveRef} forceVisible={true} />}
      </div>
    </Tailwind>
  );
};
