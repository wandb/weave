import React, {createContext, Dispatch, ReactNode, useContext} from 'react';
import {useLocation} from 'react-router-dom';

import {chartAxisFields} from './extractData';
import {loadChartsConfig, saveChartsConfig} from './persistence';
import {ChartConfig, PageType} from './types';

export type ChartsState = {
  charts: ChartConfig[];
  openDrawerChartId: string | null;
  hoveredGroup: string | null;
  pageType: PageType;
};

export type ChartsAction =
  | {type: 'ADD_CHART'; payload?: Partial<ChartConfig>}
  | {type: 'REMOVE_CHART'; id: string}
  | {type: 'UPDATE_CHART'; id: string; payload: Partial<ChartConfig>}
  | {type: 'OPEN_DRAWER'; id: string}
  | {type: 'CLOSE_DRAWER'}
  | {type: 'SET_HOVERED_GROUP'; group: string | null}
  | {type: 'SET_PAGE_TYPE'; pageType: PageType}
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
  pageType: 'unknown',
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
    case 'SET_HOVERED_GROUP': {
      return {
        ...state,
        hoveredGroup: action.group,
      };
    }
    case 'SET_PAGE_TYPE': {
      return {
        ...state,
        pageType: action.pageType,
      };
    }
    case 'SET_CHART_DOMAIN': {
      return {
        ...state,
        charts: state.charts.map(c =>
          c.id === action.id
            ? {...c, xDomain: action.xDomain, yDomain: action.yDomain}
            : c
        ),
      };
    }
    case 'RESET_CHART_DOMAIN': {
      return {
        ...state,
        charts: state.charts.map(c =>
          c.id === action.id
            ? {...c, xDomain: undefined, yDomain: undefined}
            : c
        ),
      };
    }
    default:
      return state;
  }
}

function getPageTypeFromLocation(pathname: string): PageType {
  if (pathname.includes('/weave/traces')) {
    return 'traces';
  } else if (pathname.includes('/weave/evaluations')) {
    return 'evaluations';
  }
  return 'unknown';
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
  const location = useLocation();
  const pageType = getPageTypeFromLocation(location.pathname);

  const [state, dispatch] = React.useReducer(chartsReducer, undefined, () => {
    const loadedState =
      loadChartsConfig(entity, project, pageType) || initialState;
    return {
      ...loadedState,
      pageType,
    };
  });

  React.useEffect(() => {
    const newPageType = getPageTypeFromLocation(location.pathname);
    if (state.pageType !== newPageType) {
      dispatch({type: 'SET_PAGE_TYPE', pageType: newPageType});
    }
  }, [location.pathname, state.pageType]);

  React.useEffect(() => {
    saveChartsConfig(state, entity, project, state.pageType);
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
