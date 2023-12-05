import {
  defaultLanguageBinding,
  filterNodes,
  Node,
  NodeOrVoidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';

import {ActionsTrigger} from '../../../actions';
import {useWeaveContext, useWeaveFeaturesContext} from '../../../context';
import {useWhenOnScreenAfterNewValueDebounced} from '../../../hookUtils';
import {usePanelStacksForType} from '../availablePanels';
import {PanelComp2} from '../PanelComp';
import {PanelContextProvider} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import {CellWrapper} from '../PanelTable.styles';
import * as TH from './hooks';
import * as Table from './tableState';

const recordEvent = makeEventRecorder('Table');

export const Cell: React.FC<{
  table: Table.TableState;
  inputNode: Node;
  rowNode: Node;
  selectFunction: NodeOrVoidNode;
  colId: string;
  panelId: string;
  config: any;
  panelContext: any;
  simpleTable?: boolean;
  updateTableState(newConfig: any): void;
  updatePanelContext(newContext: any): void;
  updateInput?(newInput: any): void;
}> = ({
  table,
  inputNode,
  rowNode,
  selectFunction,
  panelId,
  colId,
  config,
  panelContext,
  updateTableState,
  updatePanelContext,
  updateInput,
  simpleTable,
}) => {
  const weave = useWeaveContext();
  const {actions: actionsEnabled} = useWeaveFeaturesContext();

  const updatePanelConfig = TH.useUpdatePanelConfig(
    updateTableState,
    table,
    colId
  );
  // const selectedNode = useMemo(
  //   () => Table.getCellValueNode(weave, rowNode, selectFunction),
  //   [rowNode, selectFunction, weave]
  // );
  const selectedNode = selectFunction;

  const {handler, curPanelId} = usePanelStacksForType(
    selectedNode.type,
    panelId,
    {
      excludeTable: true,
      excludePlot: true,
      disallowedPanels: ['Group', 'Expression'],
    }
  );

  // Only render when on screen for the first time. Each time selectedNode
  // changes, this behavior resets.
  const [domRef, shouldRender] =
    useWhenOnScreenAfterNewValueDebounced(selectedNode);

  const updatePanelInput = useCallback<any>(
    (newInput: Node) => {
      if (selectFunction.nodeType === 'void') {
        throw new Error('Invalid cell selection function (void)');
      }
      if (
        filterNodes(
          newInput,
          checkNode =>
            checkNode.nodeType === 'var' && checkNode.varName === 'input'
        ).length === 0
      ) {
        if (updateInput != null) {
          updateInput(newInput);
        }
        return;
      }
      const called = weave.callFunction(newInput, {input: selectFunction});
      const doUpdate = async () => {
        recordEvent('UPDATE_COLUMN_EXPRESSION_VIA_CELL');
        try {
          // const refined = await weave.refineNode(called, {row: rowNode});
          updateTableState(Table.updateColumnSelect(table, colId, called));
        } catch (e) {
          return Promise.reject(e);
        }
        return Promise.resolve();
      };
      doUpdate().catch(e => {
        console.error('PanelTable error', e);
        throw new Error(e);
      });
    },
    [colId, selectFunction, table, updateTableState, updateInput, weave]
  );
  const newContextVars = useMemo(() => {
    return {
      // TODO: This is just plain wrong, callFunction doesn't adjust types!
      domain: weave.callFunction(selectFunction, {row: inputNode}),
      row: rowNode,
      input: selectFunction,
    };
  }, [selectFunction, inputNode, rowNode, weave]);
  return (
    <CellWrapper
      ref={domRef}
      data-test-should-render={shouldRender}
      // style={{
      //   ...getPanelStackDims(handler, selectedNode.type, config),
      // }}>
    >
      {curPanelId == null ? (
        <div>-</div>
      ) : (
        shouldRender &&
        selectFunction.nodeType !== 'void' &&
        selectedNode.nodeType !== 'void' &&
        handler != null && (
          <PanelContextProvider
            // Make a new variable "domain" available to child cells.
            // This can be used to get the full range of the input data.
            newVars={newContextVars}>
            {actionsEnabled && !simpleTable ? (
              <ActionsTrigger input={selectFunction}>
                <PanelComp2
                  input={selectedNode}
                  inputType={selectFunction.type}
                  loading={false}
                  panelSpec={handler}
                  configMode={false}
                  context={panelContext}
                  config={config}
                  updateConfig={updatePanelConfig}
                  updateContext={updatePanelContext}
                  updateInput={updatePanelInput}
                />
              </ActionsTrigger>
            ) : (
              <PanelComp2
                input={selectedNode}
                inputType={selectFunction.type}
                loading={false}
                panelSpec={handler}
                configMode={false}
                context={panelContext}
                config={config}
                updateConfig={updatePanelConfig}
                updateContext={updatePanelContext}
                updateInput={updatePanelInput}
              />
            )}
          </PanelContextProvider>
        )
      )}
    </CellWrapper>
  );
};

export const Value: React.FC<{
  table: Table.TableState;
  valueNode: Node;
  config: any;
  panelContext: any;
  colId: string;
  updateTableState(newConfig: any): void;
  updatePanelContext(newContext: any): void;
}> = ({
  table,
  valueNode,
  config,
  panelContext,
  colId,
  updateTableState,
  updatePanelContext,
}) => {
  const {actions: actionsEnabled} = useWeaveFeaturesContext();
  const updatePanelConfig = TH.useUpdatePanelConfig(
    updateTableState,
    table,
    colId
  );
  const {handler, curPanelId} = usePanelStacksForType(valueNode.type, '', {
    excludeTable: true,
    excludePlot: true,
    disallowedPanels: ['Group', 'Expression'],
  });

  return (
    <>
      {curPanelId == null ? (
        <div>
          No panel for type {defaultLanguageBinding.printType(valueNode.type)}
        </div>
      ) : (
        handler != null &&
        (actionsEnabled ? (
          <ActionsTrigger input={valueNode}>
            <PanelComp2
              input={valueNode}
              inputType={valueNode.type}
              loading={false}
              panelSpec={handler}
              configMode={false}
              context={panelContext}
              config={config}
              updateConfig={updatePanelConfig}
              updateContext={updatePanelContext}
            />
          </ActionsTrigger>
        ) : (
          <PanelComp2
            input={valueNode}
            inputType={valueNode.type}
            loading={false}
            panelSpec={handler}
            configMode={false}
            context={panelContext}
            config={config}
            updateConfig={updatePanelConfig}
            updateContext={updatePanelContext}
          />
        ))
      )}
    </>
  );
};
