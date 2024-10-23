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
export const useCurrentViewDefinition = (): ViewDefinition => {
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
  return filtered;
};

export const getDefaultViewDefinition = (label: string): ViewDefinition => {
  return {
    label,
    definition: {
      // TODO: Need less fragile way of setting this up
      // cols: {
      // 'attributes.weave.client_version': false,
      // 'attributes.weave.os_name': false,
      // 'attributes.weave.os_release': false,
      // 'attributes.weave.os_version': false,
      // 'attributes.weave.source': false,
      // 'attributes.weave.sys_version': false,
      // },
    },
  };
};

export const getDefaultViewId = (table: string): string => {
  return `${table}_default`;
};

export const getNewViewId = (table: string): string => {
  const now = new Date();
  return `${table}_${now
    .toISOString()
    .replace('T', '_')
    .replace(/[:.]/g, '-')
    .slice(0, -1)}`;
};

export const getDefaultView = (
  projectId: string,
  table: string
): TraceObjSchema => {
  const objectId = getDefaultViewId(table);
  const label = capitalizeFirst(table);
  const val = getDefaultViewDefinition(label);
  return {
    project_id: projectId,
    object_id: objectId,
    created_at: '',
    digest: '',
    version_index: 0,
    is_latest: 1,
    kind: 'object',
    val,
  };
};

export type SavedViewsInfo = {
  currentViewerId: string | null; // user id of viewer, null if not logged in

  isLoading: boolean;

  currentViewId: string; // objectId Can be special value "default"
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

export const savedViewObjectToQuery = (view: TraceObjSchema): string => {
  const params = new URLSearchParams();
  params.set('view', view.object_id);
  const {definition} = view.val;
  Object.entries(definition).forEach(([key, value]) => {
    const v = JSON.stringify(value);
    params.set(key, v);
  });
  return params.toString();
};
