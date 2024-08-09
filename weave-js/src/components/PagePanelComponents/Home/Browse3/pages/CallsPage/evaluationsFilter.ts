import _ from 'lodash';
import {useMemo} from 'react';

import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {WFHighLevelCallFilter} from './callsTableFilter';

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
