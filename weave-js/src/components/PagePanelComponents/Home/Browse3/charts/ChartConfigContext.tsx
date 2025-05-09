import React, {createContext, useContext, useEffect, useReducer} from 'react';

import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';
import {getDefaultChartConfigs} from './CallsCharts';
import {loadChartConfigs, saveChartConfigs} from './chartConfigPersistence';
import {ChartConfig} from './ChartTypes';

export type ChartConfigAction =
  | {type: 'initialize'; configs: ChartConfig[]}
  | {type: 'add'; config: ChartConfig}
  | {type: 'update'; config: ChartConfig}
  | {type: 'delete'; id: string};

export type ChartConfigState = {
  configs: ChartConfig[];
  loading: boolean;
  error?: string;
};

const ChartConfigContext = createContext<{
  state: ChartConfigState;
  dispatch: React.Dispatch<ChartConfigAction>;
} | null>(null);

function chartConfigReducer(
  state: ChartConfigState,
  action: ChartConfigAction
): ChartConfigState {
  switch (action.type) {
    case 'initialize':
      return {
        ...state,
        configs: action.configs,
        loading: false,
        error: undefined,
      };
    case 'add':
      return {...state, configs: [...state.configs, action.config]};
    case 'update':
      return {
        ...state,
        configs: state.configs.map(cfg =>
          (cfg as ChartConfig).id === (action.config as ChartConfig).id
            ? action.config
            : cfg
        ),
      };
    case 'delete':
      return {
        ...state,
        configs: state.configs.filter(
          cfg => (cfg as ChartConfig).id !== action.id
        ),
      };
    default:
      return state;
  }
}

export const ChartConfigProvider: React.FC<{
  projectId: string;
  children: React.ReactNode;
}> = ({projectId, children}) => {
  const [state, dispatch] = useReducer(chartConfigReducer, {
    configs: [],
    loading: true,
  });

  const getClient = useGetTraceServerClientContext();

  // Load configs on mount
  useEffect(() => {
    let mounted = true;
    loadChartConfigs(getClient(), projectId).then(
      (configs: ChartConfig[]) => {
        if (mounted) {
          if (configs.length > 0) {
            dispatch({type: 'initialize', configs});
          } else {
            dispatch({type: 'initialize', configs: getDefaultChartConfigs()});
          }
        }
      },
      (err: unknown) => {
        if (mounted)
          dispatch({type: 'initialize', configs: getDefaultChartConfigs()});
      }
    );
    return () => {
      mounted = false;
    };
  }, [getClient, projectId]);

  // Save configs on change (debounced in persistence layer)
  useEffect(() => {
    if (!state.loading) {
      saveChartConfigs(getClient(), projectId, state.configs);
    }
  }, [getClient, projectId, state.configs, state.loading]);

  return (
    <ChartConfigContext.Provider value={{state, dispatch}}>
      {children}
    </ChartConfigContext.Provider>
  );
};

export function useChartConfigContext() {
  const ctx = useContext(ChartConfigContext);
  if (!ctx)
    throw new Error(
      'useChartConfigContext must be used within ChartConfigProvider'
    );
  return ctx;
}
