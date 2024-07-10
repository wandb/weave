import * as Plotly from 'plotly.js';
import React, {useEffect, useMemo, useRef} from 'react';

import {usePeekLocation} from '../../../../context';
import {PLOT_GRID_COLOR} from '../../ecpConstants';

export type ScatterPlotPoint = {
  x: number;
  y: number;
  size: number;
  color: string;
  selected?: boolean;
};
type ScatterPlotData = ScatterPlotPoint[];
export const PlotlyScatterPlot: React.FC<{
  height: number;
  xColor: string;
  yColor: string;
  xIsPercentage: boolean;
  yIsPercentage: boolean;
  xTitle: string;
  yTitle: string;
  data: ScatterPlotData;
  onRangeChange: (
    xMin?: number,
    xMax?: number,
    yMin?: number,
    yMax?: number
  ) => void;
}> = props => {
  const divRef = useRef<HTMLDivElement>(null);
  const plotlyData: Plotly.Data[] = useMemo(() => {
    return props.data.map(s => ({
      x: [s.x],
      y: [s.y],
      mode: 'markers',
      type: 'scatter',
      hoverinfo: 'none',
      marker: {
        color: s.color,
        size: s.size,
        symbol: s.selected ? 'circle' : 'circle-open',
      },
    }));
  }, [props.data]);

  const ranges = useMemo(() => {
    const vals = props.data.map(s => [s.x, s.y]).flat();
    return {
      x: [Math.min(...vals), Math.max(...vals)],
      y: [Math.min(...vals), Math.max(...vals)],
    };
  }, [props.data]);

  const lowerBound = Math.min(ranges.x[0], ranges.y[0]);
  const upperBound = Math.min(ranges.x[1], ranges.y[1]);

  const plotlyLayout: Partial<Plotly.Layout> = useMemo(() => {
    const shapes: Partial<Plotly.Layout['shapes']> = [];
    if (plotlyData.length > 0) {
      shapes.push({
        type: 'line',
        x0: lowerBound,
        y0: lowerBound,
        x1: upperBound,
        y1: upperBound,
        line: {
          color: 'rgba(50, 171, 96, 1)',
          width: 2,
          dash: 'dot',
        },
      });
    }
    return {
      height: props.height,
      showlegend: false,
      margin: {
        l: 0, // legend
        r: 0,
        b: 20, // legend
        t: 0,
        pad: 0,
      },
      dragmode: 'select',
      xaxis: {
        tickformat: props.xIsPercentage ? '.0%' : '',
        gridcolor: PLOT_GRID_COLOR,
        linecolor: props.xColor,
        linewidth: 2,
        title: {
          text: props.xTitle,
          standoff: 10,
        },
        automargin: true,
      },
      yaxis: {
        tickformat: props.yIsPercentage ? '.0%' : '',
        gridcolor: PLOT_GRID_COLOR,
        linecolor: props.yColor,
        linewidth: 2,
        automargin: true,
        title: {
          text: props.yTitle,
          standoff: 10,
        },
      },
      shapes,
    } as Partial<Plotly.Layout>;
  }, [
    lowerBound,
    plotlyData.length,
    props.height,
    props.xColor,
    props.xIsPercentage,
    props.xTitle,
    props.yColor,
    props.yIsPercentage,
    props.yTitle,
    upperBound,
  ]);
  const plotlyConfig = useMemo(() => {
    return {
      displayModeBar: false,
      responsive: true,
    };
  }, []);

  useEffect(() => {
    if (divRef.current) {
      const current = divRef.current;
      Plotly.newPlot(current, plotlyData, plotlyLayout, plotlyConfig);

      // Set up event listener for relayout (zoom and range change)
      (current as any).on('plotly_selected', (eventData: any) => {
        if (eventData == null) {
          // Clear bounding box:
          Plotly.relayout(current, {
            dragmode: undefined,
          })
            .then(() => {
              return Plotly.relayout(current, {
                dragmode: 'select',
              });
            })
            .then(() => {
              setTimeout(() => {
                props.onRangeChange();
              }, 250); // really weird hack to get the range to clear
            });
        } else {
          const newXMin = eventData.range.x[0];
          const newXMax = eventData.range.x[1];
          const newYMin = eventData.range.y[0];
          const newYMax = eventData.range.y[1];
          props.onRangeChange(newXMin, newXMax, newYMin, newYMax);
        }
      });

      // Clean up event listener on unmount
      return () => {
        (current as any).removeAllListeners('plotly_selected');
      };
    }
    return () => {};
  }, [plotlyConfig, plotlyData, plotlyLayout, props]);

  useEffect(() => {
    if (props.data && divRef.current != null) {
      Plotly.relayout(divRef.current, {
        dragmode: 'zoom',
      });
      Plotly.relayout(divRef.current, {
        dragmode: 'select',
      });
    }
  }, [props.data]);

  // Hack that does not belong here to resize the plotly plot
  // when the peeking state closes
  const peekLoc = usePeekLocation();
  useEffect(() => {
    if (peekLoc == null) {
      setTimeout(() => {
        if (divRef.current != null) {
          Plotly.Plots.resize(divRef.current);
        }
      }, 250); // timeout allows resize to complete
    }
  }, [peekLoc]);

  return <div ref={divRef}></div>;
};
