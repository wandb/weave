/**
 * FilterTagItem shows one filter. It can be removed by clicking the 'x' button.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import {RemoveAction} from '@wandb/weave/components/Tag';
import React from 'react';

import {parseRef} from '../../../../../react';
import {Timestamp, TimestampMicro} from '../../../../Timestamp';
import {UserLink} from '../../../../UserLink';
import {SmallRef} from '../smallRef/SmallRef';
import {
  FilterId,
  getFieldLabel,
  getFieldType,
  getOperatorLabel,
  getOperatorValueType,
  getStringList,
  isDateOperator,
  isValuelessOperator,
  isWeaveRef,
} from './common';
import {FilterTag} from './FilterTag';
import {IdList} from './IdList';

type FilterTagItemProps = {
  item: GridFilterItem;
  onRemoveFilter: (id: FilterId) => void;
};

const quoteValue = (valueType: string, value: string): string => {
  if ('string' === valueType) {
    return `"${value}"`;
  }
  return value;
};

export const FilterTagItem = ({item, onRemoveFilter}: FilterTagItemProps) => {
  const field = getFieldLabel(item.field);
  const operator = getOperatorLabel(item.operator);
  let label: any = `${field} ${operator}`;
  let disableRemove = false;

  let value: React.ReactNode = '';
  const fieldType = getFieldType(item.field);
  if (fieldType === 'id') {
    value = <IdList ids={getStringList(item.value)} type="Call" />;
  } else if (fieldType === 'user') {
    value = <UserLink userId={item.value} hasPopover={false} />;
  } else if (isWeaveRef(item.value)) {
    value = <SmallRef objRef={parseRef(item.value)} />;
  } else if (isValuelessOperator(item.operator)) {
    // For valueless operators, we don't show a value
  } else if (isDateOperator(item.operator)) {
    // Special case for the Called after field, show the micro label
    if (item.operator === '(date): after' && field === 'Called') {
      label = <TimestampMicro value={item.value} label="Past" />;
      disableRemove = true;
    } else {
      value = <Timestamp value={item.value} />;
    }
  } else {
    const valueType = getOperatorValueType(item.operator);
    value = ' ' + quoteValue(valueType, item.value);
  }

  return (
    <FilterTag
      label={
        <>
          {label}
          <div className="ml-4">{value}</div>
        </>
      }
      removeAction={
        disableRemove ? (
          <></>
        ) : (
          <RemoveAction
            onClick={(e: any) => {
              e.stopPropagation();
              onRemoveFilter(item.id);
            }}
          />
        )
      }
    />
  );
};
