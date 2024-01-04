import {WBMenuOption, WBPopupMenuTrigger} from '@wandb/ui';
import EditableField from '@wandb/weave/common/components/EditableField';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import {INPUT_SLIDER_CLASS} from '@wandb/weave/common/components/elements/SliderInput';
import * as SemanticHacks from '@wandb/weave/common/util/semanticHacks';
import {
  canGroupType,
  canSortType,
  constFunction,
  EditingNode,
  isListLike,
  isVoidNode,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opCount,
  voidNode,
} from '@wandb/weave/core';
import {TableState} from '@wandb/weave/index';
import React, {useCallback, useMemo, useState} from 'react';
import {Popup} from 'semantic-ui-react';

import {useWeaveContext} from '../../../context';
import {focusEditor, WeaveExpression} from '../../../panel/WeaveExpression';
import {SUGGESTION_OPTION_CLASS} from '../../../panel/WeaveExpression/styles';
import {Button} from '../../Button';
import {Tooltip} from '../../Tooltip';
import {usePanelStacksForType} from '../availablePanels';
import * as ExpressionView from '../ExpressionView';
import {PanelComp2} from '../PanelComp';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as S from '../PanelTable.styles';
import * as Table from './tableState';
import {stripTag} from './util';

const recordEvent = makeEventRecorder('Table');

const STYLE_POPUP_CLASS = 'control-box-popup';

const makeMenuItemDivider = (value: string) => {
  return {
    value,
    disabled: true,
    render: () => (
      <div
        style={{
          marginRight: 12,
          marginLeft: 12,
          borderBottom: '1px solid #888',
        }}
      />
    ),
  };
};

const makeSortingMenuItems = (
  tableState: Table.TableState,
  colId: string,
  updateTableState: (newTableState: Table.TableState) => void
) => {
  const colSortState = tableState.sort.find(
    sort => sort.columnId === colId
  )?.dir;
  const menuItems: WBMenuOption[] = [makeMenuItemDivider('sort-div')];
  if (colSortState !== 'asc') {
    menuItems.push({
      value: 'sort-asc',
      name: 'Sort Asc',
      icon: 'up-arrow',
      onSelect: async () => {
        recordEvent('UPDATE_COLUMN_SORT_ASC');
        const newTableState = Table.enableSortByCol(
          Table.disableSort(tableState),
          colId,
          true
        );
        updateTableState(newTableState);
      },
    });
  }

  if (colSortState !== undefined) {
    menuItems.push({
      value: 'sort-remove',
      name: 'Remove Sort',
      icon: 'delete',
      onSelect: async () => {
        recordEvent('REMOVE_COLUMN_SORT');
        const newTableState = Table.disableSortByCol(tableState, colId);
        updateTableState(newTableState);
      },
    });
  }

  if (colSortState !== 'desc') {
    menuItems.push({
      value: 'sort-desc',
      name: 'Sort Desc',
      icon: 'down-arrow',
      onSelect: async () => {
        recordEvent('UPDATE_COLUMN_SORT_DESC');
        const newTableState = Table.enableSortByCol(
          Table.disableSort(tableState),
          colId,
          false
        );
        updateTableState(newTableState);
      },
    });
  }

  return menuItems;
};

