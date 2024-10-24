import React, {useMemo, useState} from 'react';
import {useCallsForQueryCharts} from './callsTableQuery';

import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import {Drawer} from '@mui/material';

import {WFHighLevelCallFilter} from './callsTableFilter';
import {DEFAULT_FILTER_CALLS} from './CallsTable';
import {
  ErrorPlotlyChart,
  LatencyPlotlyChart,
  RequestsPlotlyChart,
} from './Charts';
import {Tailwind} from '../../../../../Tailwind';
import {Button} from '../../../../../Button';
import {
  IconChevronDown,
  IconChevronNext,
  IconLightbulbInfo,
} from '../../../../../Icon';

type CallsChartsProps = {
  startTime?: number;
  endTime?: number;
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
  //   setFilterModel?: (newModel: GridFilterModel) => void;
};

export const CallsCharts = ({
  startTime,
  endTime,
  entity,
  project,
  filter,
  filterModelProp,
}: // filterModel,
// filter,
CallsChartsProps) => {
  const [filterModel, setFilterModel] = useState<GridFilterModel>(
    filterModelProp ?? DEFAULT_FILTER_CALLS
  );
  const columns = useMemo(() => ['summary.weave.costs', 'started_at'], []);
  const columnSet = useMemo(() => new Set(columns), [columns]);
  const sortCalls: GridSortModel = useMemo(
    () => [{field: 'started_at', sort: 'asc'}],
    []
  );
  const calls = useCallsForQueryCharts(
    entity,
    project,
    filter,
    filterModelProp,
    0,
    1000, // change back to 1000 later
    columns, // need to select columns for performance. not working??
    columnSet,
    sortCalls
  );
  const callsLoading = calls.loading;
  const [callsResult, setCallsResult] = useState(calls.result);
  const [callsTotal, setCallsTotal] = useState(calls.total);

  //   const costAndTimeData = useMemo(() => {
  //     return calls.result
  //       .filter(
  //         call =>
  //           call.traceCall?.started_at !== undefined &&
  //           getCostFromCostData(call.traceCall?.summary?.weave?.costs ?? {})
  //             .costNumeric !== undefined
  //       )
  //       .map(call => ({
  //         value: getCostFromCostData(call.traceCall?.summary?.weave?.costs ?? {})
  //           .costNumeric,
  //         timestamp: call.traceCall?.started_at ?? '',
  //       }));
  //   }, [calls.result]);

  const costAndTimeData = useMemo(() => {
    return calls.result.map(call => ({
      started_at: call.traceCall?.started_at ?? '',
      //   ended_at: call.traceCall?.ended_at ?? '',
      latency: call.traceCall?.summary?.weave?.latency_ms ?? 0,
      isError: call.traceCall?.summary?.weave?.status === 'error',
      //   timestamp: call.traceCall?.started_at ?? '',
    }));
  }, [calls.result]);
  console.log(calls.result);
  // Sum up the cost data

  console.log(
    'Cost data:',
    filter,
    filterModelProp,
    filterModel,
    calls,
    costAndTimeData,
    calls
  );
  const [isInsightsOpen, setIsInsightsOpen] = useState(true);

  const toggleInsights = () => {
    setIsInsightsOpen(!isInsightsOpen);
  };

  return (
    <Tailwind style={{marginRight: '20px'}}>
      {/* Button to toggle insights */}
      <div className="mb-10 ml-10 mr-[20px] w-full rounded-lg border border-moon-250 bg-moon-50 pr-[20px]">
        <div
          className="flex cursor-pointer items-center gap-2 p-10"
          w-full
          onClick={toggleInsights}>
          {isInsightsOpen ? <IconChevronDown /> : <IconChevronNext />}

          <IconLightbulbInfo width={18} height={18} className="text-teal-500" />
          <div className="font-source-sans-pro text-[18px] font-semibold text-moon-500">
            {'Insights'}
          </div>
        </div>

        {/* Collapsible insights section */}
        {isInsightsOpen && (
          <div className="m-10 mt-4 flex w-full">
            <div className="mb-10 flex w-full flex-row gap-[10px]">
              <div className="mb-4 w-full flex-1 rounded-lg border border-moon-250 bg-white p-[10px]">
                <LatencyPlotlyChart chartData={costAndTimeData} height={300} />
              </div>
              <div className="mb-4 w-full flex-1 rounded-lg border border-moon-250 bg-white p-[10px]">
                <ErrorPlotlyChart chartData={costAndTimeData} height={300} />
              </div>
              <div className="mb-4 w-full flex-1 rounded-lg border border-moon-250 bg-white p-[10px]">
                <RequestsPlotlyChart chartData={costAndTimeData} height={300} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Tailwind>
  );
};

// export default CallsCharts;
