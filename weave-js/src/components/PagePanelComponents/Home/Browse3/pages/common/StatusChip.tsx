/**
 * Colored chip representing Call state.
 * Can be used for either actual state or aggregate state accounting for descendants.
 */
import {IconName} from '@wandb/weave/components/Icon';
import {IconOnlyPill, Pill, TagColorName} from '@wandb/weave/components/Tag';
import React from 'react';

export const CALL_STATUS = ['SUCCESS', 'DESCENDANT_ERROR', 'ERROR'];
export type CallStatusType = (typeof CALL_STATUS)[number];

type StatusChipProps = {
  value: CallStatusType;
  iconOnly?: boolean;
};

type CallStatusInfo = {
  icon: IconName;
  label: string;
  color: TagColorName;
};
const STATUS_INFO: Record<CallStatusType, CallStatusInfo> = {
  SUCCESS: {
    icon: 'checkmark-circle',
    label: 'Finished',
    color: 'green',
  },
  DESCENDANT_ERROR: {
    icon: 'warning',
    label: 'Finished',
    color: 'sienna',
  },
  ERROR: {
    icon: 'failed',
    label: 'Error',
    color: 'red',
  },
};

export const StatusChip = ({value, iconOnly}: StatusChipProps) => {
  const statusInfo = STATUS_INFO[value];
  const {icon, color, label} = statusInfo;

  const pill = iconOnly ? (
    <IconOnlyPill icon={icon} color={color} />
  ) : (
    <Pill icon={icon} color={color} label={label} />
  );
  return pill;
};
