/**
 * Colored chip representing Run / Run Queue Item / Sweep state.
 *
 * TODO: Split into multiple components for the different use cases?
 *
 * See https://www.notion.so/wandbai/Run-Run-Queue-Item-and-Sweep-States-61c84c5d0f0a40c19046f1c58db5bb19?pvs=4
 * for documentation on the meaning of each state.
 */
import {IconName} from '@wandb/weave/components/Icon';
import {Pill, TagColorName} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';

export const RUN_STATE = [
  'idle',
  'preempting',
  'preempted',
  'pending',
  'queued',
  'starting',
  'running',
  'finished',
  'failed',
  'crashed',
  'stopping',
  'stopped',
  'killed',
] as const;
export type RunStateType = (typeof RUN_STATE)[number];

type RunStateProps = {
  value: string;
  // By default we will show an icon, but you can turn it off.
  noIcon?: boolean;
  tooltip?: boolean;
};

type RunStateInfo = {
  icon: IconName;
  color: TagColorName;
  tooltip?: string;
};
const RUN_STATE_INFO: Record<RunStateType, RunStateInfo> = {
  idle: {
    icon: 'idle',
    color: 'red',
    tooltip:
      'The run cannot start because there are no active agents on the queue.',
  },
  preempting: {
    icon: 'loading',
    color: 'sienna',
  },
  preempted: {
    icon: 'failed',
    color: 'sienna',
  },
  pending: {
    icon: 'loading', // sweep state
    color: 'moon',
    tooltip:
      'The run has been picked up by an agent but has not yet started. This could be due to resources being unavailable on the cluster.',
  },
  queued: {
    icon: 'queued',
    color: 'moon',
    tooltip: 'The run is waiting for an agent to process it.',
  },
  starting: {
    icon: 'run',
    color: 'teal',
  },
  running: {
    icon: 'run',
    color: 'teal',
    tooltip: 'The run is currently executing.',
  },
  finished: {
    icon: 'checkmark-circle',
    color: 'green',
    tooltip: 'The job completed successfully.',
  },
  failed: {
    icon: 'failed',
    color: 'red',
    tooltip:
      'The run ended with a non-zero exit code or the run failed to start.',
  },
  crashed: {
    icon: 'warning',
    color: 'red',
    tooltip: 'The run stopped sending data or did not successfully start.',
  },
  stopping: {
    icon: 'loading',
    color: 'sienna',
  },
  stopped: {
    icon: 'failed',
    color: 'sienna',
  },
  killed: {
    icon: 'failed',
    color: 'sienna',
    tooltip: 'The job was killed by the user.',
  },
};

export const RunState = ({value, noIcon, tooltip}: RunStateProps) => {
  if (!value) {
    return null;
  }

  const stateStr = value.toLowerCase() as RunStateType;
  const label = stateStr.charAt(0).toUpperCase() + stateStr.slice(1);

  const stateInfo = RUN_STATE_INFO[stateStr];
  if (stateInfo == null) {
    return <Pill color="moon" label={label} />;
  }

  const pill = (
    <Pill
      icon={noIcon ? undefined : stateInfo.icon}
      color={stateInfo.color}
      label={label}
    />
  );

  if (!tooltip || stateInfo.tooltip == null) {
    return pill;
  }
  return (
    <Tooltip
      position="top center"
      content={stateInfo.tooltip}
      trigger={<div>{pill}</div>}
    />
  );
};
