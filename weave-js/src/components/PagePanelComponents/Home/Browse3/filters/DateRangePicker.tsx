/**
 * Component for selecting a date range for filtering
 */

import moment from 'moment';
import React from 'react';

import {StyledDateRangePicker} from '../StyledDateRangePicker';

type DateRangePickerProps = {
  value: string;
  onSetValue: (value: string) => void;
};

export const DateRangePicker = ({value, onSetValue}: DateRangePickerProps) => {
  // The value is stored as a JSON string containing start and end dates
  const parsedValue = React.useMemo(() => {
    try {
      if (!value) {
        return {start: null, end: null};
      }
      return JSON.parse(value);
    } catch (e) {
      return {start: null, end: null};
    }
  }, [value]);

  const startValue = parsedValue.start ? moment(parsedValue.start) : null;
  const endValue = parsedValue.end ? moment(parsedValue.end) : null;

  const handleRangeChange = (
    newValue: [moment.Moment | null, moment.Moment | null]
  ) => {
    const [newStart, newEnd] = newValue;
    const newRangeValue = {
      start: newStart ? newStart.toISOString() : null,
      end: newEnd ? newEnd.toISOString() : null,
    };
    onSetValue(JSON.stringify(newRangeValue));
  };

  return (
    <StyledDateRangePicker
      value={[startValue, endValue]}
      onChange={handleRangeChange}
      localeText={{start: 'start', end: 'end'}}
      calendars={1}
      showDaysOutsideCurrentMonth={false}
      disableHighlightToday={true}
    />
  );
};

export const DateRangeDisplay = ({value}: {value: string}) => {
  try {
    if (!value) {
      return null;
    }
    const {start, end} = JSON.parse(value);

    return (
      <span>
        {start ? moment(start).format('YYYY-MM-DD') : '(any)'} to{' '}
        {end ? moment(end).format('YYYY-MM-DD') : '(any)'}
      </span>
    );
  } catch (e) {
    return null;
  }
};
