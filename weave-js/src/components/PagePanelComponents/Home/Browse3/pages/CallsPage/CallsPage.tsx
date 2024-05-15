import _ from 'lodash';
import React, {FC, useMemo} from 'react';

import {
  WeaveHeaderExtrasContext,
  WeaveHeaderExtrasProvider,
} from '../../context';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {opNiceName} from '../common/Links';
import {SimplePageLayout} from '../common/SimplePageLayout';
import {useInitializingFilter} from '../util';
import {
  opVersionKeyToRefUri,
  opVersionRefOpName,
} from '../wfReactInterface/utilities';
import {CallsTable} from './CallsTable';
import {WFHighLevelCallFilter} from './callsTableFilter';

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
}> = props => {
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
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
      return opNiceName(opName) + ' Traces';
    }
    return 'Traces';
  }, [filter.opVersionRefs, isEvaluationTable]);

  return (
    <WeaveHeaderExtrasProvider>
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
                hideControls={filter.frozen}
                initialFilter={filter}
                onFilterUpdate={setFilter}
              />
            ),
          },
        ]}
        headerExtra={<HeaderExtras />}
      />
    </WeaveHeaderExtrasProvider>
  );
};

export const useEvaluationsFilter = (
  entity: string,
  project: string
): WFHighLevelCallFilter => {
  return useMemo(() => {
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
  }, [entity, project]);
};

export const useCurrentFilterIsEvaluationsFilter = (
  currentFilter: WFHighLevelCallFilter,
  entity: string,
  project: string
) => {
  const evaluationsFilter = useEvaluationsFilter(entity, project);
  return _.isEqual(currentFilter, evaluationsFilter);
};
