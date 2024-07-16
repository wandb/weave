import {GridColDef, GridColumnGroupingModel} from '@mui/x-data-grid-pro';

import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClient';

export type FilterId = number | string | undefined;

// These are columns we won't allow the user to filter on.
// For most of these it would be great if we could enable filtering in the future.
export const UNFILTERABLE_FIELDS = [
  'op_name',
  'feedback',
  'derived.status_code',
  'derived.tokens',
  'derived.cost',
  'derived.latency',
  'wb_user_id',
];

export type ColumnInfo = {
  cols: Array<GridColDef<TraceCallSchema>>;
  colGroupingModel: GridColumnGroupingModel;
};

export const FIELD_TYPE: Record<string, string> = {
  'derived.status_code': 'status',
  wb_user_id: 'user',
  started_at: 'datetime',
};

export const getFieldType = (field: string): string => {
  return FIELD_TYPE[field] ?? 'text';
};

export type SelectOperatorOption = {
  value: string;
  label: string;
  isDisabled?: boolean; // TODO
};

export const getOperatorLabel = (operatorValue: string): string => {
  if ('(any): isEmpty' === operatorValue) {
    return 'is empty';
  }
  if ('(any): isNotEmpty' === operatorValue) {
    return 'is not empty';
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
  return [
    {
      value: '(string): contains',
      label: 'contains',
    },
    {
      value: '(string): equals',
      label: 'equals',
    },
    {
      value: '(number): =',
      label: '=',
    },
    {
      value: '(number): !=',
      label: '!=',
    },
    {
      value: '(number): <',
      label: '<',
    },
    {
      value: '(number): <=',
      label: '<=',
    },
    {
      value: '(number): >',
      label: '>',
    },
    {
      value: '(number): >=',
      label: '>=',
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
