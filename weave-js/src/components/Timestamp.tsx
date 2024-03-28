/**
 * Render UTC timestamp from server.
 */
import moment from 'moment';
import React from 'react';
import TimeAgo, {Formatter} from 'react-timeago';

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
  return {
    // TODO: It would be nice if we could display a timezone string here to
    //       make it clear to the user this is local time. However, we don't have
    //       a reliable way to get it. We'd have to add a dependency on moment-timezone
    //       and then ask it to guess.
    //       REF: https://github.com/moment/moment/issues/162
    long: then.format('dddd, MMMM Do YYYY [at] h:mm:ss a'),
    short: then.format(format),
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

export const Timestamp = ({value, format, live = true}: TimestampProps) => {
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
    return (
      <Tooltip position="top center" content={content} trigger={timeago} />
    );
  }

  const {long, short} = formatTimestampInternal(then, format);
  const text = <span>{short}</span>;
  return <Tooltip position="top center" content={long} trigger={text} />;
};
