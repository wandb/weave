import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useEffect, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {toast} from '../../../../../../common/components/elements/Toast';
import {capitalizeFirst} from '../../../../../../core/util/string';
import {Tailwind} from '../../../../../Tailwind';
import {
  WeaveHeaderExtrasContext,
  WeaveHeaderExtrasProvider,
} from '../../context';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
} from '../common/SimplePageLayout';
import {SavedViewPrefix} from '../SavedViews/SavedViewPrefix';
import {SavedViewSuffix} from '../SavedViews/SavedViewSuffix';
import {
  getDefaultView,
  getDefaultViewId,
  getNewViewId,
  SAVED_PARAM_KEYS,
  SavedViewsInfo,
  useCurrentViewDefinition,
} from '../SavedViews/savedViewUtil';
import {ViewName} from '../SavedViews/ViewName';
import {ViewNameEditing} from '../SavedViews/ViewNameEditing';
import {useControllableState} from '../util';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {CallsTable} from './CallsTable';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useCurrentFilterIsEvaluationsFilter} from './evaluationsFilter';

const HeaderExtras = () => {
  const {renderExtras} = React.useContext(WeaveHeaderExtrasContext);
  return <>{renderExtras()}</>;
};

export const CallsPage: FC<{
  currentViewerId: string | null;
  isReadonly: boolean;

  entity: string;
  project: string;

  view: string;
  onRecordLastView: (view: string) => void;

  initialFilter?: WFHighLevelCallFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelCallFilter) => void;

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
  const {entity, project, view} = props;
  console.log({view});
  const [filter, setFilter] = useControllableState(
    props.initialFilter ?? {},
    props.onFilterUpdate
  );

  const isEvaluationTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    entity,
    project
  );
  // table is the internal id stored in the object.
  // TODO: Should we just use the capitalized version?
  const table = isEvaluationTable ? 'evaluations' : 'traces';
  const defaultLabel = capitalizeFirst(table);

  const [views, setViews] = useState<TraceObjSchema[] | null>(null);

  const getTsClient = useGetTraceServerClientContext();

  const tsClient = getTsClient();
  const projectId = projectIdFromParts({entity, project});

  // const {loading, result: savedViews} = useBaseObjectInstances('SavedView', {
  //   project_id: projectId,
  //   filter: {
  //     // TODO: Could we filter at query time based on the page
  //     // so we don't have to do it on the result?
  //     base_object_classes: ['SavedView'],
  //     latest_only: true,
  //   },
  // });
  // console.log('after usebase object instances');
  // console.log({loading, savedViews});

  // TODO: Memo
  // const views = savedViews?.filter(v => v.val.table === table) ?? [];
  // console.log({loading, savedViews, views});

  const fetchViews = useCallback(() => {
    tsClient
      .objsQuery({
        project_id: projectId,
        filter: {
          // TODO: Could we filter at query time based on the page
          // so we don't have to do it on the result?
          base_object_classes: ['SavedView'],
          latest_only: true,
        },
      })
      .then(res => {
        const viewsForPage = res.objs.filter(v => v.val.table === table);
        // Add a "default" view if we don't have one
        if (!viewsForPage.some(v => v.object_id === getDefaultViewId(table))) {
          viewsForPage.push(getDefaultView(projectId, table));
        }
        setViews(viewsForPage);
      })
      .catch(err => {
        console.error(err);
      });
  }, [projectId, tsClient, table]);

  // Load view data on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(fetchViews, [table]);

  const baseView =
    views?.find(v => v.object_id === view) ??
    getDefaultView(projectId, defaultLabel);
  const currentViewDefinition = useCurrentViewDefinition();

  const history = useHistory();
  const onLoadView = (viewToLoad: TraceObjSchema) => {
    // We want to preserve any params that are not part of view definition,
    // e.g. peek drawer state.
    const newQuery = new URLSearchParams(history.location.search);

    // Clear out any params related to saved views
    for (const key of SAVED_PARAM_KEYS) {
      newQuery.delete(key);
    }

    // Update with params from the view definition
    for (const [key, value] of Object.entries(viewToLoad.val.definition)) {
      newQuery.set(key, JSON.stringify(value));
    }

    newQuery.set('view', viewToLoad.object_id);
    history.push({search: newQuery.toString()});
    props.onRecordLastView(viewToLoad.object_id);
  };
  const onResetView = () => {
    let viewToLoad = views?.find(v => v.object_id === view);
    if (!viewToLoad) {
      const defaultViewId = getDefaultViewId(table);
      viewToLoad = views?.find(v => v.object_id === defaultViewId);
    }
    if (viewToLoad) {
      onLoadView(viewToLoad);
    } else {
      console.log('could not find view to reset to');
      console.log({views});
    }
  };

  const viewDef = useCurrentViewDefinition();
  const {onRecordLastView} = props;

  console.log({view});
  const onUpsertView = useCallback(
    (objectId: string, label: string | null, successMessage: string) => {
      if (objectId === getDefaultViewId(table)) {
        objectId = getNewViewId(table);
      }
      if (label === null) {
        // If caller doesn't provide a new label, use the existing one.
        label = baseView.val.label;
      }
      const className = 'SavedView';
      tsClient
        .objCreate({
          obj: {
            project_id: projectIdFromParts({entity, project}),
            object_id: objectId,
            val: {
              _type: className,
              table,
              // name,
              _class_name: className,
              _bases: ['SavedView', 'Object', 'BaseModel'],
              label,
              definition: viewDef,
            },
          },
        })
        .then(res => {
          const newQuery = new URLSearchParams(history.location.search);
          newQuery.set('view', objectId);
          history.push({search: newQuery.toString()});
          fetchViews();
          toast(successMessage);
          onRecordLastView(objectId);
        });
    },
    [
      entity,
      fetchViews,
      history,
      project,
      table,
      onRecordLastView,
      baseView.val.label,
      tsClient,
      viewDef,
    ]
  );

  const onSaveNewView = () => {
    // setIsEditingName(true);
    // querySetString(history, 'view', 'placeholder');
    // // TODO: Set focus to name input
    const objectId = getNewViewId(table);
    onUpsertView(objectId, 'Untitled view', 'Successfully created new view.');
  };

  const onSaveView = () => {
    onUpsertView(view, null, 'Successfully saved view.');
  };

  const onRenameView = (newName: string) => {
    onUpsertView(view, newName, 'Successfully renamed view.');
  };

  const onDeleteView = () => {
    tsClient
      .objDelete({
        project_id: projectIdFromParts({entity, project}),
        object_id: view,
      })
      .then(res => {
        fetchViews();
        // TODO: Use label of view
        toast(`Successfully deleted view.`);
        // onRecordLastView(objectId);
        const newQuery = new URLSearchParams();
        // newQuery.set('view', 'default');
        history.push({search: newQuery.toString()});
      });
  };

  const savedViewsInfo: SavedViewsInfo = {
    currentViewerId: props.currentViewerId,
    isLoading: views === null,
    currentViewId: view,
    currentViewDefinition,
    isDefault: view === getDefaultViewId(table),
    isModified: !_.isEqual(currentViewDefinition, baseView?.val.definition),
    views: views ?? [],
    baseView,
    onLoadView,
    onSaveView,
    onSaveNewView,
    onResetView,
    onDeleteView,
  };
  // console.log({
  //   currentViewDefinition,
  //   bv: baseView?.val.definition,
  //   savedViewsInfo,
  // });

  const onNameChanged = (newName: string) => {
    if (views === null) {
      return;
    }
    // Update the local state with the new name
    const updatedViews = views.map(v => {
      if (v.object_id === view) {
        return {...v, val: {...v.val, label: newName}};
      }
      return v;
    });
    setViews(updatedViews);
    // Update the server with the new name
    onRenameView(newName);
  };
  const activeName =
    view === 'placeholder'
      ? 'Untitled view'
      : baseView.val.label ?? 'Untitled view';
  const [isEditingName, setIsEditingName] = useState(false);
  const title = (
    <Tailwind>
      {isEditingName ? (
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
                <CallsTable
                  {...props}
                  // CPR (Tim): Applying "hide controls" when the filter is frozen is pretty crude.
                  // We will likely need finer-grained control over the filter enablement states
                  // rather than just a boolean flag. Note: "frozen === hideControls" at the moment.
                  // In fact, it probably should be used to determine if the filter should be applied
                  // to the frozenFilter prop. Furthermore, "frozen" is only used when showing the
                  // evaluations table. So, in this case, I think we should really just remove the
                  // `frozen` property completely and have a top-level evaluations tab that hides controls.
                  hideControls={filter.frozen && !isEvaluationTable}
                  hideOpSelector={isEvaluationTable}
                  initialFilter={filter}
                  onFilterUpdate={setFilter}
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
