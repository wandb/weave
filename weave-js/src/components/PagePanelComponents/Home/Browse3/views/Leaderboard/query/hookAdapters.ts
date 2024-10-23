import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useEffect, useState} from 'react';

import {useGetTraceServerClientContext} from '../../../pages/wfReactInterface/traceServerClientContext';
import {
  FilterAndGroupSpec,
  PythonLeaderboardObjectVal,
} from '../types/leaderboardConfigType';
import {
  getLeaderboardData,
  getPythonLeaderboardData,
  GroupedLeaderboardData,
  PythonLeaderboardEvalData,
} from './leaderboardQuery';

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

export const usePythonLeaderboardData = (
  entity: string,
  project: string,
  val: PythonLeaderboardObjectVal
): LeaderboardDataState & {evalData: PythonLeaderboardEvalData} => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [state, setState] = useState<
    LeaderboardDataState & {evalData: PythonLeaderboardEvalData}
  >({
    loading: true,
    data: {modelGroups: {}},
    evalData: {},
  });
  const deepVal = useDeepMemo(val);
  useEffect(() => {
    let mounted = true;
    getPythonLeaderboardData(
      getTraceServerClient(),
      entity,
      project,
      deepVal
    ).then(data => {
      if (mounted) {
        setState({
          loading: false,
          data: data.finalData,
          evalData: data.evalData,
        });
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, project, getTraceServerClient, deepVal]);
  return state;
};
