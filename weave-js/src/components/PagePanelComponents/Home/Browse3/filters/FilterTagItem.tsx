/**
 * FilterTagItem shows one filter. It can be removed by clicking the 'x' button.
 */

import {GridFilterItem} from '@mui/x-data-grid-pro';
import {Icon} from '@wandb/weave/components/Icon';
import {RemoveAction} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';

import {parseRef} from '../../../../../react';
import {Timestamp} from '../../../../Timestamp';
import {UserLink} from '../../../../UserLink';
import {ALL_TRACES_OR_CALLS_REF_KEY} from '../pages/CallsPage/callsTableFilter';
import {opNiceName} from '../pages/common/opNiceName';
import {SmallRef} from '../smallRef/SmallRef';
import {
  FilterId,
  getFieldLabel,
  getFieldType,
  getOperatorLabel,
  getOperatorValueType,
  getStringList,
  isValuelessOperator,
  isWeaveRef,
} from './common';
import {FilterTag} from './FilterTag';
import {IdList} from './IdList';

type FilterTagItemProps = {
  item: GridFilterItem;
  onRemoveFilter: (id: FilterId) => void;
  className?: string;
};

const quoteValue = (valueType: string, value: string): string => {
  if ('string' === valueType) {
    return `"${value}"`;
  }
  return value;
};

export const FilterTagItem = ({
  item,
  onRemoveFilter,
  className = '',
}: FilterTagItemProps) => {
  const field = getFieldLabel(item.field);
  const operator = getOperatorLabel(item.operator);
  let label: any = `${field} ${operator}`;
  let value: React.ReactNode = '';

  let disableRemove = false;

  const fieldType = getFieldType(item.field);
  if (fieldType === 'id') {
    value = <IdList ids={getStringList(item.value)} type="Call" />;
  } else if (fieldType === 'user') {
    value = <UserLink userId={item.value} hasPopover={false} />;
  } else if (item.id === 'default-operation') {
    let tooltip: React.ReactNode = null;
    if (item.value === ALL_TRACES_OR_CALLS_REF_KEY) {
      tooltip = (
        <Tooltip
          content="All traces from any op"
          trigger={<span>All ops</span>}
        />
      );
      disableRemove = true;
    } else {
      const opName = opNiceName(parseRef(item.value).artifactName);
      tooltip = (
        <Tooltip content={item.value} trigger={<span>{opName}</span>} />
      );
    }
    label = (
      <div className="flex items-center gap-2">
        <Icon name="job-program-code" />
        {tooltip}
      </div>
    );
  } else if (isWeaveRef(item.value)) {
    value = <SmallRef objRef={parseRef(item.value)} />;
  } else if (!isValuelessOperator(item.operator)) {
    const valueType = getOperatorValueType(item.operator);
    if (valueType === 'date') {
      value = <Timestamp value={item.value} />;
    } else {
      value = ' ' + quoteValue(valueType, item.value);
    }
  }
  return (
    <div
      className={`flex items-center gap-1 rounded bg-moon-100 px-2 py-1 ${className}`}>
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
    </div>
  );
};
