/**
 * Colored chip representing Call state.
 * Can be used for either actual state or aggregate state accounting for descendants.
 */
import {IconName} from '@wandb/weave/components/Icon';
import {IconOnlyPill, Pill, TagColorName} from '@wandb/weave/components/Tag';
import React from 'react';

import {Tooltip} from '../../../../../Tooltip';

export const CALL_STATUS = ['SUCCESS', 'DESCENDANT_ERROR', 'ERROR', 'UNSET'];
export type CallStatusType = (typeof CALL_STATUS)[number];

type StatusChipProps = {
  value: CallStatusType;
  iconOnly?: boolean;
};

type CallStatusInfo = {
  icon: IconName;
  label: string;
  color: TagColorName;
  tooltip: string;
};
const STATUS_INFO: Record<CallStatusType, CallStatusInfo> = {
  SUCCESS: {
    icon: 'checkmark-circle',
    label: 'Finished',
    color: 'green',
    tooltip: 'This call succeeded.',
  },
  DESCENDANT_ERROR: {
    icon: 'warning',
    label: 'Finished',
    color: 'gold',
    tooltip: 'This call succeeded, but one or more descendants failed.',
  },
  ERROR: {
    icon: 'failed',
    label: 'Error',
    color: 'red',
    tooltip: 'This call failed.',
  },
  UNSET: {
    icon: 'randomize-reset-reload',
    label: 'Running',
    color: 'cactus',
    tooltip: 'This call has not finished.',
  },
};

export const StatusChip = ({value, iconOnly}: StatusChipProps) => {
  const statusInfo = STATUS_INFO[value];
  const {icon, color, label, tooltip} = statusInfo;

  const pill = iconOnly ? (
    <IconOnlyPill icon={icon} color={color} />
  ) : (
    <Pill icon={icon} color={color} label={label} />
  );
  return <Tooltip trigger={<span>{pill}</span>} content={tooltip} />;
};
