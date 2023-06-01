import {linkHoverBlue} from '@wandb/weave/common/css/globals.styles';
import {
  compareItems,
  constFunction,
  constString,
  defaultLanguageBinding,
  Node,
  NodeOrVoidNode,
  opGroupGroupKey,
  opMap,
  opPick,
  taggableValue,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import React, {useMemo, useState} from 'react';
import {Resizable} from 'react-resizable';

import {useWeaveContext} from '../../../context';
import {useGatedValue} from '../../../hookUtils';
import * as LLReact from '../../../react';
import {panelSpecById, usePanelStacksForType} from '../availablePanels';
import {PanelComp2} from '../PanelComp';
import {PanelContextProvider} from '../PanelContext';
import {PanelString} from '../PanelString';
import * as TableState from '../PanelTable/tableState';
import {PanelType} from '../PanelType';
import {defaultFacet, PanelFacetProps, useConfig} from './common';

export {PanelFacetConfig} from './common';

const SelectPanel: React.FC<{
  inputNode: Node;
  selectFunction: NodeOrVoidNode;
  panelId: string | undefined;
  vars: {[key: string]: NodeOrVoidNode};
  config: any;
  panelContext: any;
  updateConfig(newConfig: any): void;
  updatePanelContext(newContext: any): void;
}> = ({
  inputNode,
  selectFunction,
  vars,
  panelId,
  config,
  panelContext,
  updateConfig,
  updatePanelContext,
}) => {
  const {handler, curPanelId} = usePanelStacksForType(
    selectFunction.type,
    panelId,
    {excludeTable: true}
  );

  return curPanelId == null || handler == null ? (
    <div>
      No panel for type {defaultLanguageBinding.printType(selectFunction.type)}
    </div>
  ) : (
    <PanelContextProvider
      newVars={{
        ...vars,
        row: inputNode,
      }}>
      <PanelComp2
        input={selectFunction}
        inputType={selectFunction.type}
        loading={false}
        panelSpec={handler}
        configMode={false}
        context={panelContext}
        config={config}
        updateConfig2={() => console.log('DROPPED UPDATE CONFIG2')}
        updateConfig={updateConfig}
        updateContext={updatePanelContext}
      />
    </PanelContextProvider>
  );
};

const PanelFacetFlexMode: React.FC<PanelFacetProps> = props => {
  const {input} = props;
  const inputNode = input;

  const weave = useWeaveContext();

  const config = useMemo(
    () =>
      // TODO: be better. we trigger this when switching from Plot
      props.config == null ||
      props.config.dims == null ||
      props.config.dims.select == null
        ? defaultFacet()
        : props.config,
    [props.config]
  );
  const {table, dims, cellSize} = config;
  const [resizingSize, setResizingSize] = useState(cellSize);

  const xColName = TableState.getTableColumnName(
    table.columnNames,
    table.columnSelectFunctions,
    dims.x,
    weave.client.opStore
  );

  const {
    rowsNode,
    // resultNode,
  } = useMemo(
    () => TableState.tableGetResultTableNode(table, inputNode, weave),
    [table, inputNode, weave]
  );

  const cellNodesUse = LLReact.useEach(rowsNode as any);

  const cellNodes = useMemo(
    () => (cellNodesUse.loading ? [] : cellNodesUse.result),
    [cellNodesUse.loading, cellNodesUse.result]
  );

  const cellFunction = table.columnSelectFunctions[dims.select];
  if (cellFunction.nodeType === 'void' || cellFunction.type === 'invalid') {
    // We check this in PanelFacet
    throw new Error('Invalid panel cell function');
  }

  // TODO: make this handle only visible nodes! we can make an infinite scroll
  // facet panel easily. E.g. same way as we do paging on the table.
  return useGatedValue(
    <div style={{display: 'flex', flexWrap: 'wrap'}}>
      {cellNodes.map((cellNode, i) => {
        const picked = opPick({
          obj: opGroupGroupKey({obj: cellNode}) as any,
          key: constString(xColName),
        });
        const cell = (
          <div key={i} style={{display: 'flex', marginRight: config.padding}}>
            <div style={{display: 'flex', marginRight: 4}}>
              {/* TODO Don't hard-code typeswitch here */}
              {taggableValue(picked.type) === 'type' ? (
                <PanelType
                  // Have to force this right now. PanelString should
                  // declare that it can work on anything with a toString()
                  // method.
                  input={picked as any}
                  context={props.context}
                  updateContext={props.updateContext}
                  // Get rid of updateConfig
                  updateConfig={() => console.log('HELLO')}
                />
              ) : (
                <PanelString
                  // Have to force this right now. PanelString should
                  // declare that it can work on anything with a toString()
                  // method.
                  input={picked as any}
                  context={props.context}
                  updateContext={props.updateContext}
                  // Get rid of updateConfig
                  updateConfig={() => console.log('HELLO')}
                />
              )}
              :
            </div>
            <SelectPanel
              inputNode={cellNode}
              selectFunction={cellFunction}
              vars={table.columns[dims.select].panelVars ?? {}}
              panelId={table.columns[dims.select].panelId}
              config={table.columns[dims.select].panelConfig}
              panelContext={props.context}
              updateConfig={newConfig =>
                props.updateConfig({
                  table: TableState.updateColumnPanelConfig(
                    table,
                    dims.select,
                    newConfig
                  ),
                })
              }
              updatePanelContext={props.updateContext}
            />
          </div>
        );
        if (!config.manualSize) {
          return cell;
        }
        return (
          <Resizable
            key={i}
            width={cellSize.w}
            height={cellSize.h}
            onResize={(e, data) => {
              setResizingSize({w: data.size.width, h: data.size.height});
            }}
            onResizeStop={() => props.updateConfig({cellSize: resizingSize})}>
            <div style={{width: config.cellSize.w, height: config.cellSize.h}}>
              {cell}
            </div>
          </Resizable>
        );
      })}
    </div>,
    o => !cellNodesUse.loading
  );
};

const PanelFacetGridMode: React.FC<PanelFacetProps> = props => {
  const {input} = props;
  const inputNode = input;

  const weave = useWeaveContext();

  const config = useMemo(
    () =>
      // TODO: be better. we trigger this when switching from Plot
      props.config == null ||
      props.config.dims == null ||
      props.config.dims.select == null
        ? defaultFacet()
        : props.config,
    [props.config]
  );
  const {table, dims, cellSize} = config;
  const [resizingSize, setResizingSize] = useState(cellSize);

  const cellFunction = table.columnSelectFunctions[dims.select];

  const {
    rowsNode,
    // resultNode,
  } = useMemo(
    () => TableState.tableGetResultTableNode(table, inputNode, weave),
    [table, inputNode, weave]
  );

  // TODO: move into Table state
  const domainNode = useMemo(
    () =>
      opMap({
        arr: rowsNode as any,
        mapFn: constFunction(
          {row: TableState.getExampleRow(rowsNode).type},
          ({row}) => weave.callFunction(cellFunction, {row})
        ) as any,
      }),
    [rowsNode, cellFunction, weave]
  );
  const cellVars = useMemo(() => ({domain: domainNode}), [domainNode]);

  const groupKeysNode = opMap({
    arr: rowsNode as any,
    mapFn: constFunction(
      {row: TableState.getExampleRow(rowsNode).type},
      ({row}) => opGroupGroupKey({obj: row})
    ) as any,
  });
  const groupKeysUse = LLReact.useNodeValue(groupKeysNode as any);
  const cellNodesUse = LLReact.useEach(rowsNode as any);

  const xColName = TableState.getTableColumnName(
    table.columnNames,
    table.columnSelectFunctions,
    dims.x,
    weave.client.opStore
  );
  const yColName = TableState.getTableColumnName(
    table.columnNames,
    table.columnSelectFunctions,
    dims.y,
    weave.client.opStore
  );

  const groupKeys = useMemo(
    () => (groupKeysUse.loading ? [] : groupKeysUse.result),
    [groupKeysUse.loading, groupKeysUse.result]
  );

  // TODO: this is really lame, I want to recover the sort order
  // from the group keys, but multi-sort makes that harder. So we
  // actually do the sort again here :(. This is a very bad smell, all
  // data manipulation should happen as CG ops.
  // A different approach would be to two two successive groupBys instead
  // of the single multi-groupBy we do now.
  const {xPos, yPos} = useMemo(() => {
    const xKeys: any[] = [];
    const yKeys: any[] = [];
    groupKeys.forEach((gk: {[key: string]: any}) => {
      const xKey = gk[xColName];
      xKeys.push(xKey);
      const yKey = gk[yColName];
      yKeys.push(yKey);
    });
    let sortedXKeys = _.uniqBy(xKeys, xKey =>
      xKey instanceof Date ? xKey.getTime() : xKey
    );
    const sortXSetting = table.sort.find(
      sortCol => sortCol.columnId === dims.x
    );
    if (sortXSetting != null) {
      sortedXKeys = sortedXKeys.sort(
        (a, b) => compareItems(a, b) * (sortXSetting.dir === 'asc' ? 1 : -1)
      );
    }
    let sortedYKeys = _.uniqBy(yKeys, yKey =>
      yKey instanceof Date ? yKey.getTime() : yKey
    );
    const sortYSetting = table.sort.find(
      sortCol => sortCol.columnId === dims.y
    );
    if (sortYSetting != null) {
      sortedYKeys = sortedYKeys.sort(
        (a, b) => compareItems(a, b) * (sortYSetting.dir === 'asc' ? 1 : -1)
      );
    }
    return {
      xPos: _.fromPairs(sortedXKeys.map((xKey, i) => [xKey, i])),
      yPos: _.fromPairs(sortedYKeys.map((yKey, i) => [yKey, i])),
    };
  }, [dims.x, dims.y, groupKeys, table.sort, xColName, yColName]);

  const cellNodes = useMemo(
    () => (cellNodesUse.loading ? [] : cellNodesUse.result),
    [cellNodesUse.loading, cellNodesUse.result]
  );

  // TODO: make this handle only visible nodes! we can make an infinite scroll
  // facet panel easily. E.g. same way as we do paging on the table.
  return useGatedValue(
    <div
      style={{
        display: 'inline-block',
        marginLeft: 'auto',
        marginRight: 'auto',
      }}>
      <div
        // TODO: I'm just putting this in
        style={{
          display: 'grid',
          gridTemplateColumns: 140,
          gridTemplateRows: 24,
          gridAutoColumns: config.cellSize.w,
          gridAutoRows: config.cellSize.h,
        }}>
        {Object.keys(xPos).map(xKey => (
          <div
            key={'col-' + xKey}
            style={{
              gridColumnStart: xPos[xKey] + 2,
              gridRowStart: 1,
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
              fontSize: 10,
            }}>
            {xKey}
          </div>
        ))}
        {Object.keys(yPos).map(yKey => (
          <div
            key={'row-' + yKey}
            style={{
              gridRowStart: yPos[yKey] + 2,
              gridColumnStart: 1,
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              textOverflow: 'ellipsis',
              fontSize: 12,
            }}>
            {yKey}
          </div>
        ))}
        {cellNodes.map((cellNode, i) => {
          const groupKey = groupKeys[i];

          if (groupKey == null) {
            return <div>-</div>;
          }

          const xKey = groupKey[xColName];
          const yKey = groupKey[yColName];
          const selected =
            xKey === config.selectedCell?.x && config.selectedCell?.y === yKey;
          return (
            <Resizable
              key={'cell-' + xPos[xKey] + '-' + yPos[yKey]}
              width={cellSize.w}
              height={cellSize.h}
              onResize={(e, data) => {
                setResizingSize({w: data.size.width, h: data.size.height});
              }}
              onResizeStop={() => props.updateConfig({cellSize: resizingSize})}>
              <div
                style={{
                  width: config.cellSize.w,
                  height: config.cellSize.h,
                  gridColumnStart: xPos[xKey] + 2,
                  gridRowStart: yPos[yKey] + 2,
                  border: selected ? `1px solid ${linkHoverBlue}` : undefined,
                }}
                onClick={() =>
                  props.updateConfig({selectedCell: {x: xKey, y: yKey}})
                }>
                <PanelContextProvider newVars={cellVars}>
                  <SelectPanel
                    inputNode={cellNode}
                    selectFunction={cellFunction}
                    vars={table.columns[dims.select].panelVars ?? {}}
                    panelId={table.columns[dims.select].panelId}
                    config={table.columns[dims.select].panelConfig}
                    panelContext={props.context}
                    updateConfig={newConfig =>
                      props.updateConfig({
                        table: TableState.updateColumnPanelConfig(
                          table,
                          dims.select,
                          newConfig
                        ),
                      })
                    }
                    updatePanelContext={props.updateContext}
                  />
                </PanelContextProvider>
              </div>
            </Resizable>
          );
        })}
      </div>
    </div>,
    o => !cellNodesUse.loading
  );
};

const PanelFacet: React.FC<PanelFacetProps> = props => {
  const config = useConfig(props.config);
  const {table, dims} = config;

  const xEnabled = table.columnSelectFunctions[dims.x].type !== 'invalid';

  // TODO: Combine into a childPanelIsRenderable function
  const cellPanel = panelSpecById(table.columns[dims.select].panelId);
  const cellEnabled =
    table.columnSelectFunctions[dims.select].type !== 'invalid' ||
    (cellPanel != null &&
      (cellPanel.inputType === 'invalid' || cellPanel.inputType === 'any'));
  const yEnabled = table.columnSelectFunctions[dims.y].type !== 'invalid';
  if (!xEnabled) {
    return <div>x must be configured</div>;
  }

  if (!cellEnabled) {
    return <div>cell must be configured</div>;
  }

  if (!yEnabled) {
    return <PanelFacetFlexMode {...props} />;
  }

  return <PanelFacetGridMode {...props} />;
};

export default PanelFacet;
