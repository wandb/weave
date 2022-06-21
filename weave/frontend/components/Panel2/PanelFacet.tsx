import * as _ from 'lodash';
import React from 'react';
// TODO: importing PanelTable.styles? :(
import * as S from './PanelTable.styles';
import {useMemo, useCallback, useState} from 'react';
import * as Panel2 from './panel';
import * as Types from '@wandb/cg/browser/model/types';
import * as Op from '@wandb/cg/browser/ops';
import * as Graph from '@wandb/cg/browser/graph';
import * as HL from '@wandb/cg/browser/hl';
import * as LLReact from '@wandb/common/cgreact';
import * as TableState from './PanelTable/tableState';
import makeComp from '@wandb/common/util/profiler';
import * as ConfigPanel from './ConfigPanel';
import {PanelComp2} from './PanelComp';
import {usePanelStacksForType} from './availablePanels';
import {Resizable} from 'react-resizable';
import {PanelString} from './PanelString';
import {PanelType} from './PanelType';
import {PanelContextProvider, usePanelContext} from './PanelContext';
// TODO: dont' import this, refactor DimConfig into own
// file.
import * as PanelPlot from './PanelPlot';
import {useGatedValue} from '@wandb/common/state/hooks';

const inputType = {type: 'list' as const, objectType: 'any' as const};

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
  };
}

const useConfig = (propsConfig: FacetConfig | undefined): FacetConfig => {
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

type PanelFacetProps = Panel2.PanelProps<typeof inputType, FacetConfig>;

const PanelFacetConfig: React.FC<PanelFacetProps> = props => {
  const {
    input,
    updateConfig: propsUpdateConfig,
    context,
    updateContext,
  } = props;

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

  const cellSelectFunction =
    tableConfig.columnSelectFunctions[config.dims.select];
  const cellNode = useMemo(
    () =>
      // Only use selected node if it's executable (has no voids...)
      // otherwise fall back to the props version.
      // TODO: this isn't really right
      HL.nodeIsExecutable(cellSelectFunction)
        ? TableState.getCellValueNode(input, cellSelectFunction)
        : Graph.voidNode(),
    [input, cellSelectFunction]
  );
  const cellPanel = tableConfig.columns[config.dims.select];
  const {
    handler: cellHandler,
    stackIds: cellPanelStackOptions,
    curPanelId: curCellPanelId,
  } = usePanelStacksForType(cellSelectFunction.type, cellPanel.panelId, {
    excludeTable: true,
  });
  console.log(
    'PANEL INFO',
    cellSelectFunction.type,
    cellPanel.panelId,
    cellPanelStackOptions,
    curCellPanelId
  );

  const updateCellPanelId = useCallback(
    (newPanelId: string) => {
      updateTableConfig(
        TableState.updateColumnPanelId(
          tableConfig,
          config.dims.select,
          newPanelId
        )
      );
    },
    [updateTableConfig, tableConfig, config.dims.select]
  );
  const updateCellPanelConfig = useCallback(
    (newConfig: any) => {
      updateTableConfig(
        TableState.updateColumnPanelConfig(
          tableConfig,
          config.dims.select,
          newConfig
        )
      );
    },
    [updateTableConfig, tableConfig, config.dims.select]
  );

  return (
    <div>
      <ConfigPanel.ConfigOption label={'x'}>
        <PanelPlot.DimConfig
          dimName="x"
          colId={config.dims.x}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'y'}>
        <PanelPlot.DimConfig
          dimName="y"
          colId={config.dims.y}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'cell'}>
        <PanelPlot.DimConfig
          dimName="select"
          colId={config.dims.select}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label="cell panel">
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          search
          options={cellPanelStackOptions.map(si => ({
            text: si.displayName,
            value: si.id,
          }))}
          value={curCellPanelId}
          onChange={(e, {value}) => updateCellPanelId(value as string)}
        />
        {cellSelectFunction.nodeType !== 'void' &&
          cellNode.nodeType !== 'void' &&
          cellHandler != null && (
            <S.PanelSettings>
              <PanelComp2
                input={cellNode}
                inputType={cellNode.type}
                loading={false}
                panelSpec={cellHandler}
                configMode={true}
                context={context}
                config={cellPanel.panelConfig}
                updateConfig={updateCellPanelConfig}
                updateContext={updateContext}
              />
            </S.PanelSettings>
          )}
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label="detail">
        <PanelPlot.DimConfig
          dimName="detail"
          colId={config.dims.detail}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
    </div>
  );
};

// TODO: make into a helper function (stole from paneltable2)

