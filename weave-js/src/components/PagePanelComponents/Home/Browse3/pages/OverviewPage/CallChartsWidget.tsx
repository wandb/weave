import React from 'react';

import {Chart} from '../../charts/Chart';
import {chartAxisFields} from '../../charts/extractData';
import {ChartConfig, ExtractedCallData} from '../../charts/types';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';

interface CallChartsWidgetProps {
  callData: ExtractedCallData[];
  chartConfig: ChartConfig;
  entity: string;
  project: string;
  isLoading: boolean;
  filter: WFHighLevelCallFilter;
  index: number;
  setWidgets: (widgets: Array<React.ReactNode>) => void;
  widgets: Array<React.ReactNode>;
}

const CallChartsWidget: React.FC<CallChartsWidgetProps> = ({
  callData,
  chartConfig: chart,
  entity,
  project,
  isLoading,
  filter,
  index,
  setWidgets,
  widgets,
}) => {
  const yField = chartAxisFields.find(f => f.key === chart.yAxis);
  const baseTitle = yField ? yField.label : chart.yAxis;
  const chartTitle = baseTitle;
  return (
    <div className=" w-[calc(100%-8px)]">
      <Chart
        key={chart.id}
        data={callData}
        height={280}
        xAxis={chart.xAxis}
        yAxis={chart.yAxis}
        plotType={chart.plotType || 'scatter'}
        binCount={chart.binCount}
        aggregation={chart.aggregation}
        title={chartTitle}
        customName={chart.customName}
        chartId={chart.id}
        entity={entity}
        project={project}
        groupKeys={chart.groupKeys}
        isLoading={isLoading}
        onRemove={() => {
          setWidgets(widgets.filter((_, i) => i !== index));
        }}
        filter={filter}
        noFullscreen
      />
    </div>
  );
};

export default CallChartsWidget;
