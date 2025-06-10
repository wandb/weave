import {
  GridFilterModel,
  GridSortItem,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import {useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {capitalizeFirst} from '../../../../../../core/util/string';
import {
  convertHighLevelFilterToLowLevelFilter,
  convertLowLevelFilterToHighLevelFilter,
} from '../CallsPage/callsTableQuery';
import {useURLSearchParamsDict} from '../util';
import {
  CallsFilter,
  SavedView,
  SavedViewDefinition,
  SortBy,
} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {Query} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {
  TraceObjSchemaForBaseObjectClass,
  useBaseObjectInstances,
  useCreateBuiltinObjectInstance,
} from '../wfReactInterface/objectClassQuery';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {CallFilter} from '../wfReactInterface/wfDataModelHooksInterface';

// This represents a "simple" filter like we let you use in Python.
export type Filter = {
  field: string;
  operator: string;
  value: any;
};

export type Filters = Filter[];

// Note: This is the value of an item in the items array of the UI filters value.
// It is not the same as the CallFilter type used for the "filter" param.
export type UIFilter = Filter & {id: number};

// This is the format we store in the URL params.
// It is similar to, but not exactly the same as, the GridFilterModel in Material UI.
export type UIFilters = {
  items: UIFilter[];
  logicOperator: 'and';
};

const filtersToUiFilters = (filters: Filters): UIFilters => {
  const items: UIFilter[] = filters.map((filter, index) => ({
    ...filter,
    id: index,
  }));
  return {
    items,
    logicOperator: 'and',
  };
};

const removeNullValues = <T extends object>(obj: T): Partial<T> => {
  return _.omitBy(obj, value => value === null) as Partial<T>;
};

// Objects were getting returned with extra fields, which causes
// equality checks that detect whether the view has been modified to fail.
// This removes those extra fields.
// This method and use of it should be removable once trace server
// deployments are updated with a fix.
const removeObjectAnnotations = (obj: any): any => {
  if (_.isPlainObject(obj)) {
    const newObj: Record<string, any> = {};
    for (const key in obj) {
      if (['_type', '_class_name', '_bases'].includes(key)) {
        continue;
      }
      newObj[key] = removeObjectAnnotations(obj[key]);
    }
    return newObj;
  }
  if (_.isArray(obj)) {
    return obj.map(removeObjectAnnotations);
  }
  return obj;
};

// Confusing terminology alert: CallsFilter is the Zod type with snake case names,
// CallFilter is the low-level (non-URL) UI type with camel case names.
const callFilterToCallsFilter = (
  filter?: CallFilter | null
): CallsFilter | null => {
  if (filter == null) {
    return null;
  }
  const f: CallsFilter = {};
  if (filter.opVersionRefs != null) {
    f.op_names = filter.opVersionRefs;
  }
  if (filter.inputObjectVersionRefs != null) {
    f.input_refs = filter.inputObjectVersionRefs;
  }
  if (filter.outputObjectVersionRefs != null) {
    f.output_refs = filter.outputObjectVersionRefs;
  }
  if (filter.parentIds != null) {
    f.parent_ids = filter.parentIds;
  }
  if (filter.traceId != null) {
    f.trace_ids = [filter.traceId];
  }
  if (filter.callIds != null) {
    f.call_ids = filter.callIds;
  }
  if (filter.traceRootsOnly != null) {
    f.trace_roots_only = filter.traceRootsOnly;
  }
  if (filter.userIds != null) {
    f.wb_user_ids = filter.userIds;
  }
  if (filter.runIds != null) {
    f.wb_run_ids = filter.runIds;
  }
  return f;
};

export const callsFilterToCallFilter = (
  filter?: CallsFilter | null
): CallFilter => {
  if (filter == null) {
    return {};
  }
  const f: CallFilter = {};
  if (filter.op_names != null) {
    f.opVersionRefs = filter.op_names;
  }
  if (filter.input_refs != null) {
    f.inputObjectVersionRefs = filter.input_refs;
  }
  if (filter.output_refs != null) {
    f.outputObjectVersionRefs = filter.output_refs;
  }
  if (filter.parent_ids != null) {
    f.parentIds = filter.parent_ids;
  }
  if (filter.trace_ids != null) {
    f.traceId = filter.trace_ids[0];
  }
  if (filter.call_ids != null) {
    f.callIds = filter.call_ids;
  }
  if (filter.trace_roots_only != null) {
    f.traceRootsOnly = filter.trace_roots_only;
  }
  if (filter.wb_user_ids != null) {
    f.userIds = filter.wb_user_ids;
  }
  if (filter.wb_run_ids != null) {
    f.runIds = filter.wb_run_ids;
  }
  return f;
};

/**
 * Convert a value to seconds.
 *
 * This is used for constructing time based filters.
 *
 * Handles:
 * - null/undefined: returns null
 * - Empty string: returns null
 * - Numbers: returns the number directly
 * - Strings that can be parsed as numbers: returns the parsed number
 * - Date strings: parses as date and returns seconds since epoch
 * - Date objects: returns seconds since epoch
 *
 * @param value The value to convert to seconds
 * @returns The value converted to seconds, or null if conversion failed
 */
export const toSeconds = (value: any): number | null => {
  if (value == null || value === '') {
    return null;
  }

  // If it's already a number, return it directly
  if (typeof value === 'number') {
    return value;
  }

  // This needs to happen before Number() because that can also work on a Date
  if (value instanceof Date) {
    return value.getTime() / 1000;
  }

  // Try to parse as a number
  const num = Number(value);
  if (!isNaN(num)) {
    return num;
  }

  // Try to parse as a date
  try {
    // Handle ISO format with Z
    const dateStr = String(value).replace('Z', '+00:00');
    const date = new Date(dateStr);
    if (!isNaN(date.getTime())) {
      return date.getTime() / 1000;
    }
  } catch (e) {
    // Fall through to return null
  }

  return null;
};

const filterToClause = (item: Filter): Record<string, any> => {
  if (item.operator === '(any): isEmpty') {
    return {
      $eq: [{$getField: item.field}, {$literal: ''}],
    };
  } else if (item.operator === '(any): isNotEmpty') {
    return {
      $not: [{$eq: [{$getField: item.field}, {$literal: ''}]}],
    };
  } else if (item.operator === '(string): contains') {
    return {
      $contains: {
        input: {$getField: item.field},
        substr: {$literal: item.value},
        case_insensitive: false,
      },
    };
  } else if (item.operator === '(string): notContains') {
    return {
      $not: [
        {
          $contains: {
            input: {$getField: item.field},
            substr: {$literal: item.value},
            case_insensitive: false,
          },
        },
      ],
    };
  } else if (item.operator === '(string): equals') {
    return {
      $eq: [{$getField: item.field}, {$literal: item.value}],
    };
  } else if (item.operator === '(string): notEquals') {
    return {
      $not: [{$eq: [{$getField: item.field}, {$literal: item.value}]}],
    };
  } else if (
    item.operator === '(string): in' ||
    item.operator === '(monitored): by'
  ) {
    const values =
      typeof item.value === 'string'
        ? item.value.split(',').map((v: string) => v.trim())
        : item.value;
    const clauses = values.map((v: string) => ({
      $eq: [{$getField: item.field}, {$literal: v}],
    }));
    return {$or: clauses};
  } else if (item.operator === '(number): =') {
    const value = parseFloat(item.value);
    return {
      $eq: [
        {$convert: {input: {$getField: item.field}, to: 'double'}},
        {$literal: value},
      ],
    };
  } else if (item.operator === '(number): !=') {
    const value = parseFloat(item.value);
    return {
      $not: [
        {
          $eq: [
            {$convert: {input: {$getField: item.field}, to: 'double'}},
            {$literal: value},
          ],
        },
      ],
    };
  } else if (item.operator === '(number): >') {
    const value = parseFloat(item.value);
    return {
      $gt: [{$getField: item.field}, {$literal: value}],
    };
  } else if (item.operator === '(number): >=') {
    const value = parseFloat(item.value);
    return {
      $gte: [{$getField: item.field}, {$literal: value}],
    };
  } else if (item.operator === '(number): <') {
    const value = parseFloat(item.value);
    return {
      $not: [
        {
          $gte: [
            {
              $convert: {
                input: {$getField: item.field},
                to: 'double',
              },
            },
            {$literal: value},
          ],
        },
      ],
    };
  } else if (item.operator === '(number): <=') {
    const value = parseFloat(item.value);
    return {
      $not: [
        {
          $gt: [
            {
              $convert: {
                input: {$getField: item.field},
                to: 'double',
              },
            },
            {$literal: value},
          ],
        },
      ],
    };
  } else if (item.operator === '(bool): is') {
    const value = `${item.value}`;
    return {
      $eq: [{$getField: item.field}, {$literal: value}],
    };
  } else if (item.operator === '(date): after') {
    const seconds = toSeconds(item.value);
    if (seconds === null) {
      throw new Error(`Invalid date value: ${item.value}`);
    }
    return {
      $gt: [{$getField: item.field}, {$literal: seconds}],
    };
  } else if (item.operator === '(date): before') {
    const seconds = toSeconds(item.value);
    if (seconds === null) {
      throw new Error(`Invalid date value: ${item.value}`);
    }
    return {
      $not: [
        {
          $gt: [{$getField: item.field}, {$literal: seconds}],
        },
      ],
    };
  }
  throw new Error(`Unsupported operator: ${item.operator}`);
};

export const uiFilterToFilter = (filter: UIFilter): Filter => {
  return {
    field: filter.field,
    operator: filter.operator,
    value: filter.value,
  };
};

export const uiFormatFiltersToQuery = (filters?: UIFilters): Query | null => {
  if (!filters || !filters.items) {
    return null;
  }
  return filtersToQuery(filters.items.map(uiFilterToFilter));
};

export const filtersToQuery = (filters: Filters | null): Query | null => {
  if (filters === null || filters.length === 0) {
    return null;
  }
  const filterClauses = filters.map(filterToClause);
  return {
    $expr: {
      $and: filterClauses,
    },
  };
};

const operandToFilterEq = (operand: any): Filter => {
  let left = operand.$eq[0];
  const right = operand.$eq[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal != null) {
    let value = right.$literal;
    if (typeof value === 'string') {
      let operator = '(string): equals';
      if (value === '') {
        operator = '(any): isEmpty';
        value = null;
      }
      const field = left.$getField;
      return {field, operator, value};
    }
    if (typeof value === 'number') {
      const operator = '(number): =';
      const field = left.$getField;
      return {field, operator, value};
    }
  }
  throw new Error(`Could not parse eq operand ${JSON.stringify(operand)}`);
};

const operandToFilterContains = (operand: any): Filter => {
  const {input, substr} = operand.$contains;
  // TODO: Handle case_insensitive correctly
  if (input.$getField && substr.$literal != null) {
    const value = substr.$literal;
    if (typeof value === 'string') {
      const operator = '(string): contains';
      const field = input.$getField;
      return {field, operator, value};
    }
  }
  throw new Error(
    `Could not parse contains operand ${JSON.stringify(operand)}`
  );
};

const operandToFilterGt = (operand: any): Filter => {
  let left = operand.$gt[0];
  const right = operand.$gt[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal) {
    let operator = '(number): >';
    let value = right.$literal;
    if (typeof value !== 'number') {
      throw new Error(`Could not parse gt operand: ${JSON.stringify(operand)}`);
    }
    const field = left.$getField;
    if (field === 'started_at') {
      operator = '(date): after';
      value = new Date(value * 1000).toISOString();
    }
    return {
      field,
      operator,
      value,
    };
  }
  throw new Error(`Could not parse gt operand: ${JSON.stringify(operand)}`);
};

const operandToFilterGte = (operand: any): Filter => {
  let left = operand.$gte[0];
  const right = operand.$gte[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal) {
    const operator = '(number): >=';
    const value = right.$literal;
    if (typeof value !== 'number') {
      throw new Error(
        `Could not parse gte operand: ${JSON.stringify(operand)}`
      );
    }
    const field = left.$getField;
    return {
      field,
      operator,
      value,
    };
  }
  throw new Error(`Could not parse gte operand: ${JSON.stringify(operand)}`);
};

const operandToFilter = (operand: any): Filter => {
  if (operand.$eq) {
    return operandToFilterEq(operand);
  }
  if (operand.$contains) {
    return operandToFilterContains(operand);
  }
  if (operand.$gt) {
    return operandToFilterGt(operand);
  }
  if (operand.$gte) {
    return operandToFilterGte(operand);
  }
  if (operand.$not) {
    const filter = operandToFilter(operand.$not[0]);
    if (filter.operator === '(number): >=') {
      filter.operator = '(number): <';
    } else if (filter.operator === '(number): >') {
      filter.operator = '(number): <=';
    } else if (filter.operator === '(number): =') {
      filter.operator = '(number): !=';
    } else if (filter.operator === '(string): equals') {
      filter.operator = '(string): notEquals';
    } else if (filter.operator === '(string): notEquals') {
      filter.operator = '(string): equals';
    } else if (filter.operator === '(string): contains') {
      filter.operator = '(string): notContains';
    } else if (filter.operator === '(string): notContains') {
      filter.operator = '(string): contains';
    } else if (filter.operator === '(date): after') {
      filter.operator = '(date): before';
    } else if (filter.operator === '(date): before') {
      filter.operator = '(date): after';
    } else if (filter.operator === '(any): isEmpty') {
      filter.operator = '(any): isNotEmpty';
    } else if (filter.operator === '(any): isNotEmpty') {
      filter.operator = '(any): isEmpty';
    } else {
      throw new Error(
        `Could not parse "not" operand: ${JSON.stringify(
          operand
        )} for ${JSON.stringify(filter)}`
      );
    }
    return filter;
  }
  if (operand.$or && operand.$or.length > 0) {
    const childFilters = operand.$or.map(operandToFilter);
    if (
      childFilters.every((o: Filter) => o.field === childFilters[0].field) &&
      childFilters.every((o: Filter) => o.operator === '(string): equals')
    ) {
      const operator = '(string): in';
      // TODO: Should we be leaving the values as an array?
      const value = childFilters.map((o: Filter) => o.value).join(',');
      return {field: childFilters[0].field, operator, value};
    }
  }
  throw new Error(`Could not parse operand: ${JSON.stringify(operand)}`);
};

export const queryToUiFilters = (query?: Query | null): UIFilters | null => {
  const filters = queryToFilters(query);
  if (filters == null) {
    return null;
  }
  return filtersToUiFilters(filters);
};

export const queryToGridFilterModel = (
  query?: Query | null
): GridFilterModel | null => {
  const filters = queryToUiFilters(query);
  if (filters == null) {
    return null;
  }
  return filters as GridFilterModel;
};

export const queryToFilters = (query?: Query | null): Filters | null => {
  if (query == null) {
    return null;
  }

  const andOperation = query.$expr.$and;
  if (andOperation) {
    if (andOperation.length === 0) {
      return null;
    }
    return andOperation.map(operandToFilter);
  }

  if (
    query.$expr.$eq ||
    query.$expr.$gt ||
    query.$expr.$gte ||
    query.$expr.$not ||
    query.$expr.$contains
  ) {
    return [operandToFilter(query.$expr)];
  }

  throw new Error(`Could not parse query: ${JSON.stringify(query)}`);
};

// Copied from Browse3
export const useParamsDecoded = <T extends object>() => {
  // Handle the case where entity/project (old) have spaces
  const params = useParams<T>();
  return useMemo(() => {
    return Object.fromEntries(
      Object.entries(params).map(([key, value]) => [
        key,
        decodeURIComponent(value),
      ])
    );
  }, [params]);
};

// Convert from the MUI form we store in query parameters to our internal object format.
export const convertGridSortItemToSortBy = (item: GridSortItem): SortBy => {
  const {field, sort} = item;
  return {
    field,
    direction: sort ?? 'asc',
  };
};
export const convertSortByToGridSortItem = (item: SortBy): GridSortItem => {
  const {field, direction} = item;
  return {
    field,
    sort: direction,
  };
};

export const convertSortBysToGridSortModel = (
  sortBys?: SortBy[] | null
): GridSortModel => {
  if (sortBys == null) {
    return [];
  }
  return sortBys.map(convertSortByToGridSortItem);
};

// Not page - always load first page
export const SAVED_PARAM_KEYS = [
  'cols',
  'filter',
  'filters',
  'sort',
  'pin',
  'pageSize',
];
// Get the current view definition from the query params
export const useCurrentViewDefinition = (
  baseView: TraceObjSchema
): SavedViewDefinition => {
  const params = useURLSearchParamsDict();
  const picked = _.pick(params, SAVED_PARAM_KEYS);
  const parsed = _.mapValues(picked, v => {
    try {
      return JSON.parse(v);
    } catch (e) {
      return null;
    }
  });
  const filtered = _.pickBy(parsed, v => v !== null);
  const maybeLowLevelFilter: CallFilter | null = useMemo(() => {
    if (!filtered.filter) {
      return null;
    }
    return convertHighLevelFilterToLowLevelFilter(filtered.filter);
  }, [filtered.filter]);
  const filterValue = callFilterToCallsFilter(maybeLowLevelFilter);
  const filter = filterValue ? {filter: filterValue} : {};
  const queryValue = uiFormatFiltersToQuery(filtered.filters);
  const query = queryValue ? {query: queryValue} : {};
  const sort = filtered.sort
    ? {sort_by: filtered.sort.map(convertGridSortItemToSortBy)}
    : undefined;
  const pageSize = filtered.pageSize ? {page_size: filtered.pageSize} : {};

  const pin = filtered.pin ? {pin: filtered.pin} : {};
  const cols = filtered.cols ? {cols: filtered.cols} : {};

  const merged = {
    ...baseView.val.definition,
    ...filter,
    ...query,
    ...sort,
    ...pin,
    ...pageSize,
    ...cols,
  };
  return merged;
};

export const savedViewDefinitionToParams = (
  savedViewDefinition: SavedViewDefinition
) => {
  const params: Record<string, any> = {};
  if (savedViewDefinition.filter) {
    const lowLevelFilter: CallFilter = callsFilterToCallFilter(
      savedViewDefinition.filter
    );
    params.filter = convertLowLevelFilterToHighLevelFilter(lowLevelFilter);
  }
  if (savedViewDefinition.page_size) {
    params.pageSize = savedViewDefinition.page_size;
  }
  if (savedViewDefinition.query) {
    const filters = queryToFilters(savedViewDefinition.query);
    if (filters) {
      params.filters = filtersToUiFilters(filters);
    }
  }
  // TODO: Cols, pin, sort
  if (savedViewDefinition.sort_by) {
    params.sort = savedViewDefinition.sort_by.map(convertSortByToGridSortItem);
  }

  return params;
};

export const getDefaultViewVal = (viewType: string): SavedView => {
  const label = capitalizeFirst(viewType);
  return {
    view_type: viewType,
    label,
    definition: {
      pin: {
        left: ['CustomCheckbox', 'summary.weave.trace_name'],
        right: [],
      },
      sort_by: [
        {
          field: 'started_at',
          direction: 'desc',
        },
      ],
    },
  };
};

export const getDefaultViewId = (viewType: string): string => {
  return `${viewType}_default`;
};

// Get a new view id based on the current time
// e.g. traces_2025-01-31_02-54-12-003
export const getNewViewId = (viewType: string): string => {
  const now = new Date();
  return `${viewType}_${now
    .toISOString()
    .replace('T', '_')
    .replace(/[:.]/g, '-')
    .slice(0, -1)}`; // Trim trailing 'Z'
};

export const getDefaultView = (
  projectId: string,
  viewType: string
): TraceObjSchemaForBaseObjectClass<'SavedView'> => {
  const objectId = getDefaultViewId(viewType);
  const val = getDefaultViewVal(viewType);
  return {
    base_object_class: 'SavedView',
    project_id: projectId,
    object_id: objectId,
    created_at: '',
    deleted_at: null,
    digest: '',
    version_index: 0,
    is_latest: 1,
    kind: 'object',
    val,
    wb_user_id: '',
  };
};

type SavedViewInstances = {
  loading: boolean;
  views: Array<TraceObjSchemaForBaseObjectClass<'SavedView'>>;
  refetchViews: () => void;
};

export const useSavedViewInstances = (
  projectId: string,
  table: string
): SavedViewInstances => {
  // TODO: Could we filter at query time based on the table
  // so we don't have to do it on the result?
  const savedViewQuery = useBaseObjectInstances('SavedView', {
    project_id: projectId,
    filter: {latest_only: true},
  });

  const views = useMemo(() => {
    const loadedViews = savedViewQuery.result ?? [];
    const viewsForTable = loadedViews.filter(v => v.val.view_type === table);
    viewsForTable.push(getDefaultView(projectId, table));

    // Cleanup view definitions
    viewsForTable.forEach(v => {
      if (v.val.definition.filter) {
        v.val.definition.filter = removeNullValues(v.val.definition.filter);
      }
      if (v.val.definition.query) {
        v.val.definition.query = removeObjectAnnotations(
          v.val.definition.query
        );
      }
    });

    return viewsForTable;
  }, [savedViewQuery.result, projectId, table]);
  const refetchViews = () => {
    savedViewQuery.refetch();
  };

  return {
    loading: savedViewQuery.loading,
    views,
    refetchViews,
  };
};

export const useCreateSavedView = (
  entity: string,
  project: string,
  viewType: string
) => {
  const createSavedViewInstance = useCreateBuiltinObjectInstance('SavedView');

  const createSavedView = (
    objectId: string,
    label: string,
    definition: SavedViewDefinition
  ) => {
    return createSavedViewInstance({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: {
          label,
          view_type: viewType,
          definition,
        },
      },
    });
  };

  return createSavedView;
};

export type SavedViewsInfo = {
  currentViewerId: string | null; // user id of viewer, null if not logged in

  currentViewId: string;
  views: TraceObjSchema[]; // Only the latest version of each view

  baseView: TraceObjSchema;
  currentViewDefinition: SavedViewDefinition;
  isDefault: boolean; // Whether current view is the default view
  isModified: boolean; // Whether current view is not same as base view
  isSaving: boolean; // Whether we are actively saving a view
  onLoadView: (view: TraceObjSchema) => void;
  onSaveView: () => void;
  onSaveNewView: () => void;
  onResetView: () => void;
  onDeleteView: () => void;
};
