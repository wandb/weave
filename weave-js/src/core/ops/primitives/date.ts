import moment from 'moment';

import {list, listObjectType, maybe, nonNullable} from '../../model';
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

export const opTimestampDiffStringFormat = makeDateOp({
  hidden: true,
  name: 'date-diffDaysStringFormat',
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
      moment.utc(inputs.lhs).valueOf() - moment.utc(inputs.rhs).valueOf();
    for (const unit of momentDurations) {
      const duration = moment.duration(1, unit).asMilliseconds();
      const diff = timestampDiff / duration;

      if (diff >= 1) {
        if (unit === 'years' || unit === 'months') {
          return diff.toFixed(1) + ' ' + unit;
        } else {
          if (Math.floor(diff) === 1) {
            return '1' + ' ' + unit.slice(0, -1);
          }
          return Math.floor(diff) + ' ' + unit;
        }
      }
    }
    return 'less than 1 millisecond';
  },
});

export const opDatetimeAddDuration = makeDateOp({
  hidden: true,
  name: 'datetime-add',
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
    if (inputs.lhs == null || inputs.rhs == null || inputs.rhs <= 0) {
      return null;
    }
    return moment.utc(inputs.lhs).valueOf() + inputs.rhs;
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
