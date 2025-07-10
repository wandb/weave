import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {useAsyncFn} from 'react-use';

import {toast} from '../../../../../../common/components/elements/Toast';
import {Tailwind} from '../../../../../Tailwind';
import {
  WeaveHeaderExtrasContext,
  WeaveHeaderExtrasProvider,
} from '../../context';
import {useEntityProject} from '../../context';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
} from '../common/SimplePageLayout';
import {SavedViewPrefix} from '../SavedViews/SavedViewPrefix';
import {SavedViewSuffix} from '../SavedViews/SavedViewSuffix';
import {
  convertGridSortItemToSortBy,
  getDefaultViewId,
  getNewViewId,
  savedViewDefinitionToParams,
  SavedViewsInfo,
  uiFormatFiltersToQuery,
  useCreateSavedView,
} from '../SavedViews/savedViewUtil';
import {ViewName} from '../SavedViews/ViewName';
import {ViewNameEditing} from '../SavedViews/ViewNameEditing';
import {SavedViewDefinition} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {ThreadsTable} from './ThreadsTable';

// Current view definition for threads
const useCurrentViewDefinitionForThreads = (
  baseView: TraceObjSchema,
  filterModel: GridFilterModel,
  sortModel: GridSortModel,
  paginationModel: GridPaginationModel,
  columnVisibilityModel: GridColumnVisibilityModel,
  pinModel: GridPinnedColumnFields
): SavedViewDefinition => {
  return useMemo(() => {
    const query = uiFormatFiltersToQuery(filterModel as any);
    const sort_by = sortModel.map(convertGridSortItemToSortBy);

    return {
      ...baseView.val.definition,
      ...(query && {query}),
      ...(sort_by.length > 0 && {sort_by}),
      page_size: paginationModel.pageSize,
      cols: columnVisibilityModel,
      pin: pinModel,
    };
  }, [
    baseView.val.definition,
    filterModel,
    sortModel,
    paginationModel,
    columnVisibilityModel,
    pinModel,
  ]);
};

// For threads, we now track filters, sort, pageSize, cols, pin
const THREADS_PARAM_KEYS = ['filters', 'sort', 'pageSize', 'cols', 'pin'];

const HeaderExtras = () => {
  const {renderExtras} = React.useContext(WeaveHeaderExtrasContext);
  return <>{renderExtras()}</>;
};

