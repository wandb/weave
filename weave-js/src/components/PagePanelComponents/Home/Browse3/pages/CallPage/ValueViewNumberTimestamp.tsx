import {Timestamp} from '@wandb/weave/components/Timestamp';
import React from 'react';

// Seconds relative to Unix Epoch
const JAN_1_2000_S = 946_684_800;
const JAN_1_2100_S = 4_102_444_800;
const JAN_1_2000_MS = 1000 * JAN_1_2000_S;
const JAN_1_2100_MS = 1000 * JAN_1_2100_S;

// Regex pattern to match likely timestamp field names
// First part has the base fields likely to be timestamps, second part
// has the optional suffixes that are likely
const TIMESTAMP_PATTERN =
  /^(?:.*_)?(created|started|ended|updated|finished|duration|time|timestamp)(?:_(?:at|ms))?$/i;

export const likelyTimestampName = (field: string) => {
  return TIMESTAMP_PATTERN.test(field);
};

export const isProbablyTimestampMs = (value: number, field?: string) => {
  const fieldIsLikely = !field || likelyTimestampName(field);
  return fieldIsLikely && JAN_1_2000_MS <= value && value <= JAN_1_2100_MS;
};

export const isProbablyTimestampSec = (value: number, field?: string) => {
  const fieldIsLikely = !field || likelyTimestampName(field);
  return fieldIsLikely && JAN_1_2000_S <= value && value <= JAN_1_2100_S;
};

export const isProbablyTimestamp = (value: number, field?: string) => {
  const fieldIsLikely = !field || likelyTimestampName(field);
  return (
    fieldIsLikely &&
    (isProbablyTimestampMs(value, field) ||
      isProbablyTimestampSec(value, field))
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
