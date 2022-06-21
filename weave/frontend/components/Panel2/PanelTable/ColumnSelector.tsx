import React, {useState, useCallback} from 'react';
import {Button, Grid, Icon, Input, List} from 'semantic-ui-react';
import {cloneDeep as _cloneDeep} from 'lodash';

import {fuzzyMatchWithMapping} from '@wandb/common/util/fuzzyMatch';
import LegacyWBIcon from '@wandb/common/components/elements/LegacyWBIcon';
import makeComp from '@wandb/common/util/profiler';

import {opPick, varNode, constString} from '@wandb/cg/browser/ops';

import ColumnSelectorField from './ColumnSelectorField';
import ColumnSelectorListContainer from './ColumnSelectorListContainer';
import * as Table from './tableState';
import {ColumnEntry} from './tableState';

const MAX_COLUMNS_SHOWN = 100;

interface ColumnSelectorProps {
  tableState: Table.TableState;
  allColumnNames: string[];

  update(state: Table.TableState): void;
}

const ColumnSelector: React.FC<ColumnSelectorProps> = makeComp(
  ({tableState, allColumnNames, update}) => {
    const [draggingColumn, setDraggingColumn] = useState<
      ColumnEntry | undefined
    >();
    const [visibleColumnListEl, setVisibleColumnListEl] =
      React.useState<HTMLDivElement | null>(null);

    const resetDraggingState = useCallback(() => {
      setDraggingColumn(undefined);
    }, []);

    const updateConfig: typeof update = useCallback(
      conf => {
        update(conf);
      },
      [update]
    );

    const dropField = useCallback(
      (dropColumn: ColumnEntry, visible: boolean) => {
        let conf = _cloneDeep(tableState);
        if (draggingColumn) {
          if (visible) {
            conf = Table.addColumns(conf, [draggingColumn]);
            conf = Table.moveBefore(conf, draggingColumn, dropColumn);
          } else {
            conf = Table.removeColumns(conf, [draggingColumn]);
          }
        }
        updateConfig(conf);
      },
      [tableState, draggingColumn, updateConfig]
    );

    const onContainerDrop = useCallback(
      (visible: boolean) => {
        let conf = _cloneDeep(tableState);
        if (draggingColumn) {
          if (visible) {
            conf = Table.addColumns(conf, [draggingColumn]);
            conf = Table.moveToEnd(conf, draggingColumn);
            window.setTimeout(() => {
              if (visibleColumnListEl) {
                visibleColumnListEl.scrollTo({
                  top: visibleColumnListEl.scrollHeight,
                });
              }
            });
          } else {
            conf = Table.removeColumns(conf, [draggingColumn]);
          }
        }
        updateConfig(conf);
      },
      [tableState, draggingColumn, updateConfig, visibleColumnListEl]
    );

    const addColumn = useCallback(
      (column: ColumnEntry) => {
        updateConfig(Table.addColumns(tableState, [column]));
      },
      [tableState, updateConfig]
    );

    const removeColumn = useCallback(
      (column: ColumnEntry) => {
        updateConfig(Table.removeColumns(tableState, [column]));
      },
      [tableState, updateConfig]
    );

    const addAll = useCallback(
      (hiddenColumns: ColumnEntry[]) => {
        updateConfig(Table.addColumns(tableState, hiddenColumns));
      },
      [tableState, updateConfig]
    );

    const removeAll = useCallback(
      (visibleColumns: ColumnEntry[]) => {
        updateConfig(Table.removeColumns(tableState, visibleColumns));
      },
      [tableState, updateConfig]
    );

    const [searchQuery, setSearch] = useState('');

    const getSearchMatches = (columns: ColumnEntry[]) =>
      fuzzyMatchWithMapping(columns, searchQuery, column => column.name);

    const usedColIds = new Set(tableState.order);
    const usedColNames = new Set(
      Object.entries(tableState.columns).reduce<string[]>(
        (memo, [colId, col]) => {
          const colOriginalKey = col.originalKey;
          if (colOriginalKey != null && usedColIds.has(colId)) {
            memo.push(colOriginalKey);
          }

          return memo;
        },
        []
      )
    );

    // TODO: These sets are complements; should use this to do in 1 pass
    const searchedColumnsAvailable = React.useMemo(
      () =>
        getSearchMatches(
          allColumnNames
            .filter(name => !usedColNames.has(name))
            .map(colName => ({
              name: colName,
              selectFn: opPick({
                obj: varNode('any', 'row') as any,
                key: constString(colName),
              }),
            }))
        ),
      [allColumnNames, usedColNames, searchQuery]
    );

    const searchedColumnsUsed = React.useMemo(
      () =>
        getSearchMatches(
          tableState.order.map(colId => ({
            name: Table.getTableColumnName(
              tableState.columnNames,
              tableState.columnSelectFunctions,
              colId
            ),
            id: colId,
          }))
        ).sort((a, b) =>
          tableState.groupBy.includes(b.id!)
            ? 1
            : 0 - (tableState.groupBy.includes(a.id!) ? 1 : 0)
        ),
      [
        tableState.order,
        tableState.columns,
        tableState.columnNames,
        tableState.columnSelectFunctions,
        searchQuery,
      ]
    );

    return (
      <Grid className="table-editor">
        {allColumnNames.length > Table.COLUMN_LIMIT && (
          <Grid.Row>
            <Grid.Column>
              <div style={{fontStyle: 'italic'}}>
                <Icon name="warning sign" style={{marginRight: '5px'}} />
                {`Showing more than ${Table.COLUMN_LIMIT} columns may affect responsiveness.`}
              </div>
            </Grid.Column>
          </Grid.Row>
        )}
        <Grid.Row>
          <Grid.Column>
            <Input
              className="table-editor__search"
              icon="search"
              placeholder={`Search columns`}
              loading={false}
              onChange={(e, {value}) => setSearch(value)}
            />
          </Grid.Column>
        </Grid.Row>
        <Grid.Row>
          <Grid.Column width={8}>
            <ColumnSelectorListContainer
              visibleColumns={false}
              onDrop={() => onContainerDrop(false)}>
              <h5>
                Available Columns
                <span className="count-tag">
                  {searchedColumnsAvailable.length}
                </span>
              </h5>
              <div className="items-scroll-list">
                {searchedColumnsAvailable.slice(0, 100).map(column => {
                  return (
                    <ColumnSelectorField
                      key={column.name}
                      disabled={false}
                      colName={column.name}
                      colId={column.id}
                      config={tableState}
                      onDragStart={(e: React.DragEvent) => {
                        e.dataTransfer.setData('text', ''); // this is necessary for drag+drop to work in firefox
                        setDraggingColumn(column);
                      }}
                      onDragEnd={() => resetDraggingState}
                      onDrop={dropColumn => dropField(dropColumn, false)}
                      dragging={column === draggingColumn}
                      searchQuery={searchQuery}
                      onClick={() => addColumn(column)}
                    />
                  );
                })}
                {searchedColumnsAvailable.length >= MAX_COLUMNS_SHOWN && (
                  <List.Item className="hint-text">{`Limited to ${MAX_COLUMNS_SHOWN} results. Use search to find other columns.`}</List.Item>
                )}
              </div>
              <Button
                className="right tiny wb-icon-button"
                onClick={() => addAll(searchedColumnsAvailable)}>
                <LegacyWBIcon name="next" />
                Add all
              </Button>
            </ColumnSelectorListContainer>
          </Grid.Column>
          <Grid.Column width={8}>
            <ColumnSelectorListContainer
              visibleColumns={true}
              onDrop={() => onContainerDrop(true)}>
              <h5>
                Displayed Columns
                <span className="count-tag">{searchedColumnsUsed.length}</span>
                {tableState.order.length === Table.COLUMN_LIMIT && (
                  <span className="column-limit-msg">Column limit reached</span>
                )}
              </h5>
              <div
                className="items-scroll-list"
                ref={node => setVisibleColumnListEl(node)}>
                {searchedColumnsUsed.slice(0, 100).map((column, i) => {
                  return (
                    <ColumnSelectorField
                      key={i}
                      disabled={false}
                      colName={column.name}
                      colId={column.id}
                      icon={
                        tableState.columns[column.id!].originalKey == null
                          ? 'sparkles'
                          : tableState.groupBy.includes(column.id!)
                          ? 'group'
                          : 'metadata'
                      }
                      config={tableState}
                      onDragStart={(e: React.DragEvent) => {
                        e.dataTransfer.setData('text', ''); // this is necessary for drag+drop to work in firefox
                        setDraggingColumn(column);
                      }}
                      onDragEnd={() => resetDraggingState}
                      onDrop={dropColumn => dropField(dropColumn, true)}
                      dragging={column === draggingColumn}
                      searchQuery={searchQuery}
                      onClick={() => removeColumn(column)}
                    />
                  );
                })}
                {searchedColumnsUsed.length >= MAX_COLUMNS_SHOWN && (
                  <List.Item className="hint-text">{`Limited to ${MAX_COLUMNS_SHOWN} results. Use search to find other columns.`}</List.Item>
                )}
              </div>
              <Button
                className="tiny wb-icon-button"
                onClick={() => removeAll(searchedColumnsUsed)}>
                <LegacyWBIcon name="previous" />
                Remove all
              </Button>
            </ColumnSelectorListContainer>
          </Grid.Column>
        </Grid.Row>
      </Grid>
    );
  },
  {id: 'ColumnSelector', memo: true}
);

export default ColumnSelector;
