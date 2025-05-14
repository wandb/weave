import React, {createContext, Dispatch, ReactNode, useContext} from 'react';

import {loadChartsConfig, saveChartsConfig} from './chartsConfigPersistence';
import {chartAxisFields} from './extractData';

export type ChartConfig = {
  id: string;
  xAxis: string;
  yAxis: string;
  plotType?: 'scatter' | 'line' | 'bar';
  binCount?: number; // For line plots and bar charts
  aggregation?: 'average' | 'sum' | 'min' | 'max' | 'p95' | 'p99'; // For line plots and bar charts
  xDomain?: [number, number]; // Refined x domain from painting
  yDomain?: [number, number]; // Refined y domain from painting
  colorGroupKey?: string; // For color grouping by input/output fields (scatter plots and line plots)
};

export type ChartsState = {
  charts: ChartConfig[];
  openDrawerChartId: string | null;
  hoveredGroup: string | null;
};

export type ChartsAction =
  | {type: 'ADD_CHART'; payload?: Partial<ChartConfig>}
  | {type: 'REMOVE_CHART'; id: string}
  | {type: 'UPDATE_CHART'; id: string; payload: Partial<ChartConfig>}
  | {type: 'OPEN_DRAWER'; id: string}
  | {type: 'CLOSE_DRAWER'}
  | {type: 'SET_HOVERED_GROUP'; group: string | null}
  | {
      type: 'SET_CHART_DOMAIN';
      id: string;
      xDomain?: [number, number];
      yDomain?: [number, number];
    }
  | {type: 'RESET_CHART_DOMAIN'; id: string};

const defaultXAxis = chartAxisFields[0]?.key || 'started_at';
const defaultYAxis =
  chartAxisFields.find(f => f.type === 'number')?.key || 'latency';

function genId() {
  return Math.random().toString(36).substr(2, 9);
}

const initialState: ChartsState = {
  charts: [
    {
      id: genId(),
      xAxis: defaultXAxis,
      yAxis: defaultYAxis,
      plotType: 'scatter',
    },
  ],
  openDrawerChartId: null,
  hoveredGroup: null,
};

function chartsReducer(state: ChartsState, action: ChartsAction): ChartsState {
  switch (action.type) {
    case 'ADD_CHART': {
      const needsBinning =
        action.payload?.plotType === 'line' ||
        action.payload?.plotType === 'bar';
      const newChart: ChartConfig = {
        id: genId(),
        xAxis: action.payload?.xAxis || defaultXAxis,
        yAxis: action.payload?.yAxis || defaultYAxis,
        plotType: action.payload?.plotType || 'scatter',
        ...(needsBinning ? {binCount: 20, aggregation: 'average'} : {}),
      };
      return {
        charts: [...state.charts, newChart],
        openDrawerChartId: state.openDrawerChartId,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'REMOVE_CHART': {
      const newCharts = state.charts.filter(c => c.id !== action.id);
      const openDrawerChartId =
        state.openDrawerChartId === action.id ? null : state.openDrawerChartId;
      return {
        charts: newCharts,
        openDrawerChartId,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'UPDATE_CHART': {
      return {
        charts: state.charts.map(c =>
          c.id === action.id ? {...c, ...action.payload} : c
        ),
        openDrawerChartId: state.openDrawerChartId,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'OPEN_DRAWER': {
      return {
        charts: state.charts,
        openDrawerChartId: action.id,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'CLOSE_DRAWER': {
      return {
        charts: state.charts,
        openDrawerChartId: null,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'SET_HOVERED_GROUP': {
      return {
        ...state,
        hoveredGroup: action.group,
      };
    }
    case 'SET_CHART_DOMAIN': {
      return {
        charts: state.charts.map(c =>
          c.id === action.id
            ? {...c, xDomain: action.xDomain, yDomain: action.yDomain}
            : c
        ),
        openDrawerChartId: state.openDrawerChartId,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'RESET_CHART_DOMAIN': {
      return {
        charts: state.charts.map(c =>
          c.id === action.id
            ? {...c, xDomain: undefined, yDomain: undefined}
            : c
        ),
        openDrawerChartId: state.openDrawerChartId,
        hoveredGroup: state.hoveredGroup,
      };
    }
    default:
      return state;
  }
}

const ChartsStateContext = createContext<ChartsState | undefined>(undefined);
const ChartsDispatchContext = createContext<Dispatch<ChartsAction> | undefined>(
  undefined
);

export const ChartsProvider = ({children}: {children: ReactNode}) => {
  const [state, dispatch] = React.useReducer(
    chartsReducer,
    undefined,
    () => loadChartsConfig() || initialState
  );

  React.useEffect(() => {
    saveChartsConfig(state);
  }, [state]);

  return (
    <ChartsStateContext.Provider value={state}>
      <ChartsDispatchContext.Provider value={dispatch}>
        {children}
      </ChartsDispatchContext.Provider>
    </ChartsStateContext.Provider>
  );
};

export function useChartsState() {
  const ctx = useContext(ChartsStateContext);
  if (!ctx)
    throw new Error('useChartsState must be used within ChartsProvider');
  return ctx;
}

export function useChartsDispatch() {
  const ctx = useContext(ChartsDispatchContext);
  if (!ctx)
    throw new Error('useChartsDispatch must be used within ChartsProvider');
  return ctx;
}
