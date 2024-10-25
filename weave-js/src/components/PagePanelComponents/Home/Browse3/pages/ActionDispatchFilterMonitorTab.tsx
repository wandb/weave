import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {useWFHooks} from './wfReactInterface/context';
import {useGetTraceServerClientContext} from './wfReactInterface/traceServerClientContext';
import {Feedback} from './wfReactInterface/traceServerClientTypes';
import {convertISOToDate, projectIdFromParts} from './wfReactInterface/tsDataModelHooks';

interface PlotData {
  id: string;
  title: string;
  xData: number[];
  yData: number[];
}

const PlotComponent: React.FC<PlotData> = ({id, title, xData, yData}) => {
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (plotRef.current) {
      const data: Plotly.Data[] = [
        {
          x: xData,
          y: yData,
          type: 'scatter',
          mode: 'lines+markers',
          marker: {color: 'blue'},
        },
      ];

      const layout: Partial<Plotly.Layout> = {
        title: {
          text: title,
          font: {size: 14},
        },
        xaxis: {title: 'Time', titlefont: {size: 10}, tickfont: {size: 8}},
        yaxis: {title: 'Value', titlefont: {size: 10}, tickfont: {size: 8}},
        autosize: true,
        margin: {l: 40, r: 20, t: 30, b: 30},
        // height: 150,
        font: {size: 10},
      };

      const config: Partial<Plotly.Config> = {
        displayModeBar: false, // This removes the control buttons
      };

      Plotly.newPlot(plotRef.current, data, layout, config);

      return () => {
        if (plotRef.current) {
          Plotly.purge(plotRef.current);
        }
      };
    }
  }, [id, title, xData, yData]);

  return <div style={{width: '100%', height: '100%'}} ref={plotRef} />;
};

export const ActionDispatchFilterMonitorTab: React.FC<{
  entity: string;
  project: string;
  dispatchFilterRef: string;
}> = ({entity, project, dispatchFilterRef}) => {
  const [plotsData, setPlotsData] = useState<PlotData[]>([]);
  console.log(dispatchFilterRef)
  const data = useFeedbackQuery(entity, project, dispatchFilterRef);
  console.log(data)

  const series = useMemo(() => {
    const res: {[metricName: string]: {xData: number[], yData: number[]}} = {};
    data.forEach(d => {
      console.log(d)
      const output = d.payload.output;
      Object.entries(output).forEach(([metricName, value]) => {
        console.log(typeof value)
        if (typeof value !== 'number' && typeof value !== 'boolean') {
          return;
        }
        console.log(metricName, value)
        if (!(metricName in res)) {
          res[metricName] = {xData: [], yData: []};
        }
        res[metricName].xData.push(convertISOToDate(d.created_at).getTime());
        res[metricName].yData.push(value);
      })
    })
    console.log(res)
    return Object.entries(res).map(([metricName, series]) => ({
      id: metricName,
      title: metricName,
      ...series,
    }));
  }, [data]);

  console.log(series)

  useEffect(() => {
    setPlotsData(series);
  }, [series]);

  return (
    <div
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <div
        style={{
          height: '200px',
          display: 'flex',
          flexDirection: 'row',
          overflowX: 'auto',
          padding: '10px',
        }}>
        {plotsData.map(plot => (
          <div
            key={plot.id}
            style={{flex: '0 0 33.33%', minWidth: '200px', height: '100%'}}>
            <PlotComponent {...plot} />
          </div>
        ))}
      </div>
      <div
        style={{
          flex: 1,
          backgroundColor: '#f0f0f0',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          overflowY: 'auto',
        }}>
        <TableData entity={entity} project={project} dispatchFilterRef={dispatchFilterRef} />
      </div>
    </div>
  );
};

const TableData: React.FC<{
  entity: string;
  project: string;
  dispatchFilterRef: string;
}> = ({entity, project, dispatchFilterRef}) => {
//   const feedback = useFeedbackQuery(entity, project, dispatchFilterRef);
//   console.log(feedback);
  return <div>Table Data</div>;
};

const useFeedbackQuery = (entity: string, project: string, dispatchFilterRef: string) => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  useEffect(() => {
    let isMounted = true;
    client.readBatch({refs: [dispatchFilterRef]}).then(res => {
        console.log(res)
      // THIS IS NOT FILTERED BY OP!
      const opName = res.vals[0].op_name;
      const configuredActionRef = res.vals[0].configured_action_ref;
      console.log(configuredActionRef)
      client
      .feedbackQuery({
        project_id: projectIdFromParts({entity, project}),
        query: {
          $expr: {
            $eq: [{$getField: 'payload.configured_action_ref'}, {$literal: configuredActionRef}],
          },
        },
        sort_by: [{field: 'created_at', direction: 'desc'}],
      })
      .then(res => {
        if (isMounted) {
          if ('result' in res) {
            setFeedback(res.result ?? []);
          } else {
            setFeedback([]);
          }
        }
      });
    })
    
    return () => {
      isMounted = false;
    };
  }, [client, dispatchFilterRef, entity, project]);
  return feedback;
};
