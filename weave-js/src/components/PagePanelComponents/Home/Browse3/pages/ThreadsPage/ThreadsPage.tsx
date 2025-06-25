import {
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import React, {FC, useMemo} from 'react';

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
import {getDefaultViewId, SavedViewsInfo} from '../SavedViews/savedViewUtil';
import {ViewName} from '../SavedViews/ViewName';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {ThreadsTable} from './ThreadsTable';

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

  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;

  sortModel: GridSortModel;
  setSortModel: (newModel: GridSortModel) => void;

  paginationModel: GridPaginationModel;
  setPaginationModel: (newModel: GridPaginationModel) => void;
}> = props => {
  const {baseView, views, fetchViews, onRecordLastView} = props;

  const table = 'threads';
  const view = baseView.object_id;

  const savedViewsInfo: SavedViewsInfo = useMemo(
    () => ({
      currentViewerId: props.currentViewerId,
      currentViewId: view,
      currentViewDefinition: baseView.val.definition,
      isDefault: view === getDefaultViewId(table),
      isModified: false, // Simplified for threads
      isSaving: false,
      views,
      baseView,
      onLoadView: () => {}, // Simplified for threads
      onSaveView: () => {}, // Simplified for threads
      onSaveNewView: () => {}, // Simplified for threads
      onResetView: () => {}, // Simplified for threads
      onDeleteView: () => {}, // Simplified for threads
    }),
    [props.currentViewerId, view, baseView, views, table]
  );

  const activeName = baseView.val.label ?? 'Threads view';
  const title = (
    <Tailwind>
      <ViewName value={activeName} />
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
