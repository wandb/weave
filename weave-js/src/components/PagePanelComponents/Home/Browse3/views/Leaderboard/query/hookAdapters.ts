import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useEffect, useState} from 'react';

import {useGetTraceServerClientContext} from '../../../pages/wfReactInterface/traceServerClientContext';
import {FilterAndGroupSpec} from '../types/leaderboardConfigType';
import {getLeaderboardData, GroupedLeaderboardData} from './leaderboardQuery';

type LeaderboardDataState = {
  loading: boolean;
  data: GroupedLeaderboardData;
};
export const useLeaderboardData = (
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
): LeaderboardDataState => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [state, setState] = useState<LeaderboardDataState>({
    loading: true,
    data: {modelGroups: {}},
  });
  const deepSpec = useDeepMemo(spec);
  useEffect(() => {
    let mounted = true;
    getLeaderboardData(getTraceServerClient(), entity, project, deepSpec).then(
      data => {
        if (mounted) {
          setState({loading: false, data});
        }
      }
    );
    return () => {
      mounted = false;
    };
  }, [entity, project, getTraceServerClient, deepSpec]);
  return state;
};
