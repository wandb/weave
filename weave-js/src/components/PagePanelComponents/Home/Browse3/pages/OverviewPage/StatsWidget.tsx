import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {convertBytes} from '@wandb/weave/util';
import React, {useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {
  projectIdFromParts,
  useProjectStats,
} from '../wfReactInterface/tsDataModelHooks';

export interface StatsWidgetProps {
  project: {
    entityName: string;
    name: string;
  };
}

const StatsWidget: React.FC<StatsWidgetProps> = ({project}) => {
  const {useCallsStats} = useWFHooks();
  const {result, loading: callsStatsLoading} = useCallsStats({
    entity: project.entityName,
    project: project.name,
  });

  const {
    value: projectStats,
    loading: projectStatsLoading,
    error: projectStatsError,
  } = useProjectStats(
    projectIdFromParts({entity: project.entityName, project: project.name})
  );

  const traceCount = useMemo(
    () => (
      <div>
        {callsStatsLoading ? (
          <LoadingDots />
        ) : (
          result?.count.toLocaleString() ?? 0
        )}
      </div>
    ),
    [callsStatsLoading, result]
  );

  const [
    totalIngestionSize,
    objectsIngestionSize,
    tablesIngestionSize,
    filesIngestionSize,
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
    <React.Fragment>
      {projectStatsError ? (
        <p className="text-red-500">Error loading storage sizes</p>
      ) : (
        <div
          className="grid grid-cols-[150px_1fr] rounded border border-moon-300 bg-white p-4 [&>*:nth-child(odd)]:text-moon-400"
          style={{
            width: 'calc(100% - 8px)',
            height: 'calc(100% - 8px)',
          }}>
          <div>Total traces</div>
          <div>{traceCount}</div>
          <div>Traces ingestion size</div>
          <div>{totalIngestionSize}</div>
          <div>Objects ingestion size</div>
          <div>{objectsIngestionSize}</div>
          <div>Tables ingestion size</div>
          <div>{tablesIngestionSize}</div>
          <div>Files ingestion size</div>
          <div>{filesIngestionSize}</div>
        </div>
      )}
    </React.Fragment>
  );
};

export default StatsWidget;
