import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {FC, useCallback, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {toast} from '../../../../../../common/components/elements/Toast';
import {Tailwind} from '../../../../../Tailwind';
import {
  WeaveHeaderExtrasContext,
  WeaveHeaderExtrasProvider,
} from '../../context';
import {opNiceName} from '../common/opNiceName';
import {
  SimplePageLayout,
  SimplePageLayoutContext,
} from '../common/SimplePageLayout';
import {SavedViewPrefix} from '../SavedViews/SavedViewPrefix';
import {SavedViewSuffix} from '../SavedViews/SavedViewSuffix';
import {
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

  baseView: TraceObjSchema;
  views: TraceObjSchema[];
  onRecordLastView: (view: string) => void;
  fetchViews: () => void;

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
  const {entity, project, baseView, views, fetchViews} = props;
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
  const table = isEvaluationTable ? 'evaluations' : 'traces';

  const getTsClient = useGetTraceServerClientContext();

  const tsClient = getTsClient();
  const view = baseView.object_id;

  const currentViewDefinition = useCurrentViewDefinition(baseView);

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
      console.error('could not find view to reset to');
    }
  };

  const {onRecordLastView} = props;

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
              definition: currentViewDefinition,
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
      currentViewDefinition,
    ]
  );

  const onSaveNewView = () => {
    // TODO: Could we set the title into edit mode and give it keyboard focus?
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
        // Don't need to fetch views again as we will reload the page.
        // Using history replace instead of push because can't navigate back to deleted view.
        toast('Successfully deleted view.');
        onRecordLastView(getDefaultViewId(table));
        const newQuery = new URLSearchParams();
        history.replace({search: newQuery.toString()});
      });
  };

  const savedViewsInfo: SavedViewsInfo = {
    currentViewerId: props.currentViewerId,
    currentViewId: view,
    currentViewDefinition,
    isDefault: view === getDefaultViewId(table),
    isModified: !_.isEqual(currentViewDefinition, baseView.val.definition),
    views,
    baseView,
    onLoadView,
    onSaveView,
    onSaveNewView,
    onResetView,
    onDeleteView,
  };

  const onNameChanged = (newName: string) => {
    // Update the local state with the new name
    baseView.val.label = newName;
    // Update the server with the new name
    onRenameView(newName);
  };
  const activeName = baseView.val.label ?? 'Untitled view';
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
                  entity={entity}
                  project={project}
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
