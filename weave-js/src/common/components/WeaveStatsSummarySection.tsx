import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  projectIdFromParts,
  useFilesStats,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {convertBytes} from '@wandb/weave/util';
import React, {useMemo} from 'react';

export const WeaveStatsSummarySection = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => {
  const {useCallsStats} = useWFHooks();
  const {result, loading: callsStatsLoading} = useCallsStats({
    entity,
    project,
    includeTotalStorageSize: true,
  });

  const {value: filesStatsResult, loading: filesStatsLoading} = useFilesStats(
    projectIdFromParts({entity, project})
  );

  const traceCount = useMemo(
    () => <div>{callsStatsLoading ? <LoadingDots /> : result?.count ?? 0}</div>,
    [callsStatsLoading, result]
  );
  const totalStorageSize = useMemo(
    () =>
      callsStatsLoading ? (
        <LoadingDots />
      ) : (
        convertBytes(result?.total_storage_size_bytes ?? 0)
      ),
    [callsStatsLoading, result]
  );
  const fileStorageSize = useMemo(
    () =>
      filesStatsLoading ? (
        <LoadingDots />
      ) : (
        convertBytes(filesStatsResult?.total_size_bytes ?? 0)
      ),
    [filesStatsLoading, filesStatsResult]
  );

  return (
    <>
      <div className="overview-item">
        <div className="overview-key">Total traces</div>
        <div className="overview-value">{traceCount}</div>
      </div>
      <div className="overview-item">
        <div className="overview-key">Total traces size</div>
        <div className="overview-value">{totalStorageSize}</div>
      </div>
      <div className="overview-item">
        <div className="overview-key">File storage size</div>
        <div className="overview-value">{fileStorageSize}</div>
      </div>
    </>
  );
};
