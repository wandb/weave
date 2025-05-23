import React, {createContext, Dispatch, ReactNode, useContext} from 'react';
import {Layout} from 'react-grid-layout';

import {loadChartsConfig, saveChartsConfig} from './chartsConfigPersistence';
import {chartAxisFields} from './extractData';

// Define breakpoints that match those in CallsCharts.tsx
// Simplified to desktop (12 cols) and mobile (1 col)
export const CHART_BREAKPOINTS = {lg: 768, xxs: 0};

export type ChartConfig = {
  id: string;
  xAxis: string;
  yAxis: string;
  plotType?: 'scatter' | 'line';
  binCount?: number; // Only for line plots
  aggregation?: 'average' | 'sum' | 'min' | 'max' | 'p95' | 'p99'; // Only for line plots
  groupKey?: string; // Field to group by, e.g., 'op_name'
};

export type ChartsState = {
  charts: ChartConfig[];
  openDrawerChartId: string | null;
  layouts: Record<string, Layout[]>;
  hoveredGroup: string | null;
};

export type ChartsAction =
  | {type: 'ADD_CHART'; payload?: Partial<ChartConfig>}
  | {type: 'REMOVE_CHART'; id: string}
  | {type: 'UPDATE_CHART'; id: string; payload: Partial<ChartConfig>}
  | {type: 'OPEN_DRAWER'; id: string}
  | {type: 'CLOSE_DRAWER'}
  | {type: 'UPDATE_LAYOUTS'; layouts: Record<string, Layout[]>}
  | {type: 'SET_HOVERED_GROUP'; group: string | null};

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
  layouts: {},
  hoveredGroup: null,
};

function chartsReducer(state: ChartsState, action: ChartsAction): ChartsState {
  switch (action.type) {
    case 'ADD_CHART': {
      const isLine = action.payload?.plotType === 'line';
      const newChart: ChartConfig = {
        id: genId(),
        xAxis: action.payload?.xAxis || defaultXAxis,
        yAxis: action.payload?.yAxis || defaultYAxis,
        plotType: action.payload?.plotType || 'scatter',
        ...(isLine ? {binCount: 20, aggregation: 'average'} : {}),
        groupKey: action.payload?.groupKey,
      };
      return {
        charts: [...state.charts, newChart],
        openDrawerChartId: state.openDrawerChartId,
        layouts: state.layouts,
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
        layouts: state.layouts,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'UPDATE_CHART': {
      return {
        charts: state.charts.map(c =>
          c.id === action.id ? {...c, ...action.payload} : c
        ),
        openDrawerChartId: state.openDrawerChartId,
        layouts: state.layouts,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'OPEN_DRAWER': {
      return {
        charts: state.charts,
        openDrawerChartId: action.id,
        layouts: state.layouts,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'CLOSE_DRAWER': {
      return {
        charts: state.charts,
        openDrawerChartId: null,
        layouts: state.layouts,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'UPDATE_LAYOUTS': {
      // Validate that layouts only contain valid breakpoint keys
      const validLayouts: Record<string, Layout[]> = {};
      Object.keys(CHART_BREAKPOINTS).forEach(breakpoint => {
        validLayouts[breakpoint] = action.layouts[breakpoint] || [];
      });

      return {
        ...state,
        layouts: validLayouts,
        hoveredGroup: state.hoveredGroup,
      };
    }
    case 'SET_HOVERED_GROUP': {
      return {
        ...state,
        hoveredGroup: action.group,
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
