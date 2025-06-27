/*
  ChartsContext.tsx

  The context keeps track of the charts, and their configuration. It also provides
  a way to add, remove, and update charts.
*/
import React, {createContext, Dispatch, ReactNode, useContext} from 'react';
import {v4 as uuidv4} from 'uuid';

import {chartAxisFields} from './extractData';
import {loadChartsConfig, saveChartsConfig} from './persistence';
import {ChartConfig, ChartsAction, ChartsState} from './types';

const defaultXAxis = chartAxisFields[0]?.key || 'started_at';
const defaultYAxis =
  chartAxisFields.find(f => f.type === 'number')?.key || 'latency';

function chartsReducer(state: ChartsState, action: ChartsAction): ChartsState {
  switch (action.type) {
    case 'ADD_CHART': {
      const needsBinning =
        action.payload?.plotType === 'line' ||
        action.payload?.plotType === 'bar';
      const newChart: ChartConfig = {
        id: uuidv4(),
        xAxis: action.payload?.xAxis || defaultXAxis,
        yAxis: action.payload?.yAxis || defaultYAxis,
        plotType: action.payload?.plotType || 'scatter',
        ...(needsBinning ? {binCount: 20, aggregation: 'average'} : {}),
      };
      return {
        ...state,
        charts: [...state.charts, newChart],
      };
    }
    case 'REMOVE_CHART': {
      const newCharts = state.charts.filter(c => c.id !== action.id);
      const openDrawerChartId =
        state.openDrawerChartId === action.id ? null : state.openDrawerChartId;
      return {
        ...state,
        charts: newCharts,
        openDrawerChartId,
      };
    }
    case 'UPDATE_CHART': {
      return {
        ...state,
        charts: state.charts.map(c =>
          c.id === action.id ? {...c, ...action.payload} : c
        ),
      };
    }
    case 'OPEN_DRAWER': {
      return {
        ...state,
        openDrawerChartId: action.id,
      };
    }
    case 'CLOSE_DRAWER': {
      return {
        ...state,
        openDrawerChartId: null,
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

export const ChartsProvider = ({
  children,
  entity,
  project,
}: {
  children: ReactNode;
  entity: string;
  project: string;
}) => {
  const [state, dispatch] = React.useReducer(chartsReducer, undefined, () => {
    const loadedCharts = loadChartsConfig(entity, project);
    return {
      charts: loadedCharts,
      openDrawerChartId: null,
    };
  });

  React.useEffect(() => {
    saveChartsConfig(state.charts, entity, project);
  }, [state, entity, project]);

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
