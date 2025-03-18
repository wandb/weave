/**
 * Render UTC timestamp from server.
 */
import moment from 'moment';
import React from 'react';
import TimeAgo, {Formatter} from 'react-timeago';

import {Icon} from './Icon';
import {Tooltip} from './Tooltip';

type Value = string | number;

type TimestampProps = {
  // Acceptable format: "2022-10-04T14:24:44"
  // Acceptable format: 1704824493 (seconds since epoch)
  value: Value;

  // Force a specific format. Special case:
  // "relative" - e.g. "2 hours ago"
  // See: https://momentjs.com/docs/#/displaying/format/
  format?: string;

  // By default, a "relative" timestamp will update automatically.
  // If you don't want this behavior you can set this prop to false.
  live?: boolean;

  // If true, will omit the time when it's midnight (00:00)
  dropTimeWhenDefault?: boolean;
};

// Format a time difference to a micro string (1h, 1d, 1w, etc.)
const formatMicroTime = (then: moment.Moment): string => {
  const now = moment();
  const diffMs = now.diff(then);

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  // Only use weeks when it's an exact multiple
  if (days % 7 === 0) {
    const weeks = days / 7;
    if (weeks === 1) {
      return '1w';
    } else if (weeks > 1) {
      return `${weeks}w`;
    }
  }

  // Only use months when it's an exact multiple of 30
  if (days % 30 === 0) {
    const months = days / 30;
    if (months === 1) {
      return '1mo';
    } else if (months > 1) {
      return `${months}mo`;
    }
  }

  // Otherwise use days for more precision
  if (days >= 1) {
    return days === 1 ? '1d' : `${days}d`;
  } else if (hours >= 1) {
    return hours === 1 ? '1h' : `${hours}h`;
  } else {
    return '<1h';
  }
};

// Return short and long formatted versions of the provided timestamp.
export const formatTimestamp = (value: string, overrideFormat?: string) => {
  const then = moment.utc(value, 'YYYY-MM-DDTHH:mm:ss').local();
  return formatTimestampInternal(then, overrideFormat);
};

const formatTimestampInternal = (
  then: moment.Moment,
  overrideFormat?: string
) => {
  let format = overrideFormat;
  if (!format) {
    const now = moment();
    format = 'MMM Do YYYY [at] h:mma';
    if (now.year() === then.year()) {
      format = 'MMM Do [at] h:mma';
    }
  }

  const micro = formatMicroTime(then);

  return {
    // TODO: It would be nice if we could display a timezone string here to
    //       make it clear to the user this is local time. However, we don't have
    //       a reliable way to get it. We'd have to add a dependency on moment-timezone
    //       and then ask it to guess.
    //       REF: https://github.com/moment/moment/issues/162
    long: then.format('dddd, MMMM Do YYYY [at] h:mm:ss a'),
    short: then.format(format),
    micro,
  };
};

const valueToMoment = (value: Value): moment.Moment => {
  if (typeof value === 'number') {
    return moment.unix(value);
  }
  return moment.utc(value, 'YYYY-MM-DDTHH:mm:ss').local();
};

// See: https://www.npmjs.com/package/react-timeago#formatter-optional
const TIMEAGO_FORMATTER: Formatter = (
  value,
  unit,
  suffix,
  epochSeconds,
  nextFormatter
) =>
  unit === 'second'
    ? 'just now'
    : nextFormatter!(value, unit, suffix, epochSeconds);

export const Timestamp = ({
  value,
  format,
  live = true,
  dropTimeWhenDefault = false,
}: TimestampProps) => {
  const then = valueToMoment(value);
  if (format === 'relative') {
    const content = then.format('dddd, MMMM Do YYYY [at] h:mm:ss a');
    const timeago = (
      <TimeAgo
        title="" // Suppress the default tooltip
        minPeriod={10}
        formatter={TIMEAGO_FORMATTER}
        date={then.format('YYYY-MM-DDTHH:mm:ssZ')}
        live={live}
      />
    );
    return <Tooltip content={content} trigger={timeago} />;
  }

  // Check if the time is midnight (00:00)
  const isMidnight =
    dropTimeWhenDefault && then.hour() === 0 && then.minute() === 0;

  // Use different formats based on whether it's midnight
  const shortFormat = isMidnight ? 'MMM Do YYYY' : 'MMM Do YYYY [at] h:mma';
  const longFormat = isMidnight
    ? 'dddd, MMMM Do YYYY'
    : 'dddd, MMMM Do YYYY [at] h:mm:ss a';

  const short = then.format(shortFormat);
  const long = then.format(longFormat);

  const text = <span>{short}</span>;
  return <Tooltip content={long} trigger={text} />;
};

export const TimestampMicro = ({
  value,
  label,
}: TimestampProps & {label?: string}) => {
  /* TimestampMicro displays a micro timestamp, e.g. "1d" or "1w".
     in a nice gray tooltip
   */
  const then = valueToMoment(value);
  const {long, micro} = formatTimestampInternal(then);
  const text = (
    <div className="flex items-center">
      <Icon name="date" className="mr-3" />
      <span className="font-semibold">
        {label} {micro}
      </span>
    </div>
  );
  return <Tooltip content={long} trigger={text} />;
};

export const TimestampRange = ({value, field}: {value: any; field: string}) => {
  const {before, after} = value as {
    before: string;
    after: string;
  };
  return (
    <span className="flex items-center gap-2 font-semibold">
      {field}
      <span className="flex items-center">
        <Timestamp value={after} dropTimeWhenDefault />
      </span>
      <span className="mx-2">→</span>
      <span className="flex items-center">
        <Timestamp value={before} dropTimeWhenDefault />
      </span>
    </span>
  );
};
