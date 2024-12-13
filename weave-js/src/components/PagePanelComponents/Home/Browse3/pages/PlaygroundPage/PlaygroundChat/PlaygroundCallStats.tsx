import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {makeRefCall} from '@wandb/weave/util/refs';
import React from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../../context';
import {Reactions} from '../../../feedback/Reactions';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';

export const PlaygroundCallStats = ({call}: {call: TraceCallSchema}) => {
  let totalTokens = 0;
  if (call?.summary?.usage) {
    for (const key of Object.keys(call.summary.usage)) {
      totalTokens +=
        call.summary.usage[key].prompt_tokens ||
        call.summary.usage[key].input_tokens ||
        0;
      totalTokens +=
        call.summary.usage[key].completion_tokens ||
        call.summary.usage[key].output_tokens ||
        0;
    }
  }

  const [entityName, projectName] = call?.project_id?.split('/') || [];
  const callId = call?.id || '';
  const latency = call?.summary?.weave?.latency_ms;
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
        <span>{totalTokens} tokens</span>
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
