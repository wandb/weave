import {
  constNode,
  constNone,
  list,
  Node,
  opArray,
  opDict,
  Stack,
  typedDict,
} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import {useMemo} from 'react';

import {
  useWeaveContext,
  useWeaveRedesignedPlotConfigEnabled,
} from '../../../context';
import * as LLReact from '../../../react';
import {usePanelContext} from '../PanelContext';
import * as TableState from '../PanelTable/tableState';
import {useTableStatesWithRefinedExpressions} from '../PanelTable/tableStateReact';
import * as PlotState from './plotState';
import {
  AnyPlotConfig,
  ConcretePlotConfig,
  LAZY_PATHS,
  PlotConfig,
} from './versions';

export const useConfig = (
  inputNode: Node,
  propsConfig?: AnyPlotConfig
): {config: PlotConfig; isRefining: boolean} => {
  const {stack} = usePanelContext();
  const weave = useWeaveContext();
  const redesignedPlotConfigEnabled = useWeaveRedesignedPlotConfigEnabled();

  const newConfig = useMemo(() => {
    return PlotState.setDefaultSeriesNames(
      PlotState.panelPlotDefaultConfig(inputNode, propsConfig, stack),
      !!redesignedPlotConfigEnabled
    );
  }, [propsConfig, inputNode, stack, redesignedPlotConfigEnabled]);

  const defaultColNameStrippedConfig = useMemo(
    () =>
      produce(newConfig, draft => {
        draft.series.forEach(s => {
          ['pointShape' as const, 'pointSize' as const].forEach(colName => {
            if (s.table.columnNames[s.dims[colName]] === colName) {
              s.table = TableState.updateColumnName(
                s.table,
                s.dims[colName],
                ''
              );
            }
          });
        });
      }),
    [newConfig]
  );

  const tableStates = useMemo(
    () => defaultColNameStrippedConfig.series.map(s => s.table),
    [defaultColNameStrippedConfig.series]
  );

  const loadable = useTableStatesWithRefinedExpressions(
    tableStates,
    inputNode,
    stack,
    weave
  );

  const configWithRefinedExpressions = useMemo(() => {
    return loadable.loading
      ? newConfig
      : produce(newConfig, draft => {
          draft.series.forEach((s, i) => {
            s.table = loadable.result[i];
          });
        });
  }, [loadable, newConfig]);

  const final = useMemo(
    () => ({
      config: configWithRefinedExpressions,
      isRefining: loadable.loading,
    }),
    [configWithRefinedExpressions, loadable.loading]
  );

  return final;
};

export const useConcreteConfig = (
  config: PlotConfig,
  stack: Stack,
  panelId: string
): {config: ConcretePlotConfig; loading: boolean} => {
  const lazyConfigElementsNode = useMemo(
    () =>
      opDict(
        LAZY_PATHS.reduce((acc, path) => {
          let elementNode = PlotState.getThroughArray(config, path.split('.'));
          if (_.isArray(elementNode)) {
            elementNode = opArray(
              elementNode.reduce((innerAcc, node, i) => {
                innerAcc[i] = node;
                return innerAcc;
              }, {} as any) as any
            );
          }
          if (elementNode == null) {
            elementNode = constNone();
          }
          acc[path] = elementNode;
          return acc;
        }, {} as any)
      ),
    [config]
  );

  const concreteConfigUse = LLReact.useNodeValue(lazyConfigElementsNode, {
    callSite: 'PanelPlot.concreteConfig.' + panelId,
  });
  const concreteConfigEvaluationResult = concreteConfigUse.result as
    | {[K in (typeof LAZY_PATHS)[number]]: any}
    | undefined;

  const concreteConfigLoading = concreteConfigUse.loading;

  return useMemo(() => {
    let loading: boolean = false;
    let newConfig: ConcretePlotConfig;
    if (concreteConfigLoading) {
      newConfig = PlotState.defaultConcretePlot(
        // Don't use the actual input.type here, defaultConcretePlot is expensive!
        // but we don't need a hydrated config in the loading case.
        constNode(list(typedDict({})), []),
        stack
      );
      loading = true;
    } else {
      // generate the new config with the concrete values obtained from the execution of the lazy paths
      newConfig = produce(config, draft => {
        LAZY_PATHS.forEach(path => {
          PlotState.setThroughArray(
            draft,
            path.split('.'),
            concreteConfigEvaluationResult![path],
            false
          );
        });
      }) as any;
    }

    return {config: newConfig, loading};
  }, [concreteConfigEvaluationResult, concreteConfigLoading, config, stack]);
};

export const ensureValidSignals = (
  config: ConcretePlotConfig
): ConcretePlotConfig => {
  // ensure that the domain is valid for the axis type
  return produce(config, draft =>
    ['x' as const, 'y' as const].forEach(axisName => {
      ['domain' as const, 'selection' as const].forEach(signalName => {
        if (
          !PlotState.isValidDomainForAxisType(
            draft.signals[signalName][axisName],
            PlotState.getAxisType(draft.series[0], axisName)
          )
        ) {
          draft.signals[signalName][axisName] = undefined;
        }
      });
    })
  );
};
