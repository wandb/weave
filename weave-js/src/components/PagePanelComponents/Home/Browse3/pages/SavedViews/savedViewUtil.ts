import _ from 'lodash';
import {useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {capitalizeFirst} from '../../../../../../core/util/string';
import {useURLSearchParamsDict} from '../util';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';

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

// Not page - always load first page
export const SAVED_PARAM_KEYS = [
  'cols',
  'filter',
  'filters',
  'sort',
  'pin',
  'pageSize',
];

// Value of the object
type ViewDefinition = Record<string, any>;

// Get the current view definition from the query params
export const useCurrentViewDefinition = (
  baseView: TraceObjSchema
): ViewDefinition => {
  const query = useURLSearchParamsDict();
  const picked = _.pick(query, SAVED_PARAM_KEYS);
  const parsed = _.mapValues(picked, v => {
    try {
      return JSON.parse(v);
    } catch (e) {
      return null;
    }
  });
  const filtered = _.pickBy(parsed, v => v !== null);
  return {
    ...baseView.val.definition,
    ...filtered,
  };
};

export const getDefaultViewDefinition = (table: string): ViewDefinition => {
  const label = capitalizeFirst(table);
  return {
    table,
    label,
    definition: {},
  };
};

export const getDefaultViewId = (table: string): string => {
  return `${table}_default`;
};

// Get a new view id based on the current time
// e.g. traces_2025-01-31_02-54-12-003
export const getNewViewId = (table: string): string => {
  const now = new Date();
  return `${table}_${now
    .toISOString()
    .replace('T', '_')
    .replace(/[:.]/g, '-')
    .slice(0, -1)}`; // Trim trailing 'Z'
};

export const getDefaultView = (
  projectId: string,
  table: string
): TraceObjSchema => {
  const objectId = getDefaultViewId(table);
  const val = getDefaultViewDefinition(table);
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

export type SavedViewsInfo = {
  currentViewerId: string | null; // user id of viewer, null if not logged in

  currentViewId: string;
  views: TraceObjSchema[]; // Only the latest version of each view

  baseView: TraceObjSchema;
  currentViewDefinition: ViewDefinition;
  isDefault: boolean; // Whether current view is the default view
  isModified: boolean; // Whether current view is not same as base view

  onLoadView: (view: TraceObjSchema) => void;
  onSaveView: () => void;
  onSaveNewView: () => void;
  onResetView: () => void;
  onDeleteView: () => void;
};
