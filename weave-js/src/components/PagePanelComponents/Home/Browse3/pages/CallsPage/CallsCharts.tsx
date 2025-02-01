import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {MOON_400} from '../../../../../../common/css/color.styles';
import * as userEvents from '../../../../../../integrations/analytics/userEvents';
import {IconInfo} from '../../../../../Icon';
import {WaveLoader} from '../../../../../Loaders/WaveLoader';
import {Tailwind} from '../../../../../Tailwind';
import {WFHighLevelCallFilter} from './callsTableFilter';
import {useCallsForQuery} from './callsTableQuery';
import {
  ErrorPlotlyChart,
  LatencyPlotlyChart,
  RequestsPlotlyChart,
} from './Charts';

type CallsChartsProps = {
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
};

const Chart = ({
  isLoading,
  chartData,
  title,
}: {
  isLoading: boolean;
  chartData: any;
  title: string;
}) => {
  const CHART_CONTAINER_STYLES =
    'flex-1 rounded-lg border border-moon-250 bg-white p-10';
  const CHART_TITLE_STYLES = 'ml-12 mt-8 text-base font-semibold text-moon-750';
  const CHART_HEIGHT = 250;
  const LOADING_CONTAINER_STYLES = `flex h-[${CHART_HEIGHT}px] items-center justify-center`;

  let chart = null;
  if (isLoading) {
    chart = (
      <div className={LOADING_CONTAINER_STYLES}>
        <WaveLoader size="small" />
      </div>
    );
  } else if (chartData.length > 0) {
    switch (title) {
      case 'Latency':
        chart = (
          <LatencyPlotlyChart chartData={chartData} height={CHART_HEIGHT} />
        );
        break;
      case 'Errors':
        chart = (
          <ErrorPlotlyChart chartData={chartData} height={CHART_HEIGHT} />
        );
        break;
      case 'Requests':
        chart = (
          <RequestsPlotlyChart chartData={chartData} height={CHART_HEIGHT} />
        );
        break;
    }
  } else {
    chart = (
      <div className={LOADING_CONTAINER_STYLES}>
        <div className="flex flex-col items-center justify-center">
          <IconInfo color={MOON_400} />
          <div className="text-moon-500">
            No data available for the selected time frame
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className={CHART_CONTAINER_STYLES}>
      <div className={CHART_TITLE_STYLES}>{title}</div>
      {chart}
    </div>
  );
};

export const CallsCharts = ({
  entity,
  project,
  filter,
  filterModelProp,
}: CallsChartsProps) => {
  const columns = useMemo(
    () => ['started_at', 'ended_at', 'exception', 'id'],
    []
  );
  const columnSet = useMemo(() => new Set(columns), [columns]);
  const sortCalls: GridSortModel = useMemo(
    () => [{field: 'started_at', sort: 'desc'}],
    []
  );
  const page = useMemo(
    () => ({
      pageSize: 1000,
      page: 0,
    }),
    []
  );

  const calls = useCallsForQuery(
    entity,
    project,
    filter,
    filterModelProp,
    page,
    sortCalls,
    columnSet,
    columns
  );

  const [callsQueryStartTime, setCallsQueryStartTime] = useState<number | null>(
    null
  );
  const sentEvent = useRef(false);
  useEffect(() => {
    if (sentEvent.current) {
      return;
    }
    if (calls.loading) {
      const startTime = Date.now();
      setCallsQueryStartTime(startTime);
    } else if (!calls.loading && callsQueryStartTime !== null) {
      const endTime = Date.now();
      const latency = endTime - callsQueryStartTime;
      userEvents.metricsPlotsViewed({
        entity,
        project,
        latency,
      });
      sentEvent.current = true;
    }
  }, [calls.loading, callsQueryStartTime, entity, project]);

  const chartData = useMemo(() => {
    if (calls.loading || !calls.result || calls.result.length === 0) {
      return {latency: [], errors: [], requests: []};
    }

    const data: {
      latency: Array<{started_at: string; latency: number}>;
      errors: Array<{started_at: string; isError: boolean}>;
      requests: Array<{started_at: string}>;
    } = {
      latency: [],
      errors: [],
      requests: [],
    };

    calls.result.forEach(call => {
      const started_at = call.traceCall?.started_at;
      if (!started_at) {
        return;
      }
      const ended_at = call.traceCall?.ended_at;

      const isError =
        call.traceCall?.exception !== null &&
        call.traceCall?.exception !== undefined &&
        call.traceCall?.exception !== '';

      data.requests.push({started_at});

      if (isError) {
        data.errors.push({started_at, isError});
      } else {
        data.errors.push({started_at, isError: false});
      }

      if (ended_at != null) {
        const startTime = new Date(started_at).getTime();
        const endTime = new Date(ended_at).getTime();
        const latency = endTime - startTime;
        data.latency.push({started_at, latency});
      }
    });
    return data;
  }, [calls.result, calls.loading]);

  const charts = (
    <div className="m-10 flex flex-row gap-10">
      <Chart
        isLoading={calls.loading}
        chartData={chartData.latency}
        title="Latency"
      />
      <Chart
        isLoading={calls.loading}
        chartData={chartData.errors}
        title="Errors"
      />
      <Chart
        isLoading={calls.loading}
        chartData={chartData.requests}
        title="Requests"
      />
    </div>
  );

  return (
    <Tailwind>
      {/* setting the width to the width of the screen minus the sidebar width because of overflow: 'hidden' properties in SimplePageLayout causing issues */}
      <div className="w-full md:max-w-[calc(100vw-56px)]">
        <div className="mb-20 mt-10">{charts}</div>
      </div>
    </Tailwind>
  );
};
