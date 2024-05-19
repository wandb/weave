import {EditingNode, Node, voidNode} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';

import {useWeaveContext} from '../../../context';
import {usePanelStacksForType} from '../availablePanels';
import {ChildPanelConfigComp} from '../ChildPanel';
import * as ConfigPanel from '../ConfigPanel';
import * as Panel2 from '../panel';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {PanelPlotProps} from '../PanelPlot/types';
import * as TableState from '../PanelTable/tableState';

export const inputType = {type: 'list' as const, objectType: 'any' as const};

interface FacetConfig {
  table: TableState.TableState;
  dims: {
    x: TableState.ColumnId;
    y: TableState.ColumnId;
    select: TableState.ColumnId;
    detail: TableState.ColumnId;
  };
  manualSize: boolean;
  padding: number;
  cellSize: {
    w: number;
    h: number;
  };
  selectedCell?: {
    x: string;
    y: string;
  };
  xAxisLabel: EditingNode;
  yAxisLabel: EditingNode;
}

export function defaultFacet(): FacetConfig {
  let tableState = TableState.emptyTable();
  tableState = TableState.appendEmptyColumn(tableState);
  const xColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const yColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const selectColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const detailColId = tableState.order[tableState.order.length - 1];

  tableState = {...tableState, groupBy: [xColId, yColId]};
  tableState = {
    ...tableState,
    sort: [
      {columnId: xColId, dir: 'asc'},
      {columnId: yColId, dir: 'asc'},
    ],
  };

  return {
    table: tableState,
    dims: {
      x: xColId,
      y: yColId,
      select: selectColId,
      detail: detailColId,
    },
    padding: 0,
    manualSize: false,
    cellSize: {
      w: 200,
      h: 20,
    },
    xAxisLabel: voidNode(),
    yAxisLabel: voidNode(),
  };
}

export const useConfig = (
  propsConfig: FacetConfig | undefined
): FacetConfig => {
  return useMemo(() => {
    if (
      propsConfig == null ||
      propsConfig.dims == null ||
      propsConfig.dims.select == null
    ) {
      return defaultFacet();
    }
    return propsConfig;
  }, [propsConfig]);
};

export type PanelFacetProps = Panel2.PanelProps<typeof inputType, FacetConfig>;

