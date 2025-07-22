import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridLogicOperator,
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
import {useEntityProject} from '../../context';
import {makeDateFilter} from '../../filters/common';
import {getValidFilterModel} from '../../grid/filters';
import {getValidPaginationModel} from '../../grid/pagination';
import {getValidSortModel} from '../../grid/sort';
import {
  convertSortBysToGridSortModel,
  queryToGridFilterModel,
} from '../SavedViews/savedViewUtil';
import {useURLSearchParamsDict} from '../util';
import {SavedViewDefinition} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {ThreadsPage} from './ThreadsPage';

// Thread-specific defaults
const DEFAULT_SORT_THREADS: GridSortModel = [
  {field: 'last_updated', sort: 'desc'},
];

// Default filter: Past 1w
const DEFAULT_FILTER_THREADS: GridFilterModel = {
  items: [makeDateFilter(7)],
  logicOperator: GridLogicOperator.And,
};

// Default column visibility - show all columns initially
const DEFAULT_COLUMN_VISIBILITY_THREADS: GridColumnVisibilityModel = {};

// Default pin model - no columns pinned initially
const DEFAULT_PIN_MODEL_THREADS: GridPinnedColumnFields = {
  left: [],
  right: [],
};

type ThreadsPageLoadedProps = {
  baseView: TraceObjSchema;
  fetchViews: () => void;
  views: TraceObjSchema[];
  userInfo: MaybeUserInfo;
  projectInfo: ProjectInfo;
};

export const ThreadsPageSavedViewControl = ({
  baseView,
  views,
  fetchViews,
  userInfo,
  projectInfo,
}: ThreadsPageLoadedProps) => {
  const {entity} = useEntityProject();
  const location = useLocation();
  const currentViewerId = userInfo ? userInfo.id : null;
  const isReadonly = !currentViewerId || !userInfo?.teams.includes(entity);
  const defaultFilterAdopted = useRef(false);

  const onRecordLastView = useCallback(
    (loadedView: string) => {
      const localStorageKey = `SavedView.lastViewed.${projectInfo.internalIdEncoded}.threads`;
      safeLocalStorage.setItem(localStorageKey, loadedView);
    },
    [projectInfo.internalIdEncoded]
  );

  const viewDef = baseView.val.definition as SavedViewDefinition;
  const query = useURLSearchParamsDict();
  const history = useHistory();

  const filterModel = useDeepMemo(
    useMemo(() => {
      if (query.filters) {
        const parsedFilter = getValidFilterModel(
          query.filters,
          DEFAULT_FILTER_THREADS
        );
        // If the parsed filter is empty (no items), use the default filter
        if (
          parsedFilter &&
          parsedFilter.items.length === 0 &&
          !defaultFilterAdopted.current
        ) {
          defaultFilterAdopted.current = true;
          return DEFAULT_FILTER_THREADS;
        }
        return parsedFilter;
      }
      const filterModel = queryToGridFilterModel(viewDef.query);
      if (
        filterModel &&
        filterModel.items.length === 0 &&
        !defaultFilterAdopted.current
      ) {
        defaultFilterAdopted.current = true;
        return DEFAULT_FILTER_THREADS;
      }
      if (!defaultFilterAdopted.current) {
        defaultFilterAdopted.current = true;
        return DEFAULT_FILTER_THREADS;
      }
      return {items: []};
    }, [query.filters, viewDef])
  );

  const setFilterModel = useCallback(
    (newModel: GridFilterModel) => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('filters', JSON.stringify(newModel));
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  const columnVisibilityModel: GridColumnVisibilityModel = useDeepMemo(
    useMemo(() => {
      if (query.cols) {
        try {
          return JSON.parse(query.cols) as GridColumnVisibilityModel;
        } catch {
          return DEFAULT_COLUMN_VISIBILITY_THREADS;
        }
      }
      return (
        (viewDef.cols as GridColumnVisibilityModel) ??
        DEFAULT_COLUMN_VISIBILITY_THREADS
      );
    }, [query.cols, viewDef])
  );
  const setColumnVisibilityModel = useCallback(
    (newModel: GridColumnVisibilityModel) => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('cols', JSON.stringify(newModel));
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  const pinModel: GridPinnedColumnFields = useDeepMemo(
    useMemo(() => {
      if (query.pin) {
        try {
          return JSON.parse(query.pin) as GridPinnedColumnFields;
        } catch {
          return DEFAULT_PIN_MODEL_THREADS;
        }
      }
      return (
        (viewDef.pin as GridPinnedColumnFields) ?? DEFAULT_PIN_MODEL_THREADS
      );
    }, [query.pin, viewDef])
  );
  const setPinModel = useCallback(
    (newModel: GridPinnedColumnFields) => {
      const newQuery = new URLSearchParams(location.search);
      newQuery.set('pin', JSON.stringify(newModel));
      history.push({search: newQuery.toString()});
    },
    [history, location.search]
  );

  const sortModel: GridSortModel = useDeepMemo(
    useMemo(() => {
      if (query.sort) {
        const parsedSort = getValidSortModel(query.sort, DEFAULT_SORT_THREADS);
        // If the parsed sort is empty (no items), use the default sort
        if (parsedSort && parsedSort.length === 0) {
          return DEFAULT_SORT_THREADS;
        }
        return parsedSort;
      }
      return (
        convertSortBysToGridSortModel(viewDef.sort_by) ?? DEFAULT_SORT_THREADS
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
    <ThreadsPage
      currentViewerId={currentViewerId}
      isReadonly={isReadonly}
      baseView={baseView}
      views={views}
      fetchViews={fetchViews}
      onRecordLastView={onRecordLastView}
      filterModel={filterModel}
      setFilterModel={setFilterModel}
      columnVisibilityModel={columnVisibilityModel}
      setColumnVisibilityModel={setColumnVisibilityModel}
      pinModel={pinModel}
      setPinModel={setPinModel}
      sortModel={sortModel}
      setSortModel={setSortModel}
      paginationModel={paginationModel}
      setPaginationModel={setPaginationModel}
    />
  );
};
