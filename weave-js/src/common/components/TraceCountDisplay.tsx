import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import React from 'react';

export const TraceCountDisplay = ({
  entity,
  project,
  hasWeaveData,
}: {
  entity: string;
  project: string;
  hasWeaveData: boolean;
}) => {
  const {useCallsStats} = useWFHooks();
  const {result, loading: callsStatsLoading} = useCallsStats({
    entity,
    project,
    skip: !hasWeaveData,
  });

  return <div>{callsStatsLoading ? <LoadingDots /> : result?.count ?? 0}</div>;
};