export const ThreadsPage: FC<{
  currentViewerId: string | null;
  isReadonly: boolean;

  baseView: TraceObjSchema;
  views: TraceObjSchema[];
  onRecordLastView: (view: string) => void;
  fetchViews: () => void;

  columnVisibilityModel: GridColumnVisibilityModel;
  setColumnVisibilityModel: (newModel: GridColumnVisibilityModel) => void;

  pinModel: GridPinnedColumnFields;
  setPinModel: (newModel: GridPinnedColumnFields) => void;

  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;

  sortModel: GridSortModel;
  setSortModel: (newModel: GridSortModel) => void;

  paginationModel: GridPaginationModel;
  setPaginationModel: (newModel: GridPaginationModel) => void;
}> = props => {
  const {entity, project} = useEntityProject();
  const {baseView, views, fetchViews, onRecordLastView} = props;

  const table = 'threads';
  const view = baseView.object_id;

  const getTsClient = useGetTraceServerClientContext();
  const tsClient = getTsClient();
  const currentViewDefinition = useCurrentViewDefinitionForThreads(
    baseView,
    props.filterModel,
    props.sortModel,
    props.paginationModel,
    props.columnVisibilityModel,
    props.pinModel
  );
  const history = useHistory();

  const createSavedView = useCreateSavedView(entity, project, table);

  const [upsertState, onUpsertView] = useAsyncFn(
    async (
      objectId: string,
      label: string | null,
      successMessage: string,
      reloadAfter: boolean
    ) => {
      try {
        const resolvedLabel = label ?? baseView.val.label;
        await createSavedView(objectId, resolvedLabel, currentViewDefinition);

        const newQuery = new URLSearchParams(history.location.search);
        newQuery.set('view', objectId);
        history.push({search: newQuery.toString()});

        if (reloadAfter) {
          fetchViews();
        }

        toast(successMessage);
        onRecordLastView(objectId);
      } catch (error) {
        toast('Failed to persist Saved View.', {
          type: 'error',
        });
        throw error; // Re-throw to maintain useAsyncFn error state if needed
      }
    },
    [
      baseView.val.label,
      createSavedView,
      currentViewDefinition,
      fetchViews,
      history,
      onRecordLastView,
    ]
  );

  const onLoadView = useCallback(
    (viewToLoad: TraceObjSchema) => {
      // We want to preserve any params that are not part of view definition,
      // e.g. peek drawer state.
      const newQuery = new URLSearchParams(history.location.search);

      // Clear out any params related to saved views
      for (const key of THREADS_PARAM_KEYS) {
        newQuery.delete(key);
      }

      // Update with params from the view definition
      const params = savedViewDefinitionToParams(viewToLoad.val.definition);
      for (const [key, value] of Object.entries(params)) {
        if (THREADS_PARAM_KEYS.includes(key)) {
          newQuery.set(key, JSON.stringify(value));
        }
      }

      newQuery.set('view', viewToLoad.object_id);
      history.push({search: newQuery.toString()});
      props.onRecordLastView(viewToLoad.object_id);
    },
    [history, props]
  );

  const onResetView = useCallback(() => {
    let viewToLoad = views?.find(v => v.object_id === view);
    if (!viewToLoad) {
      const defaultViewId = getDefaultViewId(table);
      viewToLoad = views?.find(v => v.object_id === defaultViewId);
    }
    if (viewToLoad) {
      onLoadView(viewToLoad);
    } else {
      console.error('could not find view to reset to');
    }
  }, [views, view, onLoadView]);

  const onSaveNewView = useCallback(() => {
    const objectId = getNewViewId(table);
    const newName = 'Untitled view';
    // Update the local state with the new name
    baseView.val.label = newName;
    onUpsertView(objectId, newName, 'Successfully created new view.', true);
  }, [table, baseView, onUpsertView]);

  const onSaveView = useCallback(() => {
    if (view === getDefaultViewId(table)) {
      onSaveNewView();
      return;
    }
    onUpsertView(view, null, 'Successfully saved view.', true);
  }, [view, table, onSaveNewView, onUpsertView]);

  const onRenameView = useCallback(
    (newName: string) => {
      onUpsertView(view, newName, 'Successfully renamed view.', false);
    },
    [view, onUpsertView]
  );

  const [, onDeleteView] = useAsyncFn(async () => {
    try {
      await tsClient.objDelete({
        project_id: projectIdFromParts({entity, project}),
        object_id: view,
      });

      // Don't need to fetch views again as we will reload the page.
      // Using history replace instead of push because can't navigate back to deleted view.
      toast('Successfully deleted view.');
      onRecordLastView(getDefaultViewId(table));
      const newQuery = new URLSearchParams();
      history.replace({search: newQuery.toString()});
    } catch (error) {
      toast('Failed to delete view.', {
        type: 'error',
      });
      throw error; // Re-throw to maintain useAsyncFn error state if needed
    }
  }, [tsClient, entity, project, view, onRecordLastView, table, history]);

  const savedViewsInfo: SavedViewsInfo = useMemo(
    () => ({
      currentViewerId: props.currentViewerId,
      currentViewId: view,
      currentViewDefinition,
      isDefault: view === getDefaultViewId(table),
      isModified: !_.isEqual(currentViewDefinition, baseView.val.definition),
      isSaving: upsertState.loading,
      views,
      baseView,
      onLoadView,
      onSaveView,
      onSaveNewView,
      onResetView,
      onDeleteView,
    }),
    [
      props.currentViewerId,
      view,
      currentViewDefinition,
      table,
      baseView,
      upsertState.loading,
      views,
      onLoadView,
      onSaveView,
      onSaveNewView,
      onResetView,
      onDeleteView,
    ]
  );

  const onNameChanged = useCallback(
    (newName: string) => {
      // Update the local state with the new name
      baseView.val.label = newName;
      // Update the server with the new name
      onRenameView(newName);
    },
    [baseView, onRenameView]
  );

  const activeName = baseView.val.label ?? 'Threads view';
  const [isEditingName, setIsEditingName] = useState(false);
  const canEditName = !props.isReadonly && !savedViewsInfo.isDefault;
  const title = (
    <Tailwind>
      {!canEditName ? (
        <ViewName value={activeName} />
      ) : isEditingName ? (
        <ViewNameEditing
          value={activeName}
          onChanged={onNameChanged}
          onExit={() => setIsEditingName(false)}
        />
      ) : (
        <ViewName
          value={activeName}
          onEditNameStart={() => setIsEditingName(true)}
          tooltip="Click to rename view"
        />
      )}
    </Tailwind>
  );

  return (
    <WeaveHeaderExtrasProvider>
      <SimplePageLayoutContext.Provider
        value={{
          headerPrefix: (
            <Tailwind>
              <SavedViewPrefix savedViewsInfo={savedViewsInfo} />
            </Tailwind>
          ),
          headerSuffix:
            views !== null ? (
              <Tailwind>
                <SavedViewSuffix
                  savedViewsInfo={savedViewsInfo}
                  isReadonly={props.isReadonly}
                />
              </Tailwind>
            ) : undefined,
        }}>
        <SimplePageLayout
          title={title}
          hideTabsIfSingle
          tabs={[
            {
              label: 'All',
              content: (
                <ThreadsTable
                  columnVisibilityModel={props.columnVisibilityModel}
                  setColumnVisibilityModel={props.setColumnVisibilityModel}
                  pinModel={props.pinModel}
                  setPinModel={props.setPinModel}
                  filterModel={props.filterModel}
                  setFilterModel={props.setFilterModel}
                  sortModel={props.sortModel}
                  setSortModel={props.setSortModel}
                  paginationModel={props.paginationModel}
                  setPaginationModel={props.setPaginationModel}
                />
              ),
            },
          ]}
          headerExtra={<HeaderExtras />}
        />
      </SimplePageLayoutContext.Provider>
    </WeaveHeaderExtrasProvider>
  );
};
