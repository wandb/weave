import {Button} from '@wandb/weave/components/Button';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {makeRefCall} from '@wandb/weave/util/refs';
import React from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../../context';
import {Reactions} from '../../../feedback/Reactions';
import {TraceCostStats} from '../../CallPage/cost';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';

export const PlaygroundCallStats = ({call}: {call: TraceCallSchema}) => {
  const [entityName, projectName] = call?.project_id?.split('/') || [];
  const callId = call?.id || '';
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

  const latency = call?.summary?.weave?.latency_ms ?? 0;
  const usageData = call?.summary?.usage;
  const costData = call?.summary?.weave?.costs;

  return (
    <Tailwind>
      <div className="flex w-full items-center justify-center gap-8 py-8">
        <TraceCostStats
          usageData={usageData}
          costData={costData}
          latency_ms={latency}
          costLoading={false}
        />
        {(call.output as any)?.choices?.[0]?.finish_reason && (
          <Tooltip
            content="Finish reason"
            trigger={
              // Placing in span so tooltip shows up
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
            variant="ghost"
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
