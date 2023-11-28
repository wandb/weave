import {OpDef} from '@wandb/weave/core';

// In Weave expression language, certain op styles receive their first
// input from the LHS of the expression, instead of as an input parameter
export function shouldSkipOpFirstInput(opDef: OpDef): boolean {
  return ['chain', 'brackets', 'binary'].includes(opDef.renderInfo.type);
}

const SHOW_DEBUG_LOG = false;

export const consoleLog = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.log(...msg);
  }
};

export const consoleGroup = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.group(...msg);
  }
};

export const consoleWarn = (...msg: any[]) => {
  if (SHOW_DEBUG_LOG) {
    console.warn(...msg);
  }
};

export function formatRelativeTime(unixTimestamp: number): string {
  const timestamp = new Date(unixTimestamp); // Unix timestamp is in ms
  const now = new Date();
  let timeDiff = now.getTime() - timestamp.getTime(); // difference in milliseconds

  const inFuture = timeDiff < 0;
  timeDiff = Math.abs(timeDiff);

  const seconds = timeDiff / 1000;
  const minutes = seconds / 60;
  const hours = minutes / 60;
  const days = hours / 24;
  const months = days / 30;
  const years = days / 365;

  const timeString = (value: number, unit: string) => {
    return `${Math.floor(value)} ${unit}${value >= 2 ? 's' : ''} ${
      inFuture ? 'from now' : 'ago'
    }`;
  };

  if (years >= 1) {
    return timeString(years, 'year');
  } else if (months >= 1) {
    return timeString(months, 'month');
  } else if (days >= 1) {
    return timeString(days, 'day');
  } else if (hours >= 1) {
    return timeString(hours, 'hour');
  } else if (minutes >= 1) {
    return timeString(minutes, 'minute');
  } else {
    return inFuture ? 'in a moment' : 'just now';
  }
}
