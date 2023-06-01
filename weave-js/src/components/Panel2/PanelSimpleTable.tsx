import {constString, Node, opGroupGroupKey, opPick} from '@wandb/weave/core';
import React, {useMemo} from 'react';
import {Table as STable} from 'semantic-ui-react';

import {useWeaveContext} from '../../context';
import {useGatedValue} from '../../hookUtils';
import * as LLReact from '../../react';
import * as Panel2 from './panel';
import {Cell, Value} from './PanelTable/Cell';
import * as Table from './PanelTable/tableState';

const inputType = {type: 'list' as const, objectType: 'any' as const};

type PanelTable = Panel2.PanelProps<typeof inputType, Table.TableState>;

const PanelSimpleTable: React.FC<PanelTable> = props => {
  const weave = useWeaveContext();
  const {input, updateConfig, updateContext} = props;

  const inputNode = input as any as Node;

  const config = useMemo(
    () =>
      props.config == null || props.config.columns == null
        ? Table.emptyTable()
        : props.config,
    [props.config]
  );

  const rowsNode = useMemo(
    () =>
      Table.getRowsNode(
        config.preFilterFunction,
        config.groupBy,
        config.columnSelectFunctions,
        config.columnNames,
        config.order,
        config.sort,
        inputNode,
        weave
      ),
    [
      config.preFilterFunction,
      config.groupBy,
      config.columnSelectFunctions,
      config.columnNames,
      config.order,
      config.sort,
      inputNode,
      weave,
    ]
  );

  const visibleRowsNode = useMemo(
    () => Table.getPagedRowsNode(config.pageSize, config.page, rowsNode),
    [config.pageSize, config.page, rowsNode]
  );

  const rowNodesUse = LLReact.useEach(visibleRowsNode as any, config.pageSize);

  const rowNodes = useMemo(
    () => (rowNodesUse.loading ? [] : rowNodesUse.result),
    [rowNodesUse.loading, rowNodesUse.result]
  );

  // Only rerender this when not loading
  return useGatedValue(
    <div style={{width: '100%', height: '100%', overflow: 'auto'}}>
      <STable>
        <STable.Body>
          {rowNodes.map((row, rowIndex) => (
            <STable.Row key={rowIndex}>
              {config.groupBy.length > 0 &&
                config.groupBy.map((groupColId, i) => (
                  <STable.Cell
                    // override a style that we set in semantic that shouldn't apply here
                    // .file-browser td {max-width}
                    style={{maxWidth: 'none'}}
                    key={`group-col-${i}`}>
                    <Value
                      table={config}
                      colId={groupColId}
                      // Warning: not memoized
                      valueNode={opPick({
                        obj: opGroupGroupKey({
                          obj: rowNodesUse.result[rowIndex] as any,
                        }),
                        key: constString(
                          Table.getTableColumnName(
                            config.columnNames,
                            config.columnSelectFunctions,
                            groupColId,
                            weave.client.opStore
                          )
                        ),
                      })}
                      config={{}}
                      updateTableState={props.updateConfig}
                      panelContext={props.context}
                      updatePanelContext={updateContext}
                    />
                  </STable.Cell>
                ))}
              {Table.getColumnRenderOrder(config).map(colId => (
                <STable.Cell
                  // override a style that we set in semantic that shouldn't apply here
                  // .file-browser td {max-width}
                  style={{maxWidth: 'none'}}
                  key={colId}>
                  <Cell
                    table={config}
                    colId={colId}
                    inputNode={inputNode}
                    rowNode={row}
                    selectFunction={config.columnSelectFunctions[colId]}
                    panelId={config.columns[colId].panelId}
                    config={config.columns[colId].panelConfig}
                    panelContext={props.context}
                    updateTableState={updateConfig}
                    updatePanelContext={updateContext}
                  />
                </STable.Cell>
              ))}
            </STable.Row>
          ))}
        </STable.Body>
      </STable>
    </div>,
    o => !rowNodesUse.loading
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'simple-table',
  Component: PanelSimpleTable,
  inputType,
};
