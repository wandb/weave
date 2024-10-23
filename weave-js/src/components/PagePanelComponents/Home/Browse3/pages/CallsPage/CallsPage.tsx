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
  onSaveLastView: (view: string) => void;

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
  const defaultName = capitalizeFirst(table);

  const [views, setViews] = useState<TraceObjSchema[] | null>(null);

  const getTsClient = useGetTraceServerClientContext();

  const tsClient = getTsClient();
  const projectId = projectIdFromParts({entity, project});
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
        if (!viewsForPage.some(v => v.object_id === 'default')) {
          viewsForPage.push(getDefaultView(projectId, defaultName));
        }
        setViews(viewsForPage);
      })
      .catch(err => {
        console.error(err);
      });
  }, [projectId, tsClient, table, defaultName]);

  // Load view data on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(fetchViews, [table]);

  const baseView =
    views?.find(v => v.object_id === view) ??
    getDefaultView(projectId, defaultName);
  const currentViewDefinition = useCurrentViewDefinition();

  const history = useHistory();
  const onLoadView = (viewToLoad: TraceObjSchema) => {
    console.log('load view');
    console.log({viewToLoad});
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
    props.onSaveLastView(viewToLoad.object_id);
  };
  const onResetView = () => {
    console.log('onResetView');
    const viewToLoad = views?.find(v => v.object_id === view);
    console.log({view, viewToLoad});
    if (viewToLoad) {
      onLoadView(viewToLoad);
    }
  };

  const viewDef = useCurrentViewDefinition();
  const {currentViewerId, onSaveLastView} = props;
  const onUpsertView = useCallback(
    (objectId: string, name: string | null, successMessage: string) => {
      console.log('onSaveView', objectId, name);
      if (name === null) {
        // If caller doesn't provide a new name, use the existing one.
        name = baseView.val.name;
        console.log('onSaveView existing name', name);
      }
      const className = 'SavedViewTraces';
      tsClient
        .objCreate({
          obj: {
            project_id: projectIdFromParts({entity, project}),
            object_id: objectId,
            val: {
              _type: className,
              table,
              name,
              _class_name: className,
              _bases: ['SavedView', 'Object', 'BaseModel'],
              definition: viewDef,
              creatorUserId: currentViewerId,
            },
          },
        })
        .then(res => {
          console.log({res});
          const newQuery = new URLSearchParams(history.location.search);
          newQuery.set('view', objectId);
          history.push({search: newQuery.toString()});
          fetchViews();
          toast(successMessage);
          onSaveLastView(objectId);
        });
    },
    [
      entity,
      fetchViews,
      history,
      project,
      table,
      currentViewerId,
      onSaveLastView,
      baseView.val.name,
      tsClient,
      viewDef,
    ]
  );

  const onSaveNewView = () => {
    // setIsEditingName(true);
    // querySetString(history, 'view', 'placeholder');
    // // TODO: Set focus to name input
    const now = new Date();
    const objectId = `SavedView_${now
      .toISOString()
      .replace('T', '_')
      .replace(/[:.]/g, '-')
      .slice(0, -1)}`;
    onUpsertView(objectId, 'Untitled view', 'Successfully created new view.');
  };

  const onSaveView = () => {
    onUpsertView(view, null, 'Successfully saved view.');
  };

  const onRenameView = (newName: string) => {
    onUpsertView(view, newName, 'Successfully renamed view.');
  };

  const savedViewsInfo: SavedViewsInfo = {
    currentViewerId: props.currentViewerId,
    isLoading: views === null,
    currentViewId: view,
    currentViewDefinition,
    isModified: !_.isEqual(currentViewDefinition, baseView?.val.definition),
    views: views ?? [],
    baseView,
    onLoadView,
    onSaveView,
    onSaveNewView,
    onResetView,
  };
  console.log({savedViewsInfo});

  const onNameChanged = (newName: string) => {
    if (views === null) {
      return;
    }
    // Update the local state with the new name
    const updatedViews = views.map(v => {
      if (v.object_id === view) {
        return {...v, val: {...v.val, name: newName}};
      }
      return v;
    });
    setViews(updatedViews);

    // Update the server with the new name
    onRenameView(newName);
  };
  const activeName =
    view === 'placeholder' ? 'Untitled view' : baseView.val.name;
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

  // const title = useMemo(() => {
  //   // TODO: If user cancels we don't want to re-save
  //   const defaultName = isEvaluationTable ? 'Evaluations' : 'Traces';
  //   return (
  //     <EditableField
  //       placeholder="Untitled view"
  //       value={baseView?.val.name ?? defaultName}
  //       onFinish={name => onSaveView(name)}
  //       updateValue={true}
  //     />
  //   );
  // }, [baseView, onSaveView, isEvaluationTable]);

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
