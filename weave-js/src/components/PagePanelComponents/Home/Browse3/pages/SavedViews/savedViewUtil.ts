import _ from 'lodash';
import {useMemo} from 'react';
import {useParams} from 'react-router-dom';

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
  const parsed = _.mapValues(picked, v => JSON.parse(v));
  return parsed;
};

export const getDefaultViewDefinition = (name: string): ViewDefinition => {
  return {
    name,
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

export const getDefaultView = (
  projectId: string,
  name: string
): TraceObjSchema => {
  const val = getDefaultViewDefinition(name);
  return {
    project_id: projectId,
    object_id: 'default',
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
  isModified: boolean; // Whether current view is not same as base view

  onLoadView: (view: TraceObjSchema) => void;
  onSaveView: () => void;
  onSaveNewView: () => void;
  onResetView: () => void;
};
