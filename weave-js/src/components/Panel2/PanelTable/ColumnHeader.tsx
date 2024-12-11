import React, {CSSProperties, useCallback, useContext, useMemo, useState} from 'react';
import {Button, Popup, DropdownProps} from 'semantic-ui-react';
import {WBMenuOption, WBPopupMenuTrigger} from '@wandb/ui';
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
  VarNode,
  OutputNode,
  Type,
} from '@wandb/weave/core';
import ModifiedDropdown from '../../../common/components/elements/ModifiedDropdown';
import EditableField from '../../../common/components/EditableField';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as SemanticHacks from '../../../common/util/semanticHacks';
import {ExpressionView} from '../ExpressionView';
import {SUGGESTION_OPTION_CLASS} from '../../../panel/WeaveExpression/styles';
import {PanelComp2} from '../PanelComp';
import {Tooltip} from '../../Tooltip';
import * as S from './ColumnHeader.styles';
import * as Table from './tableState';
import {WeaveContext, useWeaveContext} from '../../../context';

// Constants
const INPUT_SLIDER_CLASS = 'input-slider';
const STYLE_POPUP_CLASS = 'control-box-popup';

// Event recorder
const recordEvent = makeEventRecorder('PanelTable');

// Types
interface Column {
  id: string;
  select: EditingNode;
}

type MenuItem = WBMenuOption;

interface PanelConfig {
  [key: string]: any;
}

const makeMenuItemDivider = (value: string): WBMenuOption => ({
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
});

const makeSortingMenuItems = (
  tableState: Table.TableState,
  colId: string,
  updateTableState: (newTableState: Table.TableState) => Promise<void>
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
      onSelect: async (e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        recordEvent('UPDATE_COLUMN_SORT_ASC');
        const newTableState = Table.enableSortByCol(
          Table.disableSort(tableState),
          colId,
          true
        );
        await updateTableState(newTableState);
      },
    });
  }

  if (colSortState !== undefined) {
    menuItems.push({
      value: 'sort-remove',
      name: 'Remove Sort',
      icon: 'delete',
      onSelect: async (e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        recordEvent('REMOVE_COLUMN_SORT');
        const newTableState = Table.disableSortByCol(tableState, colId);
        await updateTableState(newTableState);
      },
    });
  }

  if (colSortState !== 'desc') {
    menuItems.push({
      value: 'sort-desc',
      name: 'Sort Desc',
      icon: 'down-arrow',
      onSelect: async (e: React.MouseEvent<HTMLElement>) => {
        e.stopPropagation();
        recordEvent('UPDATE_COLUMN_SORT_DESC');
        const newTableState = Table.enableSortByCol(
          Table.disableSort(tableState),
          colId,
          false
        );
        await updateTableState(newTableState);
      },
    });
  }

  return menuItems;
};

const getColumnSelect = (state: Table.TableState, colId: string): EditingNode | null => {
  const column = state.columns.find((col: Column) => col.id === colId);
  return column?.select ?? null;
};

