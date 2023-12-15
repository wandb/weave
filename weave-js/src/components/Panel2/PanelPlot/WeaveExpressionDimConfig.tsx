import {Node} from '@wandb/weave/core';
import {produce} from 'immer';
import {useCallback, useMemo} from 'react';
import React from 'react';

import {useWeaveContext} from '../../../context';
import * as ConfigPanel from '../ConfigPanel';
import {PanelContextProvider} from '../PanelContext';
import * as TableState from '../PanelTable/tableState';
import {ExpressionDimName} from './plotState';
import {PanelPlotProps} from './types';
import {PlotConfig, SeriesConfig} from './versions';

export const WeaveExpressionDimConfig: React.FC<{
  dimName: ExpressionDimName;
  input: PanelPlotProps['input'];
  series: SeriesConfig[];
  config: PlotConfig;
  updateConfig: PanelPlotProps['updateConfig'];
}> = props => {
  const {config, input, updateConfig, series} = props;

  const seriesIndices = useMemo(
    () => series.map(s => config.series.indexOf(s)),
    [series, config.series]
  );
  const updateDims = useCallback(
    (node: Node) => {
      const newConfig = produce(config, draft => {
        seriesIndices.forEach(i => {
          const s = draft.series[i];
          s.table = TableState.updateColumnSelect(
            s.table,
            s.dims[props.dimName],
            node
          );
        });
      });
      updateConfig(newConfig);
    },
    [config, props.dimName, seriesIndices, updateConfig]
  );
  const weave = useWeaveContext();

  const tableConfigs = useMemo(() => series.map(s => s.table), [series]);
  const rowsNodes = useMemo(() => {
    return series.map(
      s => TableState.tableGetResultTableNode(s.table, input, weave).rowsNode
    );
  }, [series, input, weave]);
  const colIds = useMemo(
    () => series.map(s => s.dims[props.dimName]),
    [series, props.dimName]
  );

  const cellFrames = useMemo(
    () =>
      rowsNodes.map((rowsNode, i) => {
        const tableState = tableConfigs[i];
        const colId = colIds[i];
        return TableState.getCellFrame(
          input,
          rowsNode,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          colId
        );
      }),
    [rowsNodes, input, tableConfigs, colIds]
  );

  return (
    <PanelContextProvider newVars={cellFrames[0]}>
      <ConfigPanel.ExpressionConfigField
        expr={tableConfigs[0].columnSelectFunctions[colIds[0]]}
        setExpression={updateDims as any}
      />
    </PanelContextProvider>
  );
};
