import React, {useCallback, useMemo} from 'react';
import makeComp from '@wandb/common/util/profiler';
import * as HL from '@wandb/cg/browser/hl';
import {PanelComp2} from '../PanelComp';
import * as LLReact from '@wandb/common/cgreact';
import {usePanelStacksForType} from '../availablePanels';
import * as Types from '@wandb/cg/browser/model/types';
import * as Table from './tableState';
import {PanelContextProvider} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as TH from './hooks';

const recordEvent = makeEventRecorder('Table');

export const Cell: React.FC<{
  table: Table.TableState;
  inputNode: Types.Node;
  rowNode: Types.Node;
  selectFunction: Types.NodeOrVoidNode;
  colId: string;
  panelId: string;
  config: any;
  panelContext: any;
  updateTableState(newConfig: any): void;
  updatePanelContext(newContext: any): void;
}> = makeComp(
  ({
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
  }) => {
    const updatePanelConfig = TH.useUpdatePanelConfig(
      updateTableState,
      table,
      colId
    );
    const refineNode = LLReact.useClientBound(HL.refineNode);
    const selectedNode = useMemo(
      () => Table.getCellValueNode(rowNode, selectFunction),
      [rowNode, selectFunction]
    );

    const {handler, curPanelId} = usePanelStacksForType(
      selectedNode.type,
      panelId,
      {
        excludeTable: true,
        excludePlot: true,
      }
    );

    // Only render when on screen for the first time. Each time selectedNode
    // changes, this behavior resets.
    // const [domRef, shouldRender] =
    //   useWhenOnScreenAfterNewValueDebounced(selectedNode);
    const shouldRender = true;

    const updatePanelInput = useCallback<any>(
      (newInput: Types.Node) => {
        if (selectFunction.nodeType === 'void') {
          throw new Error('Invalid cell selection function (void)');
        }
        if (
          HL.filterNodes(
            newInput,
            checkNode =>
              checkNode.nodeType === 'var' && checkNode.varName === 'input'
          ).length === 0
        ) {
          console.warn('invalid updateInput call');
          return;
        }
        const called = HL.callFunction(newInput, {input: selectFunction});
        const doUpdate = async () => {
          recordEvent('UPDATE_COLUMN_EXPRESSION_VIA_CELL');
          try {
            const refined = await refineNode(called, {row: rowNode});
            updateTableState(Table.updateColumnSelect(table, colId, refined));
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
      [colId, rowNode, selectFunction, table, updateTableState, refineNode]
    );
    const newContextVars = useMemo(() => {
      return {
        // TODO: This is just plain wrong, callFunction doesn't adjust types!
        domain: HL.callFunction(selectFunction, {row: inputNode}),
      };
    }, [selectFunction, inputNode]);
    return (
      <div
        // ref={domRef}
        data-test-should-render={shouldRender}
        style={{width: '100%', height: '100%'}}
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
            </PanelContextProvider>
          )
        )}
      </div>
    );
  },
  {id: 'PanelTableCell'}
);

export const Value: React.FC<{
  table: Table.TableState;
  valueNode: Types.Node;
  config: any;
  panelContext: any;
  colId: string;
  updateTableState(newConfig: any): void;
  updatePanelContext(newContext: any): void;
}> = makeComp(
  ({
    table,
    valueNode,
    config,
    panelContext,
    colId,
    updateTableState,
    updatePanelContext,
  }) => {
    const updatePanelConfig = TH.useUpdatePanelConfig(
      updateTableState,
      table,
      colId
    );
    const {handler, curPanelId} = usePanelStacksForType(valueNode.type, '', {
      excludeTable: true,
      excludePlot: true,
    });

    return (
      <>
        {curPanelId == null ? (
          <div>No panel for type {Types.toString(valueNode.type)}</div>
        ) : (
          handler != null && (
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
          )
        )}
      </>
    );
  },
  {id: 'Value'}
);