const isColumnSelectEqual = (
  state: Table.TableState,
  colId: string,
  selectFn: EditingNode
): boolean => {
  const currentSelect = getColumnSelect(state, colId);
  return currentSelect != null && currentSelect === selectFn;
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
  const [textAlign, setTextAlign] = useState<'left' | 'right' | 'center'>('center');
  const [workingSelectFunction, setWorkingSelectFunction] =
    useState<EditingNode>(propsSelectFunction);
  const [workingColumnName, setWorkingColumnName] =
    useState<string>(propsColumnName);
  const [workingPanelId, setWorkingPanelId] = useState<string>(propsPanelId);
  const [workingPanelConfig, setWorkingPanelConfig] =
    useState<any>(propsPanelConfig);
  const [focusEditorRef, setFocusEditorRef] = useState<(() => void) | null>(null);

  const focusEditor = useCallback(() => {
    if (focusEditorRef) {
      focusEditorRef();
    }
  }, [focusEditorRef]);

  const enableGroup = Table.enableGroupByCol;
  const disableGroup = Table.disableGroupByCol;
  const isGroupCountColumn = colId === 'groupCount';

  const applyWorkingState = useCallback(async () => {
    let newState = tableState;
    if (workingColumnName !== propsColumnName) {
      recordEvent('UPDATE_COLUMN_NAME');
      newState = Table.updateColumnName(newState, colId, workingColumnName);
    }
    if (
      weave.nodeIsExecutable(workingSelectFunction) &&
      !isColumnSelectEqual(newState, colId, workingSelectFunction)
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
        recordEvent('UPDATE_COLUMN_PANEL', {
          exprString: weave.expToString(workingSelectFunction),
        });
      }
    }

    if (newState !== tableState) {
      await updateTableState(newState);
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
        onSelect: () => {
          const syntheticEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
          }) as unknown as React.MouseEvent<HTMLElement>;

          const handleGroup = async (e: React.MouseEvent<HTMLElement>) => {
            e.stopPropagation();
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
                  (inputs: {row: VarNode<Type>}) => {
                    return opCount({arr: inputs.row});
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
            await updateTableState(newTableState);
          };
          handleGroup(syntheticEvent);
        },
      });
    } else if (isGroupCol) {
      menuItems.push({
        value: 'ungroup',
        name: 'Ungroup',
        icon: 'group-runs',
        onSelect: () => {
          const syntheticEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
          }) as unknown as React.MouseEvent<HTMLElement>;

          const handleUngroup = (e: React.MouseEvent<HTMLElement>) => {
            e.stopPropagation();
            doUngroup();
          };
          handleUngroup(syntheticEvent);
        },
      });
    }
    if (canSortType(workingSelectFunction.type)) {
      const sortMenuItems = makeSortingMenuItems(tableState, colId, updateTableState);
      menuItems = [...menuItems, ...sortMenuItems];
    }
    if (!isGroupCol) {
      if (menuItems.length > 0) {
        menuItems.push(makeMenuItemDivider('insert-div'));
      }
      menuItems = [
        ...menuItems,
        {
          value: 'insert-right',
          name: 'Insert 1 right',
          icon: 'next',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handleInsertRight = async (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              const newTableState = Table.insertColumnRight(
                tableState,
                colId,
                inputArrayNode,
                weave
              );
              recordEvent('INSERT_COLUMN');
              await updateTableState(newTableState);
            };
            handleInsertRight(syntheticEvent);
          },
        },
        {
          value: 'insert-left',
          name: 'Insert 1 left',
          icon: 'previous',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handleInsertLeft = async (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              const newTableState = Table.insertColumnLeft(
                tableState,
                colId,
                inputArrayNode,
                weave
              );
              recordEvent('INSERT_COLUMN');
              await updateTableState(newTableState);
            };
            handleInsertLeft(syntheticEvent);
          },
        },
        makeMenuItemDivider('pin-div'),
        {
          value: 'pin',
          name: isPinned ? 'Unpin' : 'Pin',
          icon: 'pin',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handlePin = (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              recordEvent('PIN_COLUMN');
              setColumnPinState(!isPinned);
            };
            handlePin(syntheticEvent);
          },
        },
        makeMenuItemDivider('remove-div'),
        {
          value: 'remove',
          name: 'Remove',
          icon: 'delete',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handleRemove = async (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              const newTableState = Table.removeColumn(tableState, colId);
              recordEvent('REMOVE_COLUMN');
              await updateTableState(newTableState);
            };
            handleRemove(syntheticEvent);
          },
        },
        {
          value: 'remove-all-right',
          name: 'Remove all right',
          icon: 'next',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handleRemoveAllRight = async (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              const newTableState = Table.removeColumnsToRight(tableState, colId);
              recordEvent('REMOVE_COLUMNS_TO_RIGHT');
              await updateTableState(newTableState);
            };
            handleRemoveAllRight(syntheticEvent);
          },
        },
        {
          value: 'remove-all-left',
          name: 'Remove all left',
          icon: 'previous',
          onSelect: () => {
            const syntheticEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
            }) as unknown as React.MouseEvent<HTMLElement>;

            const handleRemoveAllLeft = async (e: React.MouseEvent<HTMLElement>) => {
              e.stopPropagation();
              const newTableState = Table.removeColumnsToLeft(tableState, colId);
              recordEvent('REMOVE_COLUMNS_TO_LEFT');
              await updateTableState(newTableState);
            };
            handleRemoveAllLeft(syntheticEvent);
          },
        },
      ];
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

  const columnNameStyle =
    textAlign === 'right'
      ? {marginLeft: `-${colControlsWidth}px`}
      : {marginRight: `-${colControlsWidth}px`};

  // When there is a right justified column, reverse the order of the indicators
  // and set z-index to 1 otherwise click events on the Ellipses icon is blocked
  // by the click event on the column name due to DOM ordering and negative margins.
  const columnActionContainerStyle: CSSProperties =
    textAlign === 'right'
      ? {zIndex: 1, flexDirection: 'row-reverse'}
      : {flexDirection: 'row'};

  return (
    <S.ColumnHeader
      data-test="column-header"
      style={{
        textAlign,
        flexDirection: textAlign === 'right' ? 'row-reverse' : 'row',
      }}>
      {simpleTable ? (
        workingColumnName !== '' ? (
          <S.ColumnNameText>{workingColumnName}</S.ColumnNameText>
        ) : (
          <ExpressionView
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
          onClose={(e: React.MouseEvent<HTMLElement>) => {
            const nestedPopupSelector = [
              INPUT_SLIDER_CLASS,
              STYLE_POPUP_CLASS,
              SUGGESTION_OPTION_CLASS,
            ]
              .map(c => '.' + c)
              .join(',');

            const inPopup =
              (e.target as HTMLElement).closest(nestedPopupSelector) !=
              null;

            if (!inPopup) {
              SemanticHacks.withIgnoreBlockedClicks(() => {
                applyWorkingState();
                setColumnSettingsOpen(false);
              })(e, {});
            }
          }}
          trigger={
            <S.ColumnName
              style={columnNameStyle}
              onClick={() => setColumnSettingsOpen(!columnSettingsOpen)}>
              {propsColumnName !== '' ? (
                <S.ColumnNameText>{propsColumnName}</S.ColumnNameText>
              ) : (
                <ExpressionView
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
                        <ExpressionView
                          frame={cellFrame}
                          node={workingSelectFunction}
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
                      onChange={(
                        event: React.SyntheticEvent<HTMLElement>,
                        data: DropdownProps
                      ) => setWorkingPanelId(String(data.value))}
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
                            updateConfig={(config: PanelConfig) =>
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
            <S.ColumnActionContainer
              className="column-controls"
              style={columnActionContainerStyle}>
              <S.ColumnAction>
                {isPinned && (
                  <PinnedIndicator unpin={() => setColumnPinState(false)} />
                )}
                {isGroupCol && (
                  <S.ControlIcon
                    name="group-runs"
                    onClick={async (e: React.MouseEvent) => {
                      e.stopPropagation();
                      recordEvent('REMOVE_COLUMN_GROUPING');
                      await doUngroup();
                    }}
                  />
                )}
              </S.ColumnAction>
              <S.ColumnAction>
                {colIsSorted && (
                  <SortStateToggle
                    {...{
                      tableState,
                      colId,
                      updateTableState,
                    }}
                  />
                )}
              </S.ColumnAction>
              <S.ColumnAction>
                <S.EllipsisIcon
                  ref={anchorRef}
                  data-test="column-options"
                  name="overflow"
                  className="column-actions-trigger"
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    setOpen(o => !o);
                  }}
                />
              </S.ColumnAction>
            </S.ColumnActionContainer>
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
        onClick={async (e: React.MouseEvent) => {
          e.stopPropagation();
          recordEvent('REMOVE_COLUMN_SORT');
          await updateTableState(Table.disableSortByCol(tableState, colId));
        }}
      />
    );
  } else if (colSortState && colSortState === 'asc') {
    return (
      <S.ControlIcon
        name="up-arrow"
        onClick={async (e: React.MouseEvent) => {
          e.stopPropagation();
          recordEvent('UPDATE_COLUMN_SORT_DESC');
          await updateTableState(
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
