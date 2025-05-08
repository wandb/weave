import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  projectIdFromParts,
  useProjectStats,
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

  const {
    value: projectStats,
    loading: projectStatsLoading,
    error: projectStatsError,
  } = useProjectStats(projectIdFromParts({entity, project}));

  const traceCount = useMemo(
    () => <div>{callsStatsLoading ? <LoadingDots /> : result?.count ?? 0}</div>,
    [callsStatsLoading, result]
  );

  const [
    totalStorageSize,
    objectsStorageSize,
    tablesStorageSize,
    filesStorageSize,
  ] = useMemo(() => {
    if (projectStatsLoading) {
      return Array(4).fill(<LoadingDots />);
    }
    return [
      convertBytes(projectStats?.trace_storage_size_bytes ?? 0),
      convertBytes(projectStats?.objects_storage_size_bytes ?? 0),
      convertBytes(projectStats?.tables_storage_size_bytes ?? 0),
      convertBytes(projectStats?.files_storage_size_bytes ?? 0),
    ];
  }, [projectStatsLoading, projectStats]);

  return (
    <section className="tw-style">
      {projectStatsError && (
        <p className="text-red-500">Error loading storage sizes</p>
      )}
      {!projectStatsError && (
        <div className="grid w-min grid-cols-[150px_1fr] gap-4 [&>*:nth-child(odd)]:text-[#aaa]">
          <div>Total traces</div>
          <div>{traceCount}</div>
          <div>Traces storage size</div>
          <div>{totalStorageSize}</div>
          <div>Objects storage size</div>
          <div>{objectsStorageSize}</div>
          <div>Tables storage size</div>
          <div>{tablesStorageSize}</div>
          <div>Files storage size</div>
          <div>{filesStorageSize}</div>
        </div>
      )}
    </section>
  );
};
