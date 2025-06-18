import {Timestamp} from '@wandb/weave/components/Timestamp';
import React from 'react';

// Seconds relative to Unix Epoch
const JAN_1_2000_S = 946_684_800;
const JAN_1_2100_S = 4_102_444_800;
const JAN_1_2000_MS = 1000 * JAN_1_2000_S;
const JAN_1_2100_MS = 1000 * JAN_1_2100_S;

// Likely timestamp field names
const LIKELY_TIMESTAMP_NAMES = [
  'created',
  'started',
  'ended',
  'updated',
  'finished',
  'duration',
  'created_at',
  'started_at',
  'updated_at',
  'finished_at',
  'ended_at',
  'duration_ms',
  'time',
  'timestamp',
  'time_ms',
  'timestamp_ms',
];

export const likelyTimestampName = (field?: string) => {
  return LIKELY_TIMESTAMP_NAMES.some(name =>
    field?.toLowerCase().includes(name)
  );
};

export const isProbablyTimestampMs = (value: number, field?: string) => {
  return (
    likelyTimestampName(field) &&
    JAN_1_2000_MS <= value &&
    value <= JAN_1_2100_MS
  );
};

export const isProbablyTimestampSec = (value: number, field?: string) => {
  return (
    likelyTimestampName(field) && JAN_1_2000_S <= value && value <= JAN_1_2100_S
  );
};

export const isProbablyTimestamp = (value: number, field?: string) => {
  return (
    isProbablyTimestampMs(value, field) || isProbablyTimestampSec(value, field)
  );
};

type ValueViewNumberTimestampProps = {
  value: number;
};

export const ValueViewNumberTimestamp = ({
  value,
}: ValueViewNumberTimestampProps) => {
  const epochSeconds = value >= JAN_1_2000_MS ? value / 1000 : value;
  return <Timestamp value={epochSeconds} format="X" />;
};
