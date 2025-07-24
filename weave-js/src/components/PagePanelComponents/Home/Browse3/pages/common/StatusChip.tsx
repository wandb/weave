/**
 * Colored chip representing Call state.
 * Can be used for either actual state or aggregate state accounting for descendants.
 */
import {IconName} from '@wandb/weave/components/Icon';
import {IconOnlyPill, Pill, TagColorName} from '@wandb/weave/components/Tag';
import _ from 'lodash';
import React from 'react';

import {Tooltip} from '../../../../../Tooltip';
import {
  ComputedCallStatuses,
  ComputedCallStatusType,
} from '../wfReactInterface/traceServerClientTypes';

export const FILTER_TO_STATUS: Record<string, ComputedCallStatusType> =
  _.invert(ComputedCallStatuses) as Record<string, ComputedCallStatusType>;

type StatusChipProps = {
  value: ComputedCallStatusType;
  iconOnly?: boolean;
  tooltipOverride?: string;
};

type CallStatusInfo = {
  icon: IconName;
  label: string;
  color: TagColorName;
  tooltip: string;
};
export const STATUS_INFO: Record<ComputedCallStatusType, CallStatusInfo> = {
  [ComputedCallStatuses.success]: {
    icon: 'checkmark-circle',
    label: 'Finished',
    color: 'green',
    tooltip: 'This call succeeded.',
  },
  [ComputedCallStatuses.descendant_error]: {
    icon: 'warning',
    label: 'Finished',
    color: 'gold',
    tooltip:
      'This call succeeded, but one or more descendants failed. Filtering requires logging with `weave>=0.51.47` python client.',
  },
  [ComputedCallStatuses.error]: {
    icon: 'failed',
    label: 'Error',
    color: 'red',
    tooltip: 'This call failed.',
  },
  [ComputedCallStatuses.running]: {
    icon: 'randomize-reset-reload',
    label: 'Running',
    color: 'cactus',
    tooltip: 'This call has not finished.',
  },
};

export const StatusChip = ({
  value,
  iconOnly,
  tooltipOverride,
}: StatusChipProps) => {
  const statusInfo = STATUS_INFO[value];
  const {icon, color, label, tooltip} = statusInfo;

  const pill = iconOnly ? (
    <IconOnlyPill icon={icon} color={color} style={{flexShrink: 1}} />
  ) : (
    <Pill icon={icon} color={color} label={label} />
  );
  return (
    <Tooltip
      trigger={<span>{pill}</span>}
      content={tooltipOverride ?? tooltip}
    />
  );
};
