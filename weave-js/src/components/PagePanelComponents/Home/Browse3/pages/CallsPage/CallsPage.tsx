import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import React, {createContext, FC, useContext, useMemo} from 'react';

import {
  WeaveHeaderExtrasContext,
  WeaveHeaderExtrasProvider,
} from '../../context';
import {opNiceName} from '../common/opNiceName';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useControllableState} from '../util';
import {opVersionRefOpName} from '../wfReactInterface/utilities';
import {CallsTable} from './CallsTable';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useCurrentFilterIsEvaluationsFilter} from './evaluationsFilter';

// Create a context to track if we're still adjusting the filter
export const FilterAdjustingContext = createContext<boolean>(false);
export const useFilterAdjusting = () => useContext(FilterAdjustingContext);

const HeaderExtras = () => {
  const {renderExtras} = React.useContext(WeaveHeaderExtrasContext);
  return <>{renderExtras()}</>;
};

export const CallsPage: FC<{
  entity: string;
  project: string;
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

  // Optional flag to indicate if we're still adjusting the filter
  isFilterAdjusting?: boolean;
}> = props => {
  const [filter, setFilter] = useControllableState(
    props.initialFilter ?? {},
    props.onFilterUpdate
  );

  const isEvaluationTable = useCurrentFilterIsEvaluationsFilter(
    filter,
    props.entity,
    props.project
  );

  const title = useMemo(() => {
    if (isEvaluationTable) {
      return 'Evaluations';
    }
    if (filter.opVersionRefs?.length === 1) {
      const opName = opVersionRefOpName(filter.opVersionRefs[0]);
      if (opName) {
        return opNiceName(opName) + ' Traces';
      }
    }
    return 'Traces';
  }, [filter.opVersionRefs, isEvaluationTable]);

  return (
    <WeaveHeaderExtrasProvider>
      <FilterAdjustingContext.Provider value={props.isFilterAdjusting || false}>
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
      </FilterAdjustingContext.Provider>
    </WeaveHeaderExtrasProvider>
  );
};
