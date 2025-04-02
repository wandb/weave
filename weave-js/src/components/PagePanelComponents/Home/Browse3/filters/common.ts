/**
 * Shared type definitions and utility methods for filtering UI.
 */

import {
  GridColDef,
  GridColumnGroupingModel,
  GridFilterItem,
  GridFilterModel,
} from '@mui/x-data-grid-pro';
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  parseRefMaybe,
} from '@wandb/weave/react';
import _ from 'lodash';

import {parseFeedbackType} from '../feedback/HumanFeedback/tsHumanFeedback';
import {
  parseScorerFeedbackField,
  RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX,
} from '../feedback/HumanFeedback/tsScorerFeedback';
import {
  WANDB_ARTIFACT_REF_PREFIX,
  WEAVE_REF_PREFIX,
} from '../pages/wfReactInterface/constants';
import {TraceCallSchema} from '../pages/wfReactInterface/traceServerClientTypes';

export type FilterId = number | string | undefined;

// These are columns we won't allow the user to filter on.
// For most of these it would be great if we could enable filtering in the future.
export const UNFILTERABLE_FIELDS = [
  'feedback',
  'summary.weave.status',
  'summary.weave.latency_ms',
  'summary.weave.trace_name',
  'tokens',
  'cost',
  'wb_user_id', // Option+Click works
  'wb_run_id', // Option+Click works
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
  if (field.startsWith('feedback.wandb.annotation.')) {
    // Here the field is coming from convertFeedbackFieldToBackendFilter
    // so the field should start with 'feedback.' if feedback
    const parsed = parseFeedbackType(field);
    if (parsed === null) {
      return field;
    }
    return parsed.displayName;
  }
  if (field.startsWith(RUNNABLE_FEEDBACK_IN_SUMMARY_PREFIX)) {
    const parsed = parseScorerFeedbackField(field);
    if (parsed === null) {
      return field;
    }
    return parsed.scorerName + parsed.scorePath;
  }
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

export type OperatorGroup = 'string' | 'number' | 'boolean' | 'date' | 'any';
export type SelectOperatorOption = {
  label: string;
  value: string;
  group: OperatorGroup;
};

const allOperators: SelectOperatorOption[] = [
  {
    value: '(string): contains',
    label: 'contains',
    group: 'string',
  },
  {
    value: '(string): equals',
    label: 'equals',
    group: 'string',
  },
  {
    value: '(string): in',
    label: 'in',
    group: 'string',
  },
  {
    value: '(number): =',
    label: '=',
    group: 'number',
  },
  {
    value: '(number): !=',
    label: '≠',
    group: 'number',
  },
  {
    value: '(number): <',
    label: '<',
    group: 'number',
  },
  {
    value: '(number): <=',
    label: '≤',
    group: 'number',
  },
  {
    value: '(number): >',
    label: '>',
    group: 'number',
  },
  {
    value: '(number): >=',
    label: '≥',
    group: 'number',
  },
  {
    value: '(bool): is',
    label: 'is',
    group: 'boolean',
  },
  {
    value: '(date): after',
    label: 'after',
    group: 'date',
  },
  {
    value: '(date): before',
    label: 'before',
    group: 'date',
  },
  {
    value: '(any): isEmpty',
    label: 'is empty',
    group: 'any',
  },
  {
    value: '(any): isNotEmpty',
    label: 'is not empty',
    group: 'any',
  },
];

// Display labels
const GROUP_LABELS: Record<OperatorGroup, string> = {
  string: 'Text',
  number: 'Number',
  boolean: 'Boolean',
  date: 'Date',
  any: 'Other',
};

export function getGroupedOperatorOptions(
  field: string
): OperatorGroupedOption[] {
  // Get operators / operator groups
  const availableOperators = getOperatorOptions(field);
  const groups = [...new Set(availableOperators.map(op => op.group))];
  // Create grouped options
  return groups.map(group => ({
    label: GROUP_LABELS[group],
    options: availableOperators.filter(op => op.group === group),
  }));
}

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

export const isDateOperator = (operator: string) => {
  return operator.startsWith('(date):');
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
        group: 'string',
      },
      {
        value: '(string): in',
        label: 'in',
        group: 'string',
      },
    ];
  }
  if ('datetime' === fieldType) {
    return [
      {
        value: '(date): after',
        label: 'after',
        group: 'date',
      },
      {
        value: '(date): before',
        label: 'before',
        group: 'date',
      },
    ];
  }
  if ('status' === fieldType) {
    return [
      {
        value: 'is',
        label: 'is',
        group: 'boolean',
      },
      {
        value: 'is not',
        label: 'is not',
        group: 'boolean',
      },
    ];
  }
  if ('user' === fieldType) {
    return [
      {
        value: '(string): equals',
        label: 'equals',
        group: 'string',
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

// Create a unique symbol for RefString
const WeaveRefStringSymbol = Symbol('WeaveRefString');
const ArtifactRefStringSymbol = Symbol('ArtifactRefString');

// Define RefString type using the unique symbol
export type WeaveRefString = string & {[WeaveRefStringSymbol]: never};
export type ArtifactRefString = string & {[ArtifactRefStringSymbol]: never};

export const isRefPrefixedString = (value: any): boolean => {
  if (typeof value !== 'string') {
    return false;
  }
  if (
    value.startsWith(WEAVE_REF_PREFIX) ||
    value.startsWith(WANDB_ARTIFACT_REF_PREFIX)
  ) {
    return true;
  }
  return false;
};

/**
 * `isWeaveRef` is a very conservative check that will ensure the passed
 * in value is a valid ref string - capable of being safely parsed into
 * a Weave ref object. It ensures that the value is a string with the correct
 * prefix, is parsable, and matches the latest "weave trace" style refs. It
 * should be used as the appropriate type guard before parsing a ref.
 */
export const isWeaveRef = (value: any): value is WeaveRefString => {
  if (!isRefPrefixedString(value)) {
    return false;
  }
  const parsed = parseRefMaybe(value);
  return parsed ? isWeaveObjectRef(parsed) : false;
};

export const isArtifactRef = (value: any): value is ArtifactRefString => {
  if (!isRefPrefixedString(value)) {
    return false;
  }
  const parsed = parseRefMaybe(value);
  return parsed ? isWandbArtifactRef(parsed) : false;
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

export type OperatorGroupedOption = {
  label: string;
  options: SelectOperatorOption[];
};
