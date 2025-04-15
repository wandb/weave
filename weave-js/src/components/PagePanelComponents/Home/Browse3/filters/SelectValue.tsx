/**
 * Select the value for a filter. Depends on the operator.
 */

import React from 'react';

import {parseRef} from '../../../../../react';
import {UserLink} from '../../../../UserLink';
import {SmallRef} from '../smallRef/SmallRef';
import {
  FilterId,
  getFieldType,
  getStringList,
  isNumericOperator,
  isValuelessOperator,
  isWeaveRef,
} from './common';
import {IdList} from './IdList';
import {SelectDatetimeDropdown} from './SelectDatetimeDropdown';
import {TextValue} from './TextValue';
import {ValueInputBoolean} from './ValueInputBoolean';
import {ValueInputStatus} from './ValueInputStatus';

type SelectValueProps = {
  entity: string;
  project: string;
  field: string;
  operator: string;
  value: any;
  onSetValue: (value: string) => void;
  activeEditId?: FilterId | null;
};

export const SelectValue = ({
  entity,
  project,
  field,
  operator,
  value,
  onSetValue,
  activeEditId,
  itemId,
}: SelectValueProps & {itemId?: FilterId}) => {
  if (isValuelessOperator(operator)) {
    return null;
  }
  if (isWeaveRef(value)) {
    // We don't allow editing ref values in the filter popup
    // but we show them.
    return <SmallRef objRef={parseRef(value)} />;
  }

  const fieldType = getFieldType(field);
  const isActive = activeEditId === itemId;

  if (fieldType === 'id' && operator.endsWith('in')) {
    return <IdList ids={getStringList(value)} type="Call" />;
  }
  if (fieldType === 'status') {
    return <ValueInputStatus value={value} onSetValue={onSetValue} />;
  }
  if (fieldType === 'user') {
    return <UserLink userId={value} includeName={true} hasPopover={false} />;
  }
  if (fieldType === 'datetime') {
    // For date range, only show active state for the last filter
    const isDateRange = operator === '(date): range';
    const shouldBeActive = isDateRange
      ? isActive && field.endsWith('after')
      : isActive;

    return (
      <div className="min-w-[202px]">
        <SelectDatetimeDropdown
          entity={entity}
          project={project}
          value={value}
          onChange={onSetValue}
          isActive={shouldBeActive}
        />
      </div>
    );
  }

  if (operator.startsWith('(bool): ')) {
    return <ValueInputBoolean value={value} onSetValue={onSetValue} />;
  }

  const type = isNumericOperator(operator) ? 'number' : 'text';
  return (
    <TextValue
      value={value}
      onSetValue={onSetValue}
      type={type}
      isActive={isActive}
    />
  );
};
