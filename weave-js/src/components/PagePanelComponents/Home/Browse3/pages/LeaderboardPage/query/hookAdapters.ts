import {useEffect, useState} from 'react';

import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
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
  useEffect(() => {
    let mounted = true;
    getLeaderboardData(getTraceServerClient(), entity, project, spec).then(
      data => {
        if (mounted) {
          setState({loading: false, data});
        }
      }
    );
    return () => {
      mounted = false;
    };
  }, [entity, project, getTraceServerClient, spec]);
  return state;
};
