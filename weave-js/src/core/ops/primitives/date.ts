import moment from 'moment';

import {list, listObjectType, maybe, nonNullable} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {makeBasicDimDownOp, makeStandardOp} from '../opKinds';

// Not yet ready, needs to handle tags and nulls (see number.ts).
// Also we'll want to figure out what kind of unit/type to return.

const makeDateOp = makeStandardOp;
const makeDimDownDateOp = makeBasicDimDownOp;

export const opDateSub = makeDateOp({
  hidden: true,
  name: 'date-sub',
  argTypes: {lhs: list('date'), rhs: list('date')},
  renderInfo: {
    type: 'binary',
    repr: '-',
  },
  description: `Returns the difference between two ${docType('date', {
    plural: true,
  })} in milliseconds`,
  argDescriptions: {
    lhs: `First ${docType('date')}`,
    rhs: `Second ${docType('date')}`,
  },
  returnValueDescription: `The difference between the two ${docType('date', {
    plural: true,
  })} in milliseconds`,
  returnType: inputTypes => list('number'),
  resolver: inputs => {
    return inputs.lhs.map(
      (d: any, i: number) => d.getTime() - inputs.rhs[i].getTime()
    );
  },
});

const momentDurations: moment.unitOfTime.DurationConstructor[] = [
  'years',
  'months',
  'days',
  'hours',
  'minutes',
  'seconds',
  'milliseconds',
];

export const opTimestampRelativeStringAutoFormat = makeDateOp({
  hidden: true,
  name: 'timestamp-relativeStringAutoFormat',
  argTypes: {lhs: {type: 'timestamp'}, rhs: {type: 'timestamp'}},
  description: `Returns the difference between two millisecond ${docType(
    'timestamp',
    {
      plural: true,
    }
  )} in days in a nice string form`,
  argDescriptions: {
    lhs: `First ${docType('timestamp')}`,
    rhs: `Second ${docType('timestamp')}`,
  },
  returnValueDescription: `The difference between the two ${docType(
    'timestamp',
    {
      plural: true,
    }
  )} in days in a nice string form`,
  returnType: inputTypes => 'string',
  resolver: inputs => {
    if (inputs.lhs == null || inputs.rhs == null) {
      return null;
    }
    const timestampDiff =
      moment(inputs.lhs).valueOf() - moment(inputs.rhs).valueOf();
    for (const unit of momentDurations) {
      const duration = moment.duration(1, unit).asMilliseconds();
      const diff = timestampDiff / duration;
      if (Math.abs(diff) >= 1) {
        const unitString = Math.abs(diff) === 1 ? unit.slice(0, -1) : unit;
        // years and months get rounded to the tenth. Get rid of trailing 0 ie. 7.0 -> 7
        if (
          (unit === 'years' || unit === 'months') &&
          Math.round(diff) !== Math.round(diff * 10) / 10
        ) {
          return diff.toFixed(1) + ' ' + unitString;
        } else {
          return diff.toFixed() + ' ' + unitString;
        }
      }
    }
    return 'less than 1 ms';
  },
});

export const opDatetimeAddMs = makeDateOp({
  hidden: true,
  name: 'datetime-addms',
  argTypes: {lhs: {type: 'timestamp'}, rhs: 'number'},
  description: `Returns the sum between a ${docType(
    'timestamp'
  )} and duration in milliseconds ${docType('number')}`,
  argDescriptions: {
    lhs: `An ISO timestamp`,
    rhs: `Duration ${docType('number')}`,
  },
  returnValueDescription: `The sum between the a ${docType(
    'timestamp'
  )} and duration in milliseconds ${docType('number')}`,
  returnType: inputs => {
    return {type: 'timestamp'};
  },
  resolver: inputs => {
    if (inputs.lhs == null || inputs.rhs == null) {
      return null;
    }
    // Use moment.utc here incase the incoming datetime doesn't have a timezone.
    // Not ideal but example of usecase:
    // opArtifactVersionCreatedAt can be an input which is a date(in utc) with no timezone
    return moment
      .utc(inputs.lhs)
      .add(moment.duration(inputs.rhs, 'milliseconds'));
  },
});

export const opDateToNumber = makeDateOp({
  hidden: true,
  name: `date-toNumber`,
  argTypes: {date: 'date'},
  description: `Returns the number of milliseconds since the epoch`,
  argDescriptions: {date: 'The date'},
  returnValueDescription: `The number of milliseconds since the epoch`,
  returnType: inputTypes => 'number',
  resolver: inputs => {
    const {date} = inputs;
    return moment(date).unix();
  },
});

