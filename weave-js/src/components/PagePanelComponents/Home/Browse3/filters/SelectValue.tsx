import {DateTimePicker} from '@mui/x-date-pickers';
import moment from 'moment';
import React from 'react';

import {SelectValueStatus} from './SelectValueStatus';
import {SelectValueUser} from './SelectValueUser';
import {TextValue} from './TextValue';
import {getFieldType} from './types';

type SelectValueProps = {
  field: string;
  operator: string;
  value: string;
  onSetValue: (value: string) => void;
};

export const SelectValue = ({
  field,
  operator,
  value,
  onSetValue,
}: SelectValueProps) => {
  const fieldType = getFieldType(field);

  // console.log({fieldType, value});
  if (fieldType === 'status') {
    return <SelectValueStatus operator={operator} onSetValue={onSetValue} />;
  }
  if (fieldType === 'user') {
    return <SelectValueUser operator={operator} />;
  }
  if (fieldType === 'datetime') {
    const dateTimeValue = value ? moment(value) : null;
    return (
      <DateTimePicker
        slotProps={{textField: {size: 'medium'}}}
        value={dateTimeValue}
        onChange={(newValue: moment.Moment | null) =>
          onSetValue(newValue ? newValue.utc().format() : '')
        }
      />
    );
  }
  return <TextValue value={value} onSetValue={onSetValue} />;
};