const SelectPanel: React.FC<{
  inputNode: Types.Node;
  selectFunction: Types.Node;
  panelId: string | undefined;
  config: any;
  panelContext: any;
  updateConfig(newConfig: any): void;
  updatePanelContext(newContext: any): void;
}> = makeComp(
  ({
    inputNode,
    selectFunction,
    panelId,
    config,
    panelContext,
    updateConfig,
    updatePanelContext,
  }) => {
    const selectedNode = useMemo(
      () => HL.callFunction(selectFunction, {row: inputNode}),
      [selectFunction, inputNode]
    );

    const {handler, curPanelId} = usePanelStacksForType(
      selectedNode.type,
      panelId,
      {excludeTable: true}
    );

    return curPanelId == null || handler == null ? (
      <div>No panel for type {Types.toString(selectFunction.type)}</div>
    ) : (
      <PanelComp2
        input={selectedNode}
        inputType={selectFunction.type}
        loading={false}
        panelSpec={handler}
        configMode={false}
        context={panelContext}
        config={config}
        updateConfig={updateConfig}
        updateContext={updatePanelContext}
      />
    );
  },
  {id: 'PanelFacetCell'}
);

const PanelFacetFlexMode: React.FC<PanelFacetProps> = props => {
  const {input} = props;
  const inputNode = input;

  const {frame} = usePanelContext();

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
    dims.x
  );

  const {
    rowsNode,
    // resultNode,
  } = useMemo(
    () => TableState.tableGetResultTableNode(table, inputNode, frame),
    [table, inputNode, frame]
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
        const picked = Op.opPick({
          obj: Op.opGroupGroupKey({obj: cellNode}) as any,
          key: Op.constString(xColName),
        });
        const cell = (
          <div key={i} style={{display: 'flex', marginRight: config.padding}}>
            <div style={{display: 'flex', marginRight: 4}}>
              {/* TODO Don't hard-code typeswitch here */}
              {picked.type === 'type' ? (
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

  const {frame} = usePanelContext();

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
  if (cellFunction.nodeType === 'void' || cellFunction.type === 'invalid') {
    // We check this in PanelFacet
    throw new Error('PanelFacetGridMode: invalid cell function');
  }

  const {
    rowsNode,
    // resultNode,
  } = useMemo(
    () => TableState.tableGetResultTableNode(table, inputNode, frame),
    [table, inputNode, frame]
  );

  // TODO: move into Table state
  const domainNode = useMemo(
    () =>
      Op.opMap({
        arr: rowsNode as any,
        mapFn: Op.defineFunction(
          {row: TableState.getExampleRow(rowsNode).type},
          ({row}) => HL.callFunction(cellFunction, {row})
        ) as any,
      }),
    [rowsNode, cellFunction]
  );
  const cellVars = useMemo(() => ({domain: domainNode}), [domainNode]);

  const groupKeysNode = Op.opMap({
    arr: rowsNode as any,
    mapFn: Op.defineFunction(
      {row: TableState.getExampleRow(rowsNode).type},
      ({row}) => Op.opGroupGroupKey({obj: row})
    ) as any,
  });
  const groupKeysUse = LLReact.useNodeValue(groupKeysNode as any);
  const cellNodesUse = LLReact.useEach(rowsNode as any);

  const xColName = TableState.getTableColumnName(
    table.columnNames,
    table.columnSelectFunctions,
    dims.x
  );
  const yColName = TableState.getTableColumnName(
    table.columnNames,
    table.columnSelectFunctions,
    dims.y
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
        (a, b) => Op.compareItems(a, b) * (sortXSetting.dir === 'asc' ? 1 : -1)
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
        (a, b) => Op.compareItems(a, b) * (sortYSetting.dir === 'asc' ? 1 : -1)
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
          const xKey = groupKey[xColName];
          const yKey = groupKey[yColName];
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
                }}>
                <PanelContextProvider newVars={cellVars}>
                  <SelectPanel
                    inputNode={cellNode}
                    selectFunction={cellFunction}
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

export const PanelFacet: React.FC<PanelFacetProps> = props => {
  const config = useConfig(props.config);
  const {table, dims} = config;

  const xEnabled = table.columnSelectFunctions[dims.x].type !== 'invalid';
  const cellEnabled =
    table.columnSelectFunctions[dims.select].type !== 'invalid';
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

export const Spec: Panel2.PanelSpec = {
  id: 'facet',
  ConfigComponent: PanelFacetConfig,
  Component: PanelFacet,
  inputType,
};
