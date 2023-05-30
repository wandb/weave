import {WBIcon} from '@wandb/ui';
import React, {useCallback, useMemo, useState} from 'react';

import {WeaveExpression} from '../../panel/WeaveExpression';
import {ControlFilter} from './ControlFilter';
import * as Panel from './panel';
import {PanelContextProvider} from './PanelContext';
import * as Table from './PanelTable/tableState';
import {useUpdateConfigKey} from './PanelTable/util';
import {useWeaveContext} from '@wandb/weave/context';
import {TableState} from '../..';
import * as ConfigPanel from './ConfigPanel';
import {DimConfig} from './PanelFacet/common';
import * as CGReact from '../../react';
import {Checkbox} from 'semantic-ui-react';

const inputType = {type: 'list' as const, objectType: 'any' as const};
interface PanelQueryConfig {
  tableState: Table.TableState;
  pinnedRows: {[groupKey: string]: number[]};
  dims: {
    text: TableState.ColumnId;
  };
}
type PanelQueryProps = Panel.PanelProps<typeof inputType, PanelQueryConfig>;

export function defaultPanelQuery(): PanelQueryConfig {
  let tableState = TableState.emptyTable();
  tableState = TableState.appendEmptyColumn(tableState);
  const textColId = tableState.order[tableState.order.length - 1];
  const columnNames = {[textColId]: 'text'};
  tableState = {...tableState, columnNames};
  console.log('TABLE STATE', tableState);

  return {
    tableState,
    pinnedRows: {},
    dims: {
      text: textColId,
    },
  };
}

export const PanelQueryConfigComponent: React.FC<PanelQueryProps> = props => {
  const {input, updateConfig: propsUpdateConfig} = props;
  const config = props.config!;
  const updateConfig = useCallback(
    (newConfig: Partial<PanelQueryConfig>) => {
      propsUpdateConfig({
        ...config,
        ...newConfig,
      });
    },
    [config, propsUpdateConfig]
  );

  const tableConfig = config.tableState;
  const updateTableConfig = useCallback(
    (newTableConfig: TableState.TableState) =>
      updateConfig({
        tableState: newTableConfig,
      }),
    [updateConfig]
  );

  return (
    <div>
      <ConfigPanel.ConfigOption label={'text'}>
        <DimConfig
          dimName="text"
          colId={config.dims.text}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
    </div>
  );
};

export const PanelQuery: React.FC<PanelQueryProps> = props => {
  const {updateConfig} = props;
  const config = props.config!;
  const weave = useWeaveContext();
  const tableState = useMemo(() => {
    return config?.tableState ?? Table.emptyTable();
  }, [config?.tableState]);

  const preFilterFrame = useMemo(
    () => Table.getRowFrame(props.input),
    [props.input]
  );
  const updateTableState = useUpdateConfigKey('tableState', updateConfig);

  const setFilterFunction: React.ComponentProps<
    typeof ControlFilter
  >['setFilterFunction'] = useCallback(
    newNode => {
      return updateTableState(Table.updatePreFilter(tableState, newNode));
    },
    [tableState, updateTableState]
  );
  const [pageNum, setPageNum] = useState(0);
  const {pageSize} = tableState;
  const visibleRowsNode = useMemo(() => {
    const rowsNode = Table.getRowsNode(
      tableState.preFilterFunction,
      tableState.groupBy,
      tableState.columnSelectFunctions,
      tableState.columnNames,
      tableState.order,
      tableState.sort,
      props.input,
      weave
    );
    return Table.getPagedRowsNode(pageSize, pageNum, rowsNode);
  }, [
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    props.input,
    weave,
    pageSize,
    pageNum,
  ]);
  const resultNode = useMemo(() => {
    return Table.getResultTableNode(
      visibleRowsNode,
      tableState.columnSelectFunctions,
      tableState.columnNames,
      tableState.groupBy,
      tableState.order,
      weave.client.opStore
    );
  }, [
    visibleRowsNode,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.groupBy,
    tableState.order,
    weave.client.opStore,
  ]);
  console.log('RESULT NODE', resultNode);
  const nodeValueQuery = CGReact.useNodeValue(resultNode);
  console.log('NVQ', nodeValueQuery);
  const groupingId = '';
  const selectedRows = useMemo(
    () => config.pinnedRows?.[groupingId] ?? [],
    [config.pinnedRows]
  );

  const rowItems = useMemo(() => {
    const itemLabels: Array<{text: string}> = nodeValueQuery.result ?? [];
    return itemLabels.map((item, i) => ({
      text: item.text,
      rowIndex: i + pageNum,
      checked: selectedRows.includes(i + pageNum),
    }));
  }, [nodeValueQuery.result, pageNum, selectedRows]);

  const toggleRow = useCallback(
    (rowIndex: number) => {
      const newSelectedRows = [...selectedRows];
      const index = newSelectedRows.indexOf(rowIndex);
      if (index === -1) {
        newSelectedRows.push(rowIndex);
      } else {
        newSelectedRows.splice(index, 1);
      }
      updateConfig({
        pinnedRows: {
          ...config.pinnedRows,
          [groupingId]: newSelectedRows,
        },
      });
    },
    [config.pinnedRows, groupingId, selectedRows, updateConfig]
  );

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        // flex: '1 1 auto',
        paddingLeft: '12px',
        paddingBottom: '5px',
      }}
    >
      <div style={{display: 'flex'}}>
        <div style={{marginRight: 8}}>
          <WBIcon name="filter" />
        </div>
        <div style={{flexGrow: 1, marginTop: 2}}>
          <PanelContextProvider newVars={preFilterFrame}>
            <WeaveExpression
              noBox
              expr={tableState.preFilterFunction}
              setExpression={setFilterFunction}
            />
          </PanelContextProvider>
        </div>
      </div>
      <div style={{marginLeft: 16}}>
        {rowItems.map((item, i) => (
          <div key={i} style={{display: 'flex', alignItems: 'center'}}>
            <Checkbox
              checked={item.checked}
              onChange={e => toggleRow(item.rowIndex)}
              style={{marginRight: 8}}
            />
            {item.text}
          </div>
        ))}
      </div>
    </div>
  );
};

export const Spec: Panel.PanelSpec = {
  hidden: true,
  id: 'Query',
  initialize: defaultPanelQuery,
  ConfigComponent: PanelQueryConfigComponent,
  Component: PanelQuery,
  inputType,
};