export const ColumnHeader: React.FC<{
  isGroupCol: boolean;
  tableState: Table.TableState;
  inputArrayNode: Node;
  rowsNode: Node;
  columnName: string;
  selectFunction: NodeOrVoidNode;
  colId: string;
  panelId: string;
  config: any;
  panelContext: any;
  isPinned: boolean;
  simpleTable?: boolean;
  countColumnId: string | null;
  setCountColumnId: React.Dispatch<React.SetStateAction<string | null>>;
  updatePanelContext(newContext: any): void;
  updateTableState(newTableState: Table.TableState): void;
  setColumnPinState(pin: boolean): void;
}> = ({
  isGroupCol,
  tableState,
  inputArrayNode,
  rowsNode,
  columnName: propsColumnName,
  selectFunction: propsSelectFunction,
  colId,
  panelId: propsPanelId,
  config: propsPanelConfig,
  panelContext,
  updatePanelContext,
  updateTableState,
  isPinned,
  setColumnPinState,
  simpleTable,
  countColumnId,
  setCountColumnId,
}) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();

  const [columnSettingsOpen, setColumnSettingsOpen] = useState(false);

  const [workingSelectFunction, setWorkingSelectFunction] =
    useState<EditingNode>(propsSelectFunction);
  const [workingColumnName, setWorkingColumnName] =
    useState<string>(propsColumnName);
  const [workingPanelId, setWorkingPanelId] = useState<string>(propsPanelId);
  const [workingPanelConfig, setWorkingPanelConfig] =
    useState<any>(propsPanelConfig);
  const enableGroup = Table.enableGroupByCol;
  const disableGroup = Table.disableGroupByCol;
  const isGroupCountColumn = colId === 'groupCount';

  const applyWorkingState = useCallback(() => {
    let newState = tableState;
    if (workingColumnName !== propsColumnName) {
      recordEvent('UPDATE_COLUMN_NAME');
      newState = Table.updateColumnName(newState, colId, workingColumnName);
    }
    if (
      weave.nodeIsExecutable(workingSelectFunction) &&
      workingSelectFunction.type !== 'invalid'
    ) {
      let panelUpdated = false;
      if (workingSelectFunction !== propsSelectFunction) {
        newState = Table.updateColumnSelect(
          newState,
          colId,
          workingSelectFunction
        );
        panelUpdated = true;
      }

      if (workingPanelId !== propsPanelId) {
        newState = Table.updateColumnPanelId(newState, colId, workingPanelId);
        panelUpdated = true;
      }

      if (workingPanelConfig !== propsPanelConfig) {
        newState = Table.updateColumnPanelConfig(
          newState,
          colId,
          workingPanelConfig
        );
        panelUpdated = true;
      }

      if (panelUpdated) {
        recordEvent('UPDATE_COLUMN_PANEL');
      }
    }

    if (newState !== tableState) {
      updateTableState(newState);
    }
  }, [
    tableState,
    colId,
    workingColumnName,
    workingSelectFunction,
    workingPanelId,
    workingPanelConfig,
    updateTableState,
    propsColumnName,
    propsPanelConfig,
    propsPanelId,
    propsSelectFunction,
    weave,
  ]);

  const openColumnSettings = useCallback(() => {
    setColumnSettingsOpen(true);
    // Copy props in to editing function in case props version
    // has changed externally.
    setWorkingSelectFunction(propsSelectFunction);
    setWorkingColumnName(propsColumnName);
    setWorkingPanelId(propsPanelId);
    setWorkingPanelConfig(propsPanelConfig);
  }, [propsSelectFunction, propsColumnName, propsPanelId, propsPanelConfig]);

  const cellFrame = useMemo(
    () =>
      Table.getCellFrame(
        inputArrayNode,
        rowsNode,
        tableState.groupBy,
        tableState.columnSelectFunctions,
        colId
      ),
    [
      colId,
      inputArrayNode,
      rowsNode,
      tableState.columnSelectFunctions,
      tableState.groupBy,
    ]
  );
  const doUngroup = useCallback(async () => {
    let newTableState: Table.TableState | null = null;
    const countColumnExists = Object.keys(tableState.columnNames).includes(
      'groupCount'
    );
    if (countColumnId && !countColumnExists) {
      setCountColumnId(null);
    }
    if (countColumnId && countColumnExists && tableState.groupBy.length === 1) {
      newTableState = Table.removeColumn(tableState, countColumnId);
      setCountColumnId(null);
    }
    newTableState = await disableGroup(
      newTableState ?? tableState,
      colId,
      inputArrayNode,
      weave,
      stack
    );
    recordEvent('UNGROUP');
    updateTableState(newTableState);
  }, [
    countColumnId,
    setCountColumnId,
    disableGroup,
    tableState,
    colId,
    inputArrayNode,
    weave,
    stack,
    updateTableState,
  ]);

  const selectedNode = useMemo(
    () =>
      // Only use selected node if it's executable (has no voids...)
      // otherwise fall back to the props version.
      // TODO: this isn't really right
      weave.nodeIsExecutable(workingSelectFunction) &&
      !isVoidNode(cellFrame.row)
        ? Table.getCellValueNode(weave, cellFrame.row, workingSelectFunction)
        : voidNode(),
    [cellFrame.row, workingSelectFunction, weave]
  );
  const {
    handler,
    stackIds,
    curPanelId: workingCurPanelId,
  } = usePanelStacksForType(workingSelectFunction.type, workingPanelId, {
    excludeTable: true,
    excludePlot: true,
    disallowedPanels: ['Group', 'Expression'],
  });

  let columnTypeForGroupByChecks = stripTag(workingSelectFunction.type);
  if (!isGroupCol) {
    /*
      Once one column is grouped, the other non-grouped columns are all typed as
      lists. So we need to figure out the inner types of the non-grouped columns.
      */
    columnTypeForGroupByChecks = isListLike(columnTypeForGroupByChecks)
      ? stripTag(listObjectType(workingSelectFunction.type))
      : columnTypeForGroupByChecks;
  }

  const columnMenuItems: WBMenuOption[] = useMemo(() => {
    let menuItems: WBMenuOption[] = [];
    menuItems.push({
      value: 'settings',
      name: 'Column settings',
      icon: 'configuration',
      onSelect: () => openColumnSettings(),
    });
    if (
      !isGroupCol &&
      !isGroupCountColumn &&
      canGroupType(columnTypeForGroupByChecks)
    ) {
      menuItems.push({
        value: 'group',
        name: 'Group by',
        icon: 'group-runs',
        onSelect: async () => {
          recordEvent('GROUP');
          let newTableState: Table.TableState | null = null;
          if (countColumnId == null) {
            const {table, columnId} = Table.addColumnToTable(
              tableState,
              constFunction(
                {
                  row: {
                    type: 'list',
                    objectType: 'any',
                  },
                },
                ({row}) => {
                  return opCount({arr: row});
                }
              ).val,
              'groupCount'
            );
            newTableState = table;
            setCountColumnId(columnId);
          }
          newTableState = await enableGroup(
            newTableState ?? tableState,
            colId,
            inputArrayNode,
            weave,
            stack
          );
          updateTableState(newTableState);
        },
      });
    } else if (isGroupCol) {
      menuItems.push({
        value: 'ungroup',
        name: 'Ungroup',
        icon: 'group-runs',
        onSelect: doUngroup,
      });
    }
    if (canSortType(workingSelectFunction.type)) {
      menuItems = menuItems.concat(
        makeSortingMenuItems(tableState, colId, updateTableState)
      );
    }
    if (!isGroupCol) {
      if (menuItems.length > 0) {
        menuItems.push(makeMenuItemDivider('insert-div'));
      }
      menuItems = menuItems.concat([
        {
          value: 'insert-right',
          name: 'Insert 1 right',
          icon: 'next',
          onSelect: () => {
            const newTableState = Table.insertColumnRight(
              tableState,
              colId,
              inputArrayNode,
              weave
            );
            recordEvent('INSERT_COLUMN');
            updateTableState(newTableState);
          },
        },
        {
          value: 'insert-left',
          name: 'Insert 1 left',
          icon: 'previous',
          onSelect: () => {
            const newTableState = Table.insertColumnLeft(
              tableState,
              colId,
              inputArrayNode,
              weave
            );
            recordEvent('INSERT_COLUMN');
            updateTableState(newTableState);
          },
        },
        makeMenuItemDivider('pin-div'),
        {
          value: 'pin',
          name: isPinned ? 'Unpin' : 'Pin',
          icon: 'pin',
          onSelect: () => {
            recordEvent('PIN_COLUMN');
            setColumnPinState(!isPinned);
          },
        },
        makeMenuItemDivider('remove-div'),
        {
          value: 'remove',
          name: 'Remove',
          icon: 'delete',
          onSelect: () => {
            const newTableState = Table.removeColumn(tableState, colId);
            recordEvent('REMOVE_COLUMN');
            updateTableState(newTableState);
          },
        },
        {
          value: 'remove-all-right',
          name: 'Remove all right',
          icon: 'next',
          onSelect: () => {
            const newTableState = Table.removeColumnsToRight(tableState, colId);
            recordEvent('REMOVE_COLUMNS_TO_RIGHT');
            updateTableState(newTableState);
          },
        },
        {
          value: 'remove-all-left',
          name: 'Remove all left',
          icon: 'previous',
          onSelect: () => {
            const newTableState = Table.removeColumnsToLeft(tableState, colId);
            recordEvent('REMOVE_COLUMNS_TO_LEFT');
            updateTableState(newTableState);
          },
        },
      ]);
    }
    return menuItems;
  }, [
    countColumnId,
    setCountColumnId,
    isGroupCol,
    columnTypeForGroupByChecks,
    workingSelectFunction.type,
    openColumnSettings,
    enableGroup,
    tableState,
    colId,
    inputArrayNode,
    weave,
    stack,
    updateTableState,
    doUngroup,
    isPinned,
    setColumnPinState,
    isGroupCountColumn,
  ]);

  const colIsSorted =
    tableState.sort.find(sort => sort.columnId === colId)?.dir != null;

  const colControlsWidth =
    20 * (1 + (colIsSorted ? 1 : 0) + (isPinned ? 1 : 0));

  const newContextVars = useMemo(() => {
    // TODO mixing up propsSelectFunction and
    // selectFunction
    return {
      ...cellFrame,
      domain: weave.callFunction(propsSelectFunction, {
        row: inputArrayNode,
      }),
      row: cellFrame.row,
    };
  }, [cellFrame, weave, propsSelectFunction, inputArrayNode]);

  return (
    <S.ColumnHeader data-test="column-header">
      {simpleTable ? (
        workingColumnName !== '' ? (
          <S.ColumnNameText>{workingColumnName}</S.ColumnNameText>
        ) : (
          <ExpressionView.ExpressionView
            frame={cellFrame}
            node={workingSelectFunction}
          />
        )
      ) : (
        <Popup
          basic
          className="wb-table-action-popup"
          on="click"
          open={columnSettingsOpen}
          position="bottom left"
          onOpen={openColumnSettings}
          onClose={(event, data) => {
            const nestedPopupSelector = [
              INPUT_SLIDER_CLASS,
              STYLE_POPUP_CLASS,
              SUGGESTION_OPTION_CLASS,
            ]
              .map(c => '.' + c)
              .join(', ');

            const inPopup =
              (event.target as HTMLElement).closest(nestedPopupSelector) !=
              null;

            if (!inPopup) {
              SemanticHacks.withIgnoreBlockedClicks(() => {
                applyWorkingState();
                setColumnSettingsOpen(false);
              })(event, data);
            }
          }}
          trigger={
            <S.ColumnName
              style={{
                marginRight: `-${colControlsWidth}px`,
              }}
              onClick={() => setColumnSettingsOpen(!columnSettingsOpen)}>
              {propsColumnName !== '' ? (
                <S.ColumnNameText>{propsColumnName}</S.ColumnNameText>
              ) : (
                <ExpressionView.ExpressionView
                  frame={cellFrame}
                  node={propsSelectFunction}
                />
              )}
            </S.ColumnName>
          }
          content={
            columnSettingsOpen && (
              <div>
                <Tooltip
                  // Button's built-in tooltip attribute won't position properly with custom wrapper style.
                  trigger={
                    <Button
                      variant="ghost"
                      icon="close"
                      size="small"
                      twWrapperStyles={{position: 'absolute', right: 8}}
                      onClick={() => setColumnSettingsOpen(false)}
                    />
                  }
                  content="Discard changes"
                />
                <S.ColumnEditorSection>
                  <S.ColumnEditorSectionLabel>
                    Cell expression
                  </S.ColumnEditorSectionLabel>
                  <S.AssignmentWrapper>
                    <div style={{width: '100%'}}>
                      <PanelContextProvider newVars={cellFrame}>
                        <WeaveExpression
                          expr={workingSelectFunction}
                          setExpression={setWorkingSelectFunction}
                          onMount={focusEditor}
                          liveUpdate
                        />
                      </PanelContextProvider>
                    </div>
                  </S.AssignmentWrapper>
                  <S.ColumnEditorColumnName>
                    <S.ColumnEditorFieldLabel>
                      Column name:
                    </S.ColumnEditorFieldLabel>
                    <EditableField
                      value={workingColumnName}
                      placeholder={ExpressionView.simpleNodeString(
                        workingSelectFunction,
                        weave.client.opStore
                      )}
                      save={setWorkingColumnName}
                    />
                  </S.ColumnEditorColumnName>
                </S.ColumnEditorSection>
                <S.ColumnEditorSection>
                  <S.ColumnEditorSectionLabel>Panel</S.ColumnEditorSectionLabel>
                  <S.PanelNameEditor>
                    <ModifiedDropdown
                      selection
                      search
                      options={stackIds.map(si => ({
                        text: si.displayName,
                        value: si.id,
                      }))}
                      value={workingCurPanelId}
                      onChange={(e, {value}) =>
                        setWorkingPanelId(value as string)
                      }
                    />
                  </S.PanelNameEditor>
                  {propsSelectFunction.nodeType !== 'void' &&
                    selectedNode.nodeType !== 'void' &&
                    handler != null && (
                      <S.PanelSettings>
                        <PanelContextProvider newVars={newContextVars}>
                          <PanelComp2
                            input={selectedNode}
                            inputType={workingSelectFunction.type}
                            loading={false}
                            panelSpec={handler}
                            configMode={true}
                            context={panelContext}
                            config={workingPanelConfig}
                            updateConfig={config =>
                              setWorkingPanelConfig({
                                ...workingPanelConfig,
                                ...config,
                              })
                            }
                            updateContext={updatePanelContext}
                          />
                        </PanelContextProvider>
                      </S.PanelSettings>
                    )}
                </S.ColumnEditorSection>
              </div>
            )
          }
        />
      )}
      {!simpleTable && (
        <WBPopupMenuTrigger options={columnMenuItems}>
          {({anchorRef, setOpen, open}) => (
            <S.ColumnAction className="column-controls">
              {isPinned && (
                <PinnedIndicator unpin={() => setColumnPinState(false)} />
              )}
              {isGroupCol && (
                <S.ControlIcon
                  name="group-runs"
                  onClick={e => {
                    recordEvent('REMOVE_COLUMN_GROUPING');
                    doUngroup();
                  }}
                />
              )}
              {colIsSorted && (
                <SortStateToggle
                  {...{
                    tableState,
                    colId,
                    updateTableState,
                  }}
                />
              )}
              <S.EllipsisIcon
                ref={anchorRef}
                data-test="column-options"
                name="overflow"
                className="column-actions-trigger"
                onClick={() => setOpen(o => !o)}
              />
            </S.ColumnAction>
          )}
        </WBPopupMenuTrigger>
      )}
    </S.ColumnHeader>
  );
};

const SortStateToggle: React.FC<{
  tableState: Table.TableState;
  colId: string;
  updateTableState: (newTableState: Table.TableState) => void;
}> = ({updateTableState, tableState, colId}) => {
  const colSortState = tableState.sort.find(
    sort => sort.columnId === colId
  )?.dir;
  if (colSortState && colSortState === 'desc') {
    return (
      <S.ControlIcon
        name="down-arrow"
        onClick={async e => {
          recordEvent('REMOVE_COLUMN_SORT');
          updateTableState(Table.disableSortByCol(tableState, colId));
        }}
      />
    );
  } else if (colSortState && colSortState === 'asc') {
    return (
      <S.ControlIcon
        name="up-arrow"
        onClick={async e => {
          recordEvent('UPDATE_COLUMN_SORT_DESC');
          updateTableState(
            Table.enableSortByCol(Table.disableSort(tableState), colId, false)
          );
        }}
      />
    );
  } else {
    return <></>;
  }
};

const PinnedIndicator: React.FC<{
  unpin(): void;
}> = ({unpin}) => {
  return (
    <S.ControlIcon
      name="pin"
      onClick={async () => {
        recordEvent('PIN_COLUMN');
        unpin();
      }}
    />
  );
};
