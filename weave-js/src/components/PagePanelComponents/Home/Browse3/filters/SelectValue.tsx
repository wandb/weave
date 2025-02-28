/**
 * Select the value for a filter. Depends on the operator.
 */

import moment from 'moment';
import React from 'react';

import {parseRef} from '../../../../../react';
import {UserLink} from '../../../../UserLink';
import {SmallRef} from '../smallRef/SmallRef';
import {StyledDateTimePicker} from '../StyledDateTimePicker';
import {
  getFieldType,
  getStringList,
  isNumericOperator,
  isValuelessOperator,
  isWeaveRef,
} from './common';
import {IdList} from './IdList';
import {TextValue} from './TextValue';
import {ValueInputBoolean} from './ValueInputBoolean';

type SelectValueProps = {
  field: string;
  operator: string;
  value: any;
  onSetValue: (value: string) => void;
};

export const SelectValue = ({
  field,
  operator,
  value,
  onSetValue,
}: SelectValueProps) => {
  if (isValuelessOperator(operator)) {
    return null;
  }
  if (isWeaveRef(value)) {
    // We don't allow editing ref values in the filter popup
    // but we show them.
    return <SmallRef objRef={parseRef(value)} />;
  }

  const fieldType = getFieldType(field);

  if (fieldType === 'id' && operator.endsWith('in')) {
    return <IdList ids={getStringList(value)} type="Call" />;
  }
  if (fieldType === 'user') {
    return <UserLink userId={value} includeName={true} hasPopover={false} />;
  }
  if (fieldType === 'datetime' && operator.startsWith('(date): between')) {
    // TODO: Make this a real component, either StyledDateTimeRangePicker (update?)
    // or a custom input.
    return (
      <input
        type="text"
        name="daterange"
        value={`${value.start} - ${value.end}`}
        onChange={e => {
          const [start, end] = e.target.value.split(' - ');
          onSetValue(`${start} - ${end}`);
        }}
      />
    );
  }
  if (fieldType === 'datetime') {
    const dateTimeValue = value ? moment(value) : null;
    return (
      <StyledDateTimePicker
        value={dateTimeValue}
        onChange={(newValue: moment.Moment | null) =>
          onSetValue(newValue ? newValue.toISOString() : '')
        }
      />
    );
  }

  if (operator.startsWith('(bool): ')) {
    return <ValueInputBoolean value={value} onSetValue={onSetValue} />;
  }

  const type = isNumericOperator(operator) ? 'number' : 'text';
  return <TextValue value={value} onSetValue={onSetValue} type={type} />;
};
