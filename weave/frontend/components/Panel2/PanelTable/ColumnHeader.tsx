import React, {useCallback, useMemo, useState} from 'react';
import {Popup} from 'semantic-ui-react';

import {WBMenuOption, WBPopupMenuTrigger} from '@wandb/ui';

import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';
import * as Graph from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';

import * as S from '../PanelTable.styles';
import * as Table from './tableState';

import {usePanelStacksForType} from '../availablePanels';

import makeComp from '@wandb/common/util/profiler';
import * as SemanticHacks from '@wandb/common/util/semanticHacks';

import {PanelComp2} from '../PanelComp';
import * as LLReact from '@wandb/common/cgreact';
import EditableField from '@wandb/common/components/EditableField';
import ModifiedDropdown from '@wandb/common/components/elements/ModifiedDropdown';
import {INPUT_SLIDER_CLASS} from '@wandb/common/components/elements/SliderInput';
import * as ExpressionEditor from '../ExpressionEditor';
import * as ExpressionView from '../ExpressionView';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';

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
  inputArrayNode: Types.Node;
  rowsNode: Types.Node;
  columnName: string;
  selectFunction: Types.NodeOrVoidNode;
  colId: string;
  panelId: string;
  config: any;
  panelContext: any;
  isPinned: boolean;
  updatePanelContext(newContext: any): void;
  updateTableState(newTableState: Table.TableState): void;
  setColumnPinState(pin: boolean): void;
}> = makeComp(
  ({
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
  }) => {
    const {frame} = usePanelContext();

    const [columnSettingsOpen, setColumnSettingsOpen] = useState(false);

    const [workingSelectFunction, setWorkingSelectFunction] =
      useState<CGTypes.EditingNode>(propsSelectFunction);
    const [workingColumnName, setWorkingColumnName] =
      useState<string>(propsColumnName);
    const [workingPanelId, setWorkingPanelId] = useState<string>(propsPanelId);
    const [workingPanelConfig, setWorkingPanelConfig] =
      useState<any>(propsPanelConfig);

    const applyWorkingState = useCallback(() => {
      let newState = tableState;
      if (workingColumnName !== propsColumnName) {
        recordEvent('UPDATE_COLUMN_NAME');
        newState = Table.updateColumnName(newState, colId, workingColumnName);
      }
      if (
        HL.nodeIsExecutable(workingSelectFunction) &&
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
          frame,
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
        frame,
      ]
    );

    const exampleRowNode = useMemo(() => cellFrame.row, [cellFrame.row]);
    const selectedNode = useMemo(
      () =>
        // Only use selected node if it's executable (has no voids...)
        // otherwise fall back to the props version.
        // TODO: this isn't really right
        HL.nodeIsExecutable(workingSelectFunction)
          ? Table.getCellValueNode(exampleRowNode, workingSelectFunction)
          : Graph.voidNode(),
      [exampleRowNode, workingSelectFunction]
    );
    const {
      handler,
      stackIds,
      curPanelId: workingCurPanelId,
    } = usePanelStacksForType(workingSelectFunction.type, workingPanelId, {
      excludeTable: true,
      excludePlot: true,
    });
    const enableGroup = LLReact.useClientBound(Table.enableGroupByCol);
    const disableGroup = LLReact.useClientBound(Table.disableGroupByCol);

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
        tableState.groupBy.length === 0 &&
        Types.canGroupType(workingSelectFunction.type)
      ) {
        menuItems.push({
          value: 'group',
          name: 'Group by',
          icon: 'folder',
          onSelect: async () => {
            const newTableState = await enableGroup(
              tableState,
              colId,
              inputArrayNode,
              frame
            );
            recordEvent('GROUP');
            updateTableState(newTableState);
          },
        });
      } else if (isGroupCol) {
        menuItems.push({
          value: 'ungroup',
          name: 'Ungroup',
          icon: 'folder',
          onSelect: async () => {
            const newTableState = await disableGroup(
              tableState,
              colId,
              inputArrayNode,
              frame
            );
            recordEvent('UNGROUP');
            updateTableState(newTableState);
          },
        });
      }
      if (Types.canSortType(workingSelectFunction.type)) {
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
                inputArrayNode
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
                inputArrayNode
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
              const newTableState = Table.removeColumnsToRight(
                tableState,
                colId
              );
              recordEvent('REMOVE_COLUMNS_TO_RIGHT');
              updateTableState(newTableState);
            },
          },
          {
            value: 'remove-all-left',
            name: 'Remove all left',
            icon: 'previous',
            onSelect: () => {
              const newTableState = Table.removeColumnsToLeft(
                tableState,
                colId
              );
              recordEvent('REMOVE_COLUMNS_TO_LEFT');
              updateTableState(newTableState);
            },
          },
        ]);
      }
      return menuItems;
    }, [
      colId,
      isGroupCol,
      enableGroup,
      disableGroup,
      inputArrayNode,
      frame,
      tableState,
      updateTableState,
      workingSelectFunction.type,
      openColumnSettings,
      isPinned,
      setColumnPinState,
    ]);

    const colIsSorted =
      tableState.sort.find(sort => sort.columnId === colId)?.dir != null;

    const colControlsWidth =
      20 * (1 + (colIsSorted ? 1 : 0) + (isPinned ? 1 : 0));

    const newContextVars = useMemo(() => {
      // TODO mixing up propsSelectFunction and
      // selectFunction
      return {
        domain: HL.callFunction(propsSelectFunction, {
          row: inputArrayNode,
        }),
      };
    }, [propsSelectFunction, inputArrayNode]);

    return (
      <S.ColumnHeader data-test="column-header">
        <Popup
          basic
          className="wb-table-action-popup"
          on="click"
          open={columnSettingsOpen}
          position="bottom left"
          onOpen={openColumnSettings}
          onClose={(event, data) => {
            const nestedPopupSelector = [INPUT_SLIDER_CLASS, STYLE_POPUP_CLASS]
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
              {isGroupCol && 'Group by ('}
              {workingColumnName !== '' ? (
                <S.ColumnNameText>{workingColumnName}</S.ColumnNameText>
              ) : (
                <ExpressionView.ExpressionView
                  frame={cellFrame}
                  node={workingSelectFunction}
                />
              )}
              {isGroupCol && ')'}
            </S.ColumnName>
          }
          content={
            columnSettingsOpen && (
              <div>
                <S.ColumnEditorSection>
                  <S.ColumnEditorSectionLabel>
                    Cell expression
                  </S.ColumnEditorSectionLabel>
                  <S.AssignmentWrapper>
                    <ExpressionEditor.ExpressionEditor
                      frame={cellFrame}
                      node={workingSelectFunction}
                      updateNode={setWorkingSelectFunction}
                      // onAccept={setWorkingSelectFunction}
                    />
                  </S.AssignmentWrapper>
                  {/* <div
                      onClick={() =>
                        copyToClipboard(
                          Types.toString(selectFunction.type, false)
                        )
                      }>
                      <div>{Types.toString(selectFunction.type)}</div>
                    </div> */}
                  <S.ColumnEditorColumnName>
                    <S.ColumnEditorFieldLabel>
                      Column name:
                    </S.ColumnEditorFieldLabel>
                    <EditableField
                      value={workingColumnName}
                      placeholder={ExpressionView.simpleNodeString(
                        workingSelectFunction
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
        <>
          <WBPopupMenuTrigger options={columnMenuItems}>
            {({anchorRef, setOpen, open}) => (
              <S.ColumnAction className="column-controls">
                {isPinned && (
                  <PinnedIndicator unpin={() => setColumnPinState(false)} />
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
        </>
      </S.ColumnHeader>
    );
  },
  {id: 'ColumnHeader'}
);

const SortStateToggle: React.FC<{
  tableState: Table.TableState;
  colId: string;
  updateTableState: (newTableState: Table.TableState) => void;
}> = makeComp(
  ({updateTableState, tableState, colId}) => {
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
  },
  {id: 'SortStateToggle'}
);

const PinnedIndicator: React.FC<{
  unpin(): void;
}> = makeComp(
  ({unpin}) => {
    return (
      <S.ControlIcon
        name="pin"
        onClick={async () => {
          recordEvent('PIN_COLUMN');
          unpin();
        }}
      />
    );
  },
  {id: 'PinToggle'}
);
