import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import React, {useCallback, useMemo, useRef} from 'react';
import {useHistory, useLocation} from 'react-router-dom';

import {ProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {MaybeUserInfo} from '../../../../../../common/hooks/useViewerInfo';
import {safeLocalStorage} from '../../../../../../core/util/localStorage';
import {useDeepMemo} from '../../../../../../hookUtils';
import {getValidFilterModel} from '../../grid/filters';
import {getValidPaginationModel} from '../../grid/pagination';
import {getValidPinModel, removeAlwaysLeft} from '../../grid/pin';
import {getValidSortModel} from '../../grid/sort';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {
  callsFilterToCallFilter,
  convertSortBysToGridSortModel,
  queryToGridFilterModel,
} from '../SavedViews/savedViewUtil';
import {useURLSearchParamsDict} from '../util';
import {SavedViewDefinition} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallsPage} from './CallsPage';
import {
  ALWAYS_PIN_LEFT_CALLS,
  DEFAULT_PIN_CALLS,
  DEFAULT_SORT_CALLS,
  filterHasCalledAfterDateFilter,
} from './CallsTable';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {
  convertLowLevelFilterToHighLevelFilter,
  DEFAULT_FILTER_CALLS,
  useMakeInitialDatetimeFilter,
} from './callsTableQuery';

type CallsPageLoadedProps = {
  entity: string;
  project: string;
  table: string;
  baseView: TraceObjSchema;
  fetchViews: () => void;
  views: TraceObjSchema[];
  userInfo: MaybeUserInfo;
  projectInfo: ProjectInfo;
};