export const DimConfig: React.FC<{
  dimName: string;
  input: PanelPlotProps['input'];
  colId: TableState.ColumnId;
  // Hack: you can pass an extra colID to include in when grouping is
  // toggled for this dim. This is used to toggle grouping for color/label
  // together.
  extraGroupColId?: string;
  tableConfig: TableState.TableState;
  updateTableConfig: (newTableState: TableState.TableState) => void;
}> = props => {
  const weave = useWeaveContext();
  const {colId, tableConfig, input, updateTableConfig} = props;

  const inputNode = input;

  const updateDim = useCallback(
    (node: Node) => {
      updateTableConfig(
        TableState.updateColumnSelect(tableConfig, colId, node)
      );
    },
    [updateTableConfig, tableConfig, colId]
  );

  const {rowsNode} = useMemo(
    () => TableState.tableGetResultTableNode(tableConfig, inputNode, weave),
    [tableConfig, inputNode, weave]
  );
  const cellFrame = useMemo(
    () =>
      TableState.getCellFrame(
        inputNode,
        rowsNode,
        tableConfig.groupBy,
        tableConfig.columnSelectFunctions,
        colId
      ),
    [
      colId,
      inputNode,
      rowsNode,
      tableConfig.columnSelectFunctions,
      tableConfig.groupBy,
    ]
  );

  return (
    <PanelContextProvider newVars={cellFrame}>
      <ConfigPanel.ExpressionConfigField
        expr={tableConfig.columnSelectFunctions[colId]}
        setExpression={updateDim as any}
      />
    </PanelContextProvider>
  );
};
export const PanelFacetConfig: React.FC<PanelFacetProps> = props => {
  const {input, updateConfig: propsUpdateConfig, updateConfig2} = props;
  const weave = useWeaveContext();
  const {dashboardConfigOptions} = usePanelContext();
  const config = useConfig(props.config);
  const updateConfig = useCallback(
    (newConfig: Partial<FacetConfig>) => {
      propsUpdateConfig({
        ...config,
        ...newConfig,
      });
    },
    [config, propsUpdateConfig]
  );

  const tableConfig = config.table;
  const updateTableConfig = useCallback(
    (newTableConfig: TableState.TableState) =>
      updateConfig({
        table: newTableConfig,
      }),
    [updateConfig]
  );

  const updateAxisLabel = useCallback(
    (newAxisLabel: {xAxisLabel?: EditingNode; yAxisLabel?: EditingNode}) =>
      updateConfig({
        ...newAxisLabel,
      }),
    [updateConfig]
  );

  const cellSelectFunction =
    tableConfig.columnSelectFunctions[config.dims.select];
  const columnVars = useMemo(() => {
    const colVars = TableState.tableGetColumnVars(tableConfig, input, weave);
    return {
      ...colVars,
      facetItem: colVars.row,
    };
  }, [input, tableConfig, weave]);
  const cellPanel = tableConfig.columns[config.dims.select];
  const {stackIds: cellPanelStackOptions, curPanelId: curCellPanelId} =
    usePanelStacksForType(cellSelectFunction.type, cellPanel.panelId, {
      excludeTable: true,
    });
  console.log(
    'PANEL INFO',
    cellSelectFunction.type,
    cellPanel.panelId,
    cellPanelStackOptions,
    curCellPanelId
  );

  return (
    <ConfigPanel.ConfigSection label={`Properties`}>
      {dashboardConfigOptions}
      <ConfigPanel.ConfigOption label={'X-axis-label'}>
        <ConfigPanel.ExpressionConfigField
          expr={config.xAxisLabel}
          setExpression={exp => updateAxisLabel({xAxisLabel: exp})}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'X'}>
        <DimConfig
          dimName="x"
          colId={config.dims.x}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Y-axis label'}>
        <ConfigPanel.ExpressionConfigField
          expr={config.yAxisLabel}
          setExpression={exp => updateAxisLabel({yAxisLabel: exp})}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Y'}>
        <DimConfig
          dimName="y"
          colId={config.dims.y}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ChildConfigContainer>
        <PanelContextProvider newVars={columnVars}>
          <ChildPanelConfigComp
            pathEl="select"
            config={{
              vars: cellPanel.panelVars ?? {},
              input_node:
                config.table.columnSelectFunctions[config.dims.select],
              id: cellPanel.panelId,
              config: cellPanel.panelConfig,
            }}
            updateConfig={newChildPanelConfig => {
              let newTableConfig = TableState.updateColumnPanelConfig(
                tableConfig,
                config.dims.select,
                newChildPanelConfig.config
              );
              newTableConfig = TableState.updateColumnSelect(
                newTableConfig,
                config.dims.select,
                newChildPanelConfig.input_node
              );
              newTableConfig = TableState.updateColumnPanelId(
                newTableConfig,
                config.dims.select,
                newChildPanelConfig.id
              );
              updateTableConfig(newTableConfig);
            }}
            updateConfig2={change => {
              if (updateConfig2 != null) {
                updateConfig2(oldConfig => {
                  const mappedOldConfig = {
                    vars: {},
                    input_node:
                      oldConfig.table.columnSelectFunctions[
                        oldConfig.dims.select
                      ],
                    id: oldConfig.table.columns[oldConfig.dims.select].panelId,
                    config:
                      oldConfig.table.columns[oldConfig.dims.select]
                        .panelConfig,
                  };
                  const newChildPanelConfig = change(mappedOldConfig);
                  let newTConf = TableState.updateColumnPanelConfig(
                    oldConfig.table,
                    config.dims.select,
                    newChildPanelConfig.config
                  );
                  newTConf = TableState.updateColumnSelect(
                    newTConf,
                    config.dims.select,
                    newChildPanelConfig.input_node
                  );
                  newTConf = TableState.updateColumnPanelId(
                    newTConf,
                    config.dims.select,
                    newChildPanelConfig.id
                  );
                  return {table: newTConf};
                });
              }
            }}
          />
        </PanelContextProvider>
      </ConfigPanel.ChildConfigContainer>
    </ConfigPanel.ConfigSection>
  );
};
