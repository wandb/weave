/**
 * Shared type definitions and utility methods for filtering UI.
 */

import {
  GridColDef,
  GridColumnGroupingModel,
  GridFilterItem,
  GridFilterModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';

import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClientTypes';

export type FilterId = number | string | undefined;

// These are columns we won't allow the user to filter on.
// For most of these it would be great if we could enable filtering in the future.
export const UNFILTERABLE_FIELDS = [
  'op_name',
  'feedback',
  'summary.weave.status',
  'summary.weave.tokens',
  'summary.weave.cost',
  'summary.weave.latency',
  'wb_user_id', // Option+Click works
];

export type ColumnInfo = {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
};

export const FIELD_LABELS: Record<string, string> = {
  id: 'Call ID',
  started_at: 'Called',
  wb_user_id: 'User',
};

export const getFieldLabel = (field: string): string => {
  return FIELD_LABELS[field] ?? field;
};

export const FIELD_TYPE: Record<string, string> = {
  id: 'id',
  'summary.weave.status': 'status',
  wb_user_id: 'user',
  started_at: 'datetime',
};

export const getFieldType = (field: string): string => {
  return FIELD_TYPE[field] ?? 'text';
};

const allOperators = [
  {
    value: '(string): contains',
    label: 'contains',
  },
  {
    value: '(string): equals',
    label: 'equals',
  },
  {
    value: '(string): in',
    label: 'in',
  },
  {
    value: '(number): =',
    label: '=',
  },
  {
    value: '(number): !=',
    label: '≠',
  },
  {
    value: '(number): <',
    label: '<',
  },
  {
    value: '(number): <=',
    label: '≤',
  },
  {
    value: '(number): >',
    label: '>',
  },
  {
    value: '(number): >=',
    label: '≥',
  },
  {
    value: '(bool): is',
    label: 'is',
  },
  {
    value: '(date): after',
    label: 'after',
  },
  {
    value: '(date): before',
    label: 'before',
  },
  {
    value: '(any): isEmpty',
    label: 'is empty',
  },
  {
    value: '(any): isNotEmpty',
    label: 'is not empty',
  },
];
const operatorLabels: Record<string, string> = allOperators.reduce(
  (acc, operator) => {
    acc[operator.value] = operator.label;
    return acc;
  },
  {} as Record<string, string>
);

const VALUELESS_OPERATORS = new Set(['(any): isEmpty', '(any): isNotEmpty']);

export const isValuelessOperator = (operator: string) => {
  return VALUELESS_OPERATORS.has(operator);
};

export const isNumericOperator = (operator: string) => {
  return operator.startsWith('(number):');
};

export type SelectOperatorOption = {
  value: string;
  label: string;
};

export const getOperatorLabel = (operatorValue: string): string => {
  const label = operatorLabels[operatorValue];
  if (label) {
    return label;
  }
  const parts = operatorValue.split(':');
  if (parts.length > 1) {
    return parts[1].trim();
  }
  return operatorValue;
};

export const getOperatorValueType = (operatorValue: string): string => {
  const parts = operatorValue.split(':');
  if (parts.length > 1) {
    return parts[0].substring(1, parts[0].length - 1);
  }

  return 'any';
};

export const getOperatorOptions = (field: string): SelectOperatorOption[] => {
  const fieldType = getFieldType(field);
  if ('id' === fieldType) {
    return [
      {
        value: '(string): equals',
        label: 'equals',
      },
      {
        value: '(string): in',
        label: 'in',
      },
    ];
  }
  if ('datetime' === fieldType) {
    return [
      {
        value: '(date): after',
        label: 'after',
      },
      {
        value: '(date): before',
        label: 'before',
      },
    ];
  }
  if ('status' === fieldType) {
    return [
      {
        value: 'is',
        label: 'is',
      },
      {
        value: 'is not',
        label: 'is not',
      },
    ];
  }
  if ('user' === fieldType) {
    return [
      {
        value: '(string): equals',
        label: 'equals',
      },
    ];
  }
  return allOperators;
};

export const getDefaultOperatorForValue = (value: any) => {
  if (typeof value === 'number') {
    return '(number): =';
  }
  if (typeof value === 'boolean') {
    return '(bool): is';
  }
  return '(string): equals';
};

export const FIELD_DESCRIPTIONS: Record<string, string> = {
  started_at: 'The time the op was invoked',
  'attributes.weave.client_version': 'The version of the Weave library used',
  'attributes.weave.source': 'Which Weave client was used',
  'attributes.weave.os_name': 'Operating system name',
  'attributes.weave.os_version': 'Detailed operating system version',
  'attributes.weave.os_release': 'Brief operating system version',
  'attributes.weave.sys_version': 'Python version used',
};

export const isWeaveRef = (value: any): boolean => {
  return typeof value === 'string' && value.startsWith('weave:///');
};

export const getStringList = (value: any): string[] => {
  if (_.isString(value)) {
    return value.split(',').map(id => id.trim());
  }
  if (_.isArray(value) && value.every(_.isString)) {
    return value;
  }
  throw new Error('Invalid value');
};

type ReplacementTest = (item: GridFilterItem) => boolean;

export const upsertFilter = (
  model: GridFilterModel,
  item: GridFilterItem,
  replacementTest: ReplacementTest
): GridFilterModel => {
  const items: GridFilterItem[] = [];
  let found = false;
  for (const i of model.items) {
    if (replacementTest(i)) {
      items.push(item);
      found = true;
    } else {
      items.push(i);
    }
  }
  if (!found) {
    items.push(item);
  }
  return {
    ...model,
    items,
  };
};