export const opDatesMax = makeDimDownDateOp({
  hidden: true,
  name: 'dates-max',
  argTypes: {
    dates: {
      type: 'union',
      members: [
        {
          type: 'list',
          objectType: {type: 'union', members: ['none', 'date']},
        },
        {
          type: 'list',
          objectType: {type: 'union', members: ['none', {type: 'timestamp'}]},
        },
      ],
    },
  },
  description: `Returns the earliest ${docType('date')}`,
  argDescriptions: {dates: 'The list of dates'},
  returnValueDescription: `The earliest ${docType('date')}`,
  returnType: inputTypes => {
    const objType = listObjectType(inputTypes.dates);
    if (nonNullable(objType) === 'date') {
      return maybe('date');
    } else {
      return maybe({type: 'timestamp'});
    }
  },
  resolver: inputs => {
    const dates = inputs.dates as number[];
    return dates.reduce((a, b) => (a > b ? a : b));
  },
});

export const opTimestampMax = makeDimDownDateOp({
  hidden: true,
  name: 'timestamp-max',
  argTypes: {
    timestamps: {
      type: 'union',
      members: [
        {
          type: 'list',
          objectType: {type: 'union', members: ['none', {type: 'timestamp'}]},
        },
      ],
    },
  },
  description: `Returns the largest ${docType('timestamp')}`,
  argDescriptions: {timestamps: 'List of timestamps'},
  returnValueDescription: `The largest ${docType('timestamp')}`,
  returnType: inputTypes => {
    return maybe({type: 'timestamp'});
  },
  resolver: inputs => {
    const timestamps = inputs.timestamps as number[];
    return timestamps.reduce((a, b) => (a > b ? a : b));
  },
});

export const opDatesMin = makeDimDownDateOp({
  hidden: true,
  name: 'dates-min',
  argTypes: {
    dates: {
      type: 'union',
      members: [
        {
          type: 'list',
          objectType: {type: 'union', members: ['none', 'date']},
        },
        {
          type: 'list',
          objectType: {type: 'union', members: ['none', {type: 'timestamp'}]},
        },
      ],
    },
  },
  description: `Returns the earliest ${docType('date')}`,
  argDescriptions: {dates: 'The list of dates'},
  returnValueDescription: `The earliest ${docType('date')}`,
  returnType: inputTypes => {
    const objType = listObjectType(inputTypes.dates);
    if (nonNullable(objType) === 'date') {
      return maybe('date');
    } else {
      return maybe({type: 'timestamp'});
    }
  },
  resolver: inputs => {
    const dates = inputs.dates as number[];
    return dates.reduce((a, b) => (a < b ? a : b));
  },
});

export const opDatesEqual = makeDateOp({
  hidden: true,
  name: 'dates-equal',
  argTypes: {lhs: 'date', rhs: 'date'},
  description: `Returns whether two ${docType('date')}s are equal`,
  argDescriptions: {lhs: 'First date', rhs: 'Second date'},
  returnValueDescription: `Whether the two ${docType('date')}s are equal`,
  returnType: inputTypes => 'boolean',
  resolver: inputs => {
    const {lhs, rhs} = inputs;
    return lhs.getTime() === rhs.getTime();
  },
});

// These date round ops are not yet ready for prod.
// We'll want to expose a a single
// date round function, that takes a TimeUnit (type that doesn't yet
// exist) as its argument. But I haven't finished figuring out what
// I want to do with rounding so let's not expose these yet.
// These also need to handle tags and nulls (see number.ts)

// Hacks around expression editor issue that causes crashes when inputting params
const dateRounder = (level: moment.unitOfTime.StartOf) =>
  makeDateOp({
    hidden: true,
    name: `date_round-${level}`,
    argTypes: {date: 'date'},
    description: `Returns the ${docType(
      'date'
    )} rounded to the nearest ${level}`,
    argDescriptions: {date: `The ${docType('date')}`},
    returnValueDescription: `The ${docType(
      'date'
    )} rounded to the nearest ${level}`,
    returnType: inputTypes => 'date',
    resolver: inputs => {
      const {date} = inputs;
      if (typeof date === 'number') {
        return moment.unix(date).startOf(level).toDate();
      } else {
        return moment(date).startOf(level).toDate();
      }
    },
  });

export const opDateRoundYear = dateRounder('year');
export const opDateRoundQuarter = dateRounder('quarter');
export const opDateRoundMonth = dateRounder('month');
export const opDateRoundWeek = dateRounder('week');
export const opDateRoundDay = dateRounder('day');
export const opDateRoundHour = dateRounder('hour');
export const opDateRoundMinute = dateRounder('minute');

export const opDatetimeNow = makeOp({
  hidden: true,
  name: 'datetime-now',
  argTypes: {},
  description: `Returns the current time in milliseconds`,
  returnValueDescription: `datetime.now()`,
  returnType: 'number',
  resolver: () => {
    return moment.now();
  },
});
