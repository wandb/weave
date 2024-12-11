import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../../context';
import {Reactions} from '../../../feedback/Reactions';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {formatTokenCount, formatTokenCost, getUsageInputTokens, getUsageOutputTokens} from '../../CallPage/cost/costUtils';
import {useWFHooks} from '../../wfReactInterface/context';
import {addCostsToCallResults} from '../../CallPage/cost/costUtils';
import {CallSchema} from '../../wfReactInterface/wfDataModelHooksInterface';

export const PlaygroundCallStats = ({call}: {call: TraceCallSchema}) => {
  const {useCalls} = useWFHooks();
  const [entityName, projectName] = call?.project_id?.split('/') || [];
  const callId = call?.id || '';

  // Convert TraceCallSchema to CallSchema
  const callSchema: CallSchema = useMemo(() => ({
    entity: entityName,
    project: projectName,
    callId: callId,
    traceId: call.trace_id,
    parentId: call.parent_id ?? undefined,
    userId: call.wb_user_id,
    runId: call.wb_run_id ?? undefined,
    traceCall: {
      ...call,
      summary: call.summary as any
    }
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

  // Debug logging
  // console.log('Cost query results:', costs.result);
  // console.log('Original call:', call);
  // console.log('Call schema:', callSchema);

  // Merge cost data with the call
  const callWithCosts = useMemo(() => {
    if (!costs.result || costs.result.length === 0) {
      return callSchema;
    }
    const [updatedCall] = addCostsToCallResults([callSchema], costs.result);
    console.log('Updated call with costs:', updatedCall);
    return updatedCall;
  }, [callSchema, costs.result]);

  let totalTokens = 0;
  let totalCost = 0;
  let inputTokens = 0;
  let outputTokens = 0;

  if (callWithCosts?.traceCall?.summary?.usage) {
    for (const key of Object.keys(callWithCosts.traceCall.summary.usage)) {
      const usage = callWithCosts.traceCall.summary.usage[key];
      inputTokens += getUsageInputTokens(usage);
      outputTokens += getUsageOutputTokens(usage);
      totalTokens = inputTokens + outputTokens;
    }
  }

  if (callWithCosts?.traceCall?.summary?.weave?.costs) {
    for (const modelCosts of Object.values(callWithCosts.traceCall.summary.weave.costs)) {
      totalCost += (modelCosts.prompt_tokens_total_cost ?? 0) + 
                  (modelCosts.completion_tokens_total_cost ?? 0);
    }
  }

  const latency = callWithCosts?.traceCall?.summary?.weave?.latency_ms;
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
      <div className="flex w-full flex-wrap items-center justify-center gap-8 py-8 text-sm text-moon-500">
        <span>Latency: {latency}ms</span>
        <span>•</span>
        {(call.output as any)?.choices?.[0]?.finish_reason && (
          <>
            <span>
              Finish reason: {(call.output as any).choices[0].finish_reason}
            </span>
            <span>•</span>
          </>
        )}
        <span>{formatTokenCount(inputTokens)} input tokens</span>
        <span>•</span>
        <span>{formatTokenCount(outputTokens)} output tokens</span>
        <span>•</span>
        <span>{formatTokenCost(totalCost)}</span>
        <span>•</span>
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