export const CallsPageLoaded = ({
  entity,
  project,
  table,
  baseView,
  views,
  fetchViews,
  userInfo,
  projectInfo,
}: CallsPageLoadedProps) => {
  const location = useLocation();
  const currentViewerId = userInfo ? userInfo.id : null;
  const isReadonly = !currentViewerId || !userInfo?.teams.includes(entity);

  const onRecordLastView = useCallback(
    (loadedView: string) => {
      const localStorageKey = `SavedView.lastViewed.${projectInfo.internalIdEncoded}.${table}`;
      safeLocalStorage.setItem(localStorageKey, loadedView);
    },
    [projectInfo.internalIdEncoded, table]
  );

  const viewDef = baseView.val.definition as SavedViewDefinition;
  const query = useURLSearchParamsDict();
  const isEvaluationsTab = table === 'evaluations';
  const initialFilter: WFHighLevelCallFilter = useMemo(() => {
    if (isEvaluationsTab) {
      return {
        frozen: true,
        opVersionRefs: [
          opVersionKeyToRefUri({
            entity,
            project,
            opId: EVALUATE_OP_NAME_POST_PYDANTIC,
            versionHash: '*',
          }),
        ],
      };
    }
    if (query.filter === undefined) {
      return (
        convertLowLevelFilterToHighLevelFilter(
          callsFilterToCallFilter(viewDef.filter)
        ) ?? {}
      );
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter, entity, project, viewDef.filter, isEvaluationsTab]);
  const history = useHistory();

  const {initialDatetimeFilter} = useMakeInitialDatetimeFilter(
    entity,
    project,
    initialFilter,
    isEvaluationsTab
  );

  const onFilterUpdate = useCallback(
    filter => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('filter', JSON.stringify(filter));
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  const columnVisibilityModel = useDeepMemo(
    useMemo(() => {
      if (query.cols) {
        // TODO: More validation on this query param
        try {
          return JSON.parse(query.cols);
        } catch (e) {
          console.log(e);
          return {};
        }
      }
      return viewDef.cols ?? {};
    }, [query.cols, viewDef])
  );
  const setColumnVisibilityModel = (newModel: GridColumnVisibilityModel) => {
    const newQuery = new URLSearchParams(location.search);
    newQuery.set('cols', JSON.stringify(newModel));
    history.push({search: newQuery.toString()});
  };

  const pinModel = useDeepMemo(
    useMemo(() => {
      if (query.pin) {
        return getValidPinModel(
          query.pin,
          DEFAULT_PIN_CALLS,
          ALWAYS_PIN_LEFT_CALLS
        );
      }
      return viewDef.pin ?? {};
    }, [query.pin, viewDef])
  );
  const setPinModel = useCallback(
    (newModel: GridPinnedColumnFields) => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set(
        'pin',
        JSON.stringify(removeAlwaysLeft(newModel, ALWAYS_PIN_LEFT_CALLS))
      );
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  // Track if the user has explicitly removed the date filter
  const hasRemovedDateFilter = useRef(false);

  // Only show the date filter if not evals and we haven't explicitly removed it
  const defaultFilter =
    isEvaluationsTab || hasRemovedDateFilter.current
      ? DEFAULT_FILTER_CALLS
      : initialDatetimeFilter;

  const filterModel = useDeepMemo(
    useMemo(() => {
      if (query.filters) {
        return getValidFilterModel(query.filters, defaultFilter);
      }
      return queryToGridFilterModel(viewDef.query) ?? defaultFilter;
    }, [query.filters, viewDef, defaultFilter])
  );
  const setFilterModel = useCallback(
    (newModel: GridFilterModel) => {
      // If there was a date filter and now there isn't, mark it as explicitly removed
      // so we don't add it back on subsequent navigations
      const hadDateFilter = filterHasCalledAfterDateFilter(filterModel);
      if (hadDateFilter && !filterHasCalledAfterDateFilter(newModel)) {
        hasRemovedDateFilter.current = true;
      }

      // When there are no items in the newModel, it would be tempting
      // to remove the query parameter entirely, however, that would cause
      // the value from the saved view to get used, which is a problem if you
      // just removed it.
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('filters', JSON.stringify(newModel));
      history.push({search: newQuery.toString()});
    },
    [history, location.search, filterModel]
  );

  const sortModel: GridSortModel = useDeepMemo(
    useMemo(() => {
      if (query.sort) {
        return getValidSortModel(query.sort, DEFAULT_SORT_CALLS);
      }
      return (
        convertSortBysToGridSortModel(viewDef.sort_by) ?? DEFAULT_SORT_CALLS
      );
    }, [query.sort, viewDef])
  );
  const setSortModel = useCallback(
    (newModel: GridSortModel) => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('sort', JSON.stringify(newModel));
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  const paginationModel = useDeepMemo(
    useMemo(
      () =>
        getValidPaginationModel(
          query.page,
          query.pageSize ?? viewDef.page_size
        ),
      [query.page, query.pageSize, viewDef]
    )
  );
  const setPaginationModel = useCallback(
    (newModel: GridPaginationModel) => {
      const newQuery = new URLSearchParams(location.search);
      const {page, pageSize} = newModel;
      // TODO: If we change page size, should we reset page to 0?
      if (page === 0) {
        newQuery.delete('page');
      } else {
        newQuery.set('page', page.toString());
      }
      newQuery.set('pageSize', pageSize.toString());
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  return (
    <CallsPage
      currentViewerId={currentViewerId}
      isReadonly={isReadonly}
      entity={entity}
      project={project}
      baseView={baseView}
      views={views}
      fetchViews={fetchViews}
      onRecordLastView={onRecordLastView}
      initialFilter={initialFilter}
      onFilterUpdate={onFilterUpdate}
      columnVisibilityModel={columnVisibilityModel}
      setColumnVisibilityModel={setColumnVisibilityModel}
      pinModel={pinModel}
      setPinModel={setPinModel}
      filterModel={filterModel}
      setFilterModel={setFilterModel}
      sortModel={sortModel}
      setSortModel={setSortModel}
      paginationModel={paginationModel}
      setPaginationModel={setPaginationModel}
    />
  );
};
