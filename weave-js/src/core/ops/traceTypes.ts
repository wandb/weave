import {dict, list, typedDict, union} from '../model';

const traceFilterPropertyTypes = {
  trace_roots_only: union(['none', 'boolean']),
  op_names: union(['none', list('string')]),
  input_refs: union(['none', list('string')]),
  output_refs: union(['none', list('string')]),
  parent_ids: union(['none', list('string')]),
  trace_ids: union(['none', list('string')]),
  call_ids: union(['none', list('string')]),
  wb_user_ids: union(['none', list('string')]),
  wb_run_ids: union(['none', list('string')]),
};

export const traceFilterType = union([
  'none',
  typedDict(traceFilterPropertyTypes, Object.keys(traceFilterPropertyTypes)),
]);
export const traceLimitType = union(['none', 'number']);
export const traceOffsetType = union(['none', 'number']);
export const traceSortByType = union([
  'none',
  list(typedDict({field: 'string', direction: 'string'})),
]);
export const traceQueryType = union(['none', dict('any')]);
