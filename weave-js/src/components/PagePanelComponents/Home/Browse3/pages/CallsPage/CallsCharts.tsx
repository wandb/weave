import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import React, {useMemo, useState} from 'react';

import {
  IconChevronDown,
  IconChevronNext,
  IconLightbulbInfo,
} from '../../../../../Icon';
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
  const calls = useCallsForQuery(
    entity,
    project,
    filter,
    filterModelProp,
    sortCalls,
    undefined,
    columnSet,
    columns,
    0,
    1000
  );
  const [isInsightsOpen, setIsInsightsOpen] = useState(false);

  const toggleInsights = () => {
    setIsInsightsOpen(!isInsightsOpen);
  };

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

      if (ended_at !== undefined) {
        const startTime = new Date(started_at).getTime();
        const endTime = new Date(ended_at).getTime();
        const latency = endTime - startTime;
        data.latency.push({started_at, latency});
      }
    });
    return data;
  }, [calls.result, calls.loading]);

  const chartWrapper = 'flex-1 rounded-lg border border-moon-250 bg-white p-10';

  const charts = (
    <div className="m-10 flex flex-row gap-10">
      <div className={chartWrapper}>
        <LatencyPlotlyChart chartData={chartData.latency} height={300} />
      </div>
      <div className={chartWrapper}>
        <ErrorPlotlyChart chartData={chartData.errors} height={300} />
      </div>
      <div className={chartWrapper}>
        <RequestsPlotlyChart chartData={chartData.requests} height={300} />
      </div>
    </div>
  );

  return (
    <Tailwind>
      {/* setting the width to the width of the screen minus the sidebar width because of overflow: 'hidden' properties in SimplePageLayout causing issues */}
      <div className="md:w-[calc(100vw-56px)]">
        <div className="m-10">
          <div className="w-full rounded-lg border border-moon-250 bg-moon-50 p-10">
            <div
              className="flex cursor-pointer items-center gap-2"
              onClick={toggleInsights}>
              {isInsightsOpen ? <IconChevronDown /> : <IconChevronNext />}
              <IconLightbulbInfo
                width={18}
                height={18}
                className="text-teal-500"
              />
              <div className="font-source-sans-pro mt-[1px] text-[18px] font-semibold text-moon-500">
                Insights
              </div>
            </div>
            {isInsightsOpen && charts}
          </div>
        </div>
      </div>
    </Tailwind>
  );
};
