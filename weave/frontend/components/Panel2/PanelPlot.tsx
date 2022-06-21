import * as _ from 'lodash';
import React, {useContext, useEffect} from 'react';
import ReactDOM from 'react-dom';
import {useState} from 'react';
import {useMemo, useCallback, useRef} from 'react';
import {Button, Checkbox} from 'semantic-ui-react';
import {calculatePosition} from 'vega-tooltip';
import {PanelComp2, Panel2Loader} from './PanelComp';
import * as Panel2 from './panel';
import * as Types from '@wandb/cg/browser/model/types';
import * as CG from '@wandb/cg/browser/graph';
import * as Op from '@wandb/cg/browser/ops';
import * as Code from '@wandb/cg/browser/code';
import * as LLReact from '@wandb/common/cgreact';
import * as TableState from './PanelTable/tableState';
import {getPanelStacksForType, getPanelStackDims} from './availablePanels';
import * as PlotState from './plotState';
import {VisualizationSpec} from 'react-vega';
import CustomPanelRenderer from '@wandb/common/components/Vega3/CustomPanelRenderer';
import {usePanelContext} from './PanelContext';
import {ActivityDashboardContext} from '@wandb/common/components/ActivityDashboardContext';
import {useTableStateWithRefinedExpressions} from './PanelTable/tableStateReact';
import {escapeDots} from '@wandb/cg/browser/ops';
import {Loader as SemanticLoader} from 'semantic-ui-react';
import WandbLoader from '@wandb/common/components/WandbLoader';
import {allObjPaths} from '@wandb/cg/browser/model/typeHelpers';
import * as TableType from './PanelTable/tableType';
import {makeEventRecorder} from './panellib/libanalytics';
import * as ConfigPanel from './ConfigPanel';
import PanelError from '@wandb/common/components/elements/PanelError';
import * as globals from '@wandb/common/css/globals.styles';
import {RepoInsightsDashboardContext} from '@wandb/common/components/RepoInsightsDashboardContext';
import {useGatedValue} from '@wandb/common/state/hooks';

type Awaited<T> = T extends Promise<infer U> ? U : T;

const recordEvent = makeEventRecorder('Plot');

const inputType = TableType.GeneralTableLikeType;

const defaultFontStyleDict = {
  titleFont: 'Source Sans Pro',
  titleFontWeight: 'normal',
  titleColor: globals.gray900,
  labelFont: 'Source Sans Pro',
  labelFontWeight: 'normal',
  labelColor: globals.gray900,
  labelSeparation: 5,
};

function defaultPlot(
  inputNode: Types.Node,
  frame: Code.Frame
): PlotState.PlotConfig {
  const exampleRow = TableState.getExampleRow(inputNode);

  let tableState = TableState.emptyTable();
  tableState = TableState.appendEmptyColumn(tableState);
  const xColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const yColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const colorColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const labelColId = tableState.order[tableState.order.length - 1];
  tableState = TableState.appendEmptyColumn(tableState);
  const tooltipColId = tableState.order[tableState.order.length - 1];

  const axisSettings: PlotState.PlotConfig['axisSettings'] = {
    x: {},
    y: {},
  };
  const legendSettings: PlotState.PlotConfig['legendSettings'] = {
    color: {},
  };

  let labelAssigned = false;
  if (
    frame.runColors != null &&
    frame.runColors.nodeType === 'const' &&
    Object.keys(frame.runColors.val).length > 1
  ) {
    if (
      Types.isAssignableTo(
        exampleRow.type,
        Types.withNamedTag('run', 'run', 'any')
      )
    ) {
      tableState = TableState.updateColumnSelect(
        tableState,
        labelColId,
        Op.opGetRunTag({obj: CG.varNode(exampleRow.type, 'row')})
      );
      labelAssigned = true;
    } else if (Types.isAssignableTo(exampleRow.type, 'run')) {
      tableState = TableState.updateColumnSelect(
        tableState,
        labelColId,
        CG.varNode(exampleRow.type, 'row')
      );
      labelAssigned = true;
    }
  }

  // If we have a list of dictionaries, try to make a good guess at filling in the dimensions
  if (Types.isAssignableTo(exampleRow.type, Types.typedDict({}))) {
    const propertyTypes = allObjPaths(
      Types.nullableTaggableValue(exampleRow.type)
    );
    let xCandidate: string | null = null;
    let yCandidate: string | null = null;
    let labelCandidate: string | null = null;
    let mediaCandidate: string | null = null;
    // Assign the first two numeric columns to x an y if available
    for (const propertyKey of propertyTypes) {
      if (Types.isAssignableTo(propertyKey.type, Types.maybe('number'))) {
        if (xCandidate == null) {
          xCandidate = propertyKey.path.join('.');
        } else if (yCandidate == null) {
          yCandidate = propertyKey.path.join('.');
        }
      } else if (
        Types.isAssignableTo(propertyKey.type, Types.maybe('string'))
      ) {
        // don't default to the run name field
        if (
          labelCandidate == null &&
          propertyKey.path.indexOf('runname') === -1
        ) {
          labelCandidate = propertyKey.path.join('.');
        }
      } else if (
        mediaCandidate == null &&
        Types.isAssignableTo(
          propertyKey.type,
          Types.maybe(
            Types.union([
              {type: 'image-file'},
              {type: 'video-file'},
              {type: 'audio-file'},
              {type: 'html-file'},
              {type: 'bokeh-file'},
              {type: 'object3D-file'},
              {type: 'molecule-file'},
            ])
          )
        )
      ) {
        mediaCandidate = propertyKey.path.join('.');
      }
    }

    if (xCandidate != null && yCandidate != null) {
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        Op.opPick({
          obj: CG.varNode(exampleRow.type, 'row'),
          key: Op.constString(xCandidate),
        })
      );

      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        Op.opPick({
          obj: CG.varNode(exampleRow.type, 'row'),
          key: Op.constString(yCandidate),
        })
      );

      if (labelCandidate != null && !labelAssigned) {
        tableState = TableState.updateColumnSelect(
          tableState,
          labelColId,
          Op.opPick({
            obj: CG.varNode(exampleRow.type, 'row'),
            key: Op.constString(labelCandidate),
          })
        );
      }

      if (mediaCandidate != null) {
        tableState = TableState.updateColumnSelect(
          tableState,
          tooltipColId,
          Op.opPick({
            obj: CG.varNode(exampleRow.type, 'row'),
            key: Op.constString(mediaCandidate),
          })
        );
      }
    }
  }

  // If we have an array of number, default to a scatter plot
  // by index (for the moment).
  if (Types.isAssignableTo(inputNode.type, Types.list(Types.maybe('number')))) {
    if (frame.domain != null) {
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        Op.opNumberBin({
          in: CG.varNode(exampleRow.type, 'row') as any,
          binFn: Op.opNumbersBinEqual({
            arr: CG.varNode(Types.list('number'), 'domain') as any,
            bins: Op.constNumber(10),
          }),
        }) as any
      );
      tableState = {...tableState, groupBy: [xColId]};
      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        Op.opCount({arr: CG.varNode(Types.list(exampleRow.type), 'row') as any})
      );
      axisSettings.x = {
        noTitle: true,
      };
      axisSettings.y = {
        noTitle: true,
      };
      legendSettings.color = {
        noLegend: true,
      };
    } else if (
      Types.isAssignableTo(
        inputNode.type,
        Types.list(
          Types.taggedValue(
            Types.typedDict({run: 'run'}),
            Types.maybe('number')
          )
        )
      )
    ) {
      tableState = TableState.updateColumnSelect(
        tableState,
        yColId,
        Op.opRunName({
          run: Op.opGetRunTag({obj: CG.varNode(exampleRow.type, 'row')}),
        })
      );
      tableState = TableState.updateColumnSelect(
        tableState,
        xColId,
        CG.varNode(exampleRow.type, 'row')
      );
    }
  }

  // If we have an array of string, default to a histogram configuration
  if (
    Types.isAssignableTo(inputNode.type, Types.list(Types.maybe('string'))) &&
    frame.domain != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      CG.varNode(exampleRow.type, 'row')
    );
    tableState = {...tableState, groupBy: [yColId]};
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      Op.opCount({arr: CG.varNode(Types.list(exampleRow.type), 'row') as any})
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  // If we have an dict of number, default to a bar chart configuration
  if (
    Types.isAssignableTo(inputNode.type, Types.dict(Types.maybe('number'))) &&
    frame.domain != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      CG.varNode('string', 'key')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      CG.varNode(exampleRow.type, 'row')
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  // If we have an dict of array of number, default to a boxplot
  // (note this is calculated on the frontend currently. TODO fix)
  if (
    Types.isAssignableTo(
      inputNode.type,
      Types.dict(Types.list(Types.maybe('number')))
    ) &&
    frame.domain != null
  ) {
    tableState = TableState.updateColumnSelect(
      tableState,
      yColId,
      CG.varNode('string', 'key')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      xColId,
      CG.varNode(exampleRow.type, 'row')
    );
    tableState = TableState.updateColumnSelect(
      tableState,
      colorColId,
      CG.varNode('string', 'key')
    );
    axisSettings.x = {
      noTitle: true,
    };
    axisSettings.y = {
      noTitle: true,
    };
    legendSettings.color = {
      noLegend: true,
    };
  }

  // If we have an dict of array of string, default to a multi-histogram.
  // Doesn't work yet, types are f'd because PanelPlot handles input
  // dict but tableState group by array case probably doesn't.
  // if (
  //   Types.isAssignableTo(
  //     inputNode.type,
  //     Types.dict(Types.list(Types.maybe('string')))
  //   ) &&
  //   frame.domain != null
  // ) {
  //   tableState = TableState.updateColumnSelect(
  //     tableState,
  //     yColId,
  //     CG.varNode(exampleRow.type, 'row')
  //   );
  //   tableState = TableState.updateColumnSelect(
  //     tableState,
  //     xColId,
  //     Op.opCount({
  //       arr: CG.varNode(Types.list(exampleRow.type), 'row') as any,
  //     })
  //   );
  //   tableState = TableState.updateColumnSelect(
  //     tableState,
  //     colorColId,
  //     CG.varNode('string', 'key')
  //   );
  //   tableState = {...tableState, groupBy: [yColId, colorColId]};
  //   axisSettings.x = {
  //     noTitle: true,
  //   };
  //   axisSettings.y = {
  //     noTitle: true,
  //   };
  //   legendSettings.color = {
  //     noLegend: true,
  //   };
  // }

  return {
    table: tableState,
    dims: {
      x: xColId,
      y: yColId,
      color: colorColId,
      label: labelColId,
      tooltip: tooltipColId,
    },
    axisSettings,
    legendSettings,
  };
}

const useConfig = (
  inputNode: Types.Node,
  propsConfig?: PlotState.PlotConfig
): {config: PlotState.PlotConfig; isRefining: boolean} => {
  const {frame} = usePanelContext();

  const newConfig = useMemo(() => {
    // TODO: (ts) Should reset config when the incoming type changes (similar to table - maybe a common refactor?)
    let config =
      propsConfig == null || propsConfig.dims == null
        ? defaultPlot(inputNode, frame)
        : propsConfig;
    if (
      config.axisSettings == null ||
      config.axisSettings.x == null ||
      config.axisSettings.y == null
    ) {
      config = {
        ...config,
        axisSettings: {
          x: {},
          y: {},
        },
      };
    }
    if (config.legendSettings == null || config.legendSettings.color == null) {
      config = {
        ...config,
        legendSettings: {
          color: {},
        },
      };
    }
    return config;
  }, [propsConfig, inputNode, frame]);

  const {tableState: refinedTableState, isRefining} =
    useTableStateWithRefinedExpressions(inputNode, newConfig.table);
  return useMemo(() => {
    return {
      config: {
        ...newConfig,
        table: refinedTableState,
      },
      isRefining,
    };
  }, [isRefining, newConfig, refinedTableState]);
};

type PanelPlotProps = Panel2.PanelProps<typeof inputType, PlotState.PlotConfig>;

export const DimConfig: React.FC<{
  dimName: string;
  input: PanelPlotProps['input'];
  colId: TableState.ColumnId;
  // Hack: you can pass an extra colID to include in when grouping is
  // toggled for this dim. This is used to toggle grouping for color/label
  // together.
  extraGroupColId?: string;
  tableConfig: TableState.TableState;
  updateTableConfig: (newTableState: TableState.TableState) => void;
}> = props => {
  const {colId, tableConfig, input, updateTableConfig} = props;

  const inputNode = input;

  const updateDim = useCallback(
    (node: Types.Node) => {
      updateTableConfig(
        TableState.updateColumnSelect(tableConfig, colId, node)
      );
    },
    [updateTableConfig, tableConfig, colId]
  );

  const {frame} = usePanelContext();
  const {rowsNode} = useMemo(
    () => TableState.tableGetResultTableNode(tableConfig, inputNode, frame),
    [tableConfig, inputNode, frame]
  );
  const cellFrame = useMemo(
    () =>
      TableState.getCellFrame(
        inputNode,
        rowsNode,
        frame,
        tableConfig.groupBy,
        tableConfig.columnSelectFunctions,
        colId
      ),
    [
      colId,
      inputNode,
      rowsNode,
      frame,
      tableConfig.columnSelectFunctions,
      tableConfig.groupBy,
    ]
  );

  const enableGroup = LLReact.useClientBound(TableState.enableGroupByCol);
  const enableGroupBy = useCallback(async () => {
    const newTableState = await enableGroup(
      tableConfig,
      colId,
      input,
      cellFrame
    );
    updateTableConfig(newTableState);
  }, [enableGroup, tableConfig, colId, input, cellFrame, updateTableConfig]);

  const disableGroup = LLReact.useClientBound(TableState.disableGroupByCol);
  const disableGroupBy = useCallback(async () => {
    const newTableState = await disableGroup(
      tableConfig,
      colId,
      input,
      cellFrame
    );
    updateTableConfig(newTableState);
  }, [disableGroup, tableConfig, colId, input, cellFrame, updateTableConfig]);

  const colIsGrouped = tableConfig.groupBy.includes(colId);
  const colSelectFunction = tableConfig.columnSelectFunctions[colId];

  const getUngroupedSelectFunction = LLReact.useClientBound(
    TableState.getUngroupedSelectFunction
  );
  const [ungroupedColType, setUngroupedColType] =
    useState<Types.Type>('invalid');
  useEffect(() => {
    setUngroupedColType('invalid');
    getUngroupedSelectFunction(input, frame, colSelectFunction).then(node => {
      setUngroupedColType(node.type);
    });
  }, [colSelectFunction, frame, getUngroupedSelectFunction, input]);

  return (
    <>
      <ConfigPanel.ExpressionConfigField
        frame={cellFrame}
        node={tableConfig.columnSelectFunctions[colId]}
        updateNode={updateDim}
      />
      <ConfigPanel.ConfigOption label="group">
        {!colIsGrouped ? (
          <Checkbox
            toggle
            checked={false}
            disabled={!Types.canGroupType(ungroupedColType)}
            onChange={enableGroupBy}
          />
        ) : (
          <Checkbox toggle checked={true} onChange={disableGroupBy} />
        )}
      </ConfigPanel.ConfigOption>
    </>
  );
};

export const SimpleDimConfig: React.FC<{
  input: PanelPlotProps['input'];
  colId: TableState.ColumnId;
  tableConfig: TableState.TableState;
  updateTableConfig: (newTableState: TableState.TableState) => void;
}> = props => {
  const {colId, tableConfig, input, updateTableConfig} = props;

  const inputNode = input;
  const {frame} = usePanelContext();

  const updateDim = useCallback(
    (node: Types.Node) => {
      updateTableConfig(
        TableState.updateColumnSelect(tableConfig, colId, node)
      );
    },
    [updateTableConfig, tableConfig, colId]
  );

  const {rowsNode} = useMemo(
    () => TableState.tableGetResultTableNode(tableConfig, inputNode, frame),
    [tableConfig, inputNode, frame]
  );
  const cellFrame = useMemo(
    () =>
      TableState.getCellFrame(
        inputNode,
        rowsNode,
        {},
        tableConfig.groupBy,
        tableConfig.columnSelectFunctions,
        colId
      ),
    [
      colId,
      inputNode,
      rowsNode,
      tableConfig.columnSelectFunctions,
      tableConfig.groupBy,
    ]
  );

  return (
    <ConfigPanel.ExpressionConfigField
      frame={cellFrame}
      node={tableConfig.columnSelectFunctions[colId]}
      updateNode={updateDim}
    />
  );
};

export const AxisConfig: React.FC<{
  dimName: string;
  axisSettings: PlotState.AxisSetting;
  updateAxisSettings: (
    dimName: string,
    newAxisSettings: Partial<PlotState.AxisSetting>
  ) => void;
}> = props => {
  const {axisSettings, dimName, updateAxisSettings} = props;

  return (
    <div
      style={{
        display: 'flex',
        marginTop: 8,
        alignItems: 'center',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
      <div>Title</div>
      <Checkbox
        style={{marginLeft: 8}}
        checked={!axisSettings.noTitle}
        name={`showlabel-${dimName}`}
        onChange={(e, value) => {
          updateAxisSettings(dimName, {
            noTitle: !value.checked,
          });
        }}
      />
      <div style={{marginLeft: 16}}>Labels</div>
      <Checkbox
        style={{marginLeft: 8}}
        checked={!axisSettings.noLabels}
        name={`showlabel-${dimName}`}
        onChange={(e, value) => {
          updateAxisSettings(dimName, {
            noLabels: !value.checked,
          });
        }}
      />
      <div style={{marginLeft: 16}}>Ticks</div>
      <Checkbox
        style={{marginLeft: 8}}
        checked={!axisSettings.noTicks}
        name={`showlabel-${dimName}`}
        onChange={async (e, value) => {
          updateAxisSettings(dimName, {
            noTicks: !value.checked,
          });
        }}
      />
    </div>
  );
};

export const LegendConfig: React.FC<{
  dimName: string;
  legendSettings: PlotState.LegendSetting;
  updateLegendSettings: (
    dimName: string,
    newLegendSettings: Partial<PlotState.LegendSetting>
  ) => void;
}> = props => {
  const {legendSettings, dimName, updateLegendSettings} = props;

  return (
    <div
      style={{
        display: 'flex',
        marginTop: 8,
        alignItems: 'center',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
      Legend
      <Checkbox
        style={{marginLeft: 8}}
        checked={!legendSettings.noLegend}
        name={`showlabel-${dimName}`}
        onChange={(e, value) => {
          updateLegendSettings(dimName, {
            noLegend: !value.checked,
          });
        }}
      />
    </div>
  );
};

const PanelPlotConfig: React.FC<PanelPlotProps> = props => {
  const {input} = props;

  const inputNode = useMemo(() => TableType.normalizeTableLike(input), [input]);
  const typedInputNodeUse = LLReact.useNodeWithServerType(inputNode);
  const newProps = useMemo(() => {
    return {
      ...props,
      input: typedInputNodeUse.result as any,
    };
  }, [props, typedInputNodeUse.result]);

  const isRepoInsightsDash =
    Object.keys(useContext(RepoInsightsDashboardContext).frame).length > 0;
  const loaderComp = isRepoInsightsDash ? (
    <SemanticLoader active inline className="cgLoader" />
  ) : (
    <WandbLoader />
  );

  if (typedInputNodeUse.loading) {
    return loaderComp;
  } else if (typedInputNodeUse.result.nodeType === 'void') {
    return <></>;
  } else {
    return <PanelPlotConfigInner {...newProps} />;
  }
};

const PanelPlotConfigInner: React.FC<PanelPlotProps> = props => {
  const {input, updateConfig: propsUpdateConfig} = props;

  const inputNode = input;

  const {config} = useConfig(inputNode, props.config);

  const resetConfig = useCallback(() => {
    propsUpdateConfig({dims: undefined});
  }, [propsUpdateConfig]);

  const updateConfig = useCallback(
    (newConfig: Partial<PlotState.PlotConfig>) => {
      propsUpdateConfig({
        ...config,
        ...newConfig,
      });
    },
    [config, propsUpdateConfig]
  );

  const tableConfig = config.table;
  const updateTableConfig = useCallback(
    (newTableConfig: TableState.TableState) => {
      updateConfig({
        table: newTableConfig,
      });
    },
    [updateConfig]
  );

  return (
    <>
      <ConfigPanel.ConfigOption label={'X Dim'} data-test="x-dim-config">
        <DimConfig
          dimName="x"
          colId={config.dims.x}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Y Dim'} data-test="y-dim-config">
        <DimConfig
          dimName="y"
          colId={config.dims.y}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Label'} data-test="label-dim-config">
        <DimConfig
          dimName="label"
          colId={config.dims.label}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption
        label={'Tooltip'}
        data-test="tooltip-dim-config">
        <DimConfig
          dimName="tooltip"
          colId={config.dims.tooltip}
          input={input}
          tableConfig={tableConfig}
          updateTableConfig={updateTableConfig}
        />
      </ConfigPanel.ConfigOption>
      <ConfigPanel.ConfigOption label={'Mark'} data-test="mark-dim-config">
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          placeholder="auto"
          value={config.mark}
          options={(
            [
              {
                key: 'auto',
                value: null,
                text: 'auto',
              },
            ] as any
          ).concat(
            PlotState.MARK_OPTIONS.map(o => ({
              key: o,
              value: o,
              text: o,
            }))
          )}
          onChange={(e, {value}) =>
            updateConfig({mark: value as PlotState.MarkOption})
          }
        />
      </ConfigPanel.ConfigOption>
      <Button size="tiny" onClick={resetConfig}>
        {'Reset & Automate Plot'}
      </Button>
    </>
  );
};

const useLoader = () => {
  const isRepoInsightsDash =
    Object.keys(useContext(RepoInsightsDashboardContext).frame).length > 0;
  return isRepoInsightsDash ? (
    <SemanticLoader active inline className="cgLoader" />
  ) : (
    <WandbLoader />
  );
};

const PanelPlot2: React.FC<PanelPlotProps> = props => {
  const {input} = props;

  const inputNode = useMemo(() => TableType.normalizeTableLike(input), [input]);
  const typedInputNodeUse = LLReact.useNodeWithServerType(inputNode);
  const newProps = useMemo(() => {
    return {
      ...props,
      input: typedInputNodeUse.result as any,
    };
  }, [props, typedInputNodeUse.result]);

  const loaderComp = useLoader();

  if (typedInputNodeUse.loading) {
    return loaderComp;
  } else if (typedInputNodeUse.result.nodeType === 'void') {
    return <></>;
  } else {
    return <PanelPlot2ConfigBarrier {...newProps} />;
  }
};

const PanelPlot2ConfigBarrier: React.FC<PanelPlotProps> = props => {
  const {config, isRefining} = useConfig(props.input, props.config);
  const loaderComp = useLoader();
  if (isRefining) {
    return loaderComp;
  }
  return <PanelPlot2Inner {...props} config={config} />;
};

const stringIsColorLike = (val: string): boolean => {
  return (
    val.match('^#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$') != null || // matches hex code
    (val.startsWith('rgb(') && val.endsWith(')')) || // rgb
    (val.startsWith('hsl(') && val.endsWith(')')) // hsl
  );
};

const useVegaReadyTable = (
  table: TableState.TableState,
  dims: PlotState.PlotConfig['dims'],
  frame: Code.Frame
) => {
  // This function assigns smart defaults for the color of a point based on the label.
  return useMemo(() => {
    const labelSelectFn = table.columnSelectFunctions[dims.label];
    if (labelSelectFn.nodeType !== 'void') {
      const labelType = TableState.getTableColType(table, dims.label);
      if (frame.runColors != null) {
        if (Types.isAssignableTo(labelType, Types.maybe('run'))) {
          let retTable = TableState.updateColumnSelect(
            table,
            dims.color,
            Op.opPick({
              obj: CG.varNode(frame.runColors.type, 'runColors'),
              key: Op.opRunId({
                run: labelSelectFn,
              }),
            })
          );

          retTable = TableState.updateColumnSelect(
            retTable,
            dims.label,
            Op.opRunName({
              run: labelSelectFn,
            })
          );

          return retTable;
        } else if (
          labelSelectFn.nodeType === 'output' &&
          labelSelectFn.fromOp.name === 'run-name'
        ) {
          return TableState.updateColumnSelect(
            table,
            dims.color,
            Op.opPick({
              obj: CG.varNode(frame.runColors.type, 'runColors'),
              key: Op.opRunId({
                run: labelSelectFn.fromOp.inputs.run,
              }),
            })
          );
        }
      }

      if (
        Types.isAssignableTo(
          labelType,
          Types.oneOrMany(
            Types.maybe(Types.union(['number', 'string', 'boolean']))
          )
        )
      ) {
        return TableState.updateColumnSelect(table, dims.color, labelSelectFn);
      }
    }
    return table;
  }, [table, dims, frame.runColors]);
};

const PanelPlot2Inner: React.FC<
  PanelPlotProps & {config: NonNullable<PanelPlotProps['config']>}
> = props => {
  const {input, updateConfig} = props;

  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  // TODO(np): Hack to detect when we are on an activity dashboard
  const isOrgDashboard =
    Object.keys(useContext(ActivityDashboardContext).frame).length > 0;

  const isRepoInsightsDashboard =
    Object.keys(useContext(RepoInsightsDashboardContext).frame).length > 0;

  const isDashboard = isOrgDashboard || isRepoInsightsDashboard;

  const inputNode = input;
  const {frame} = usePanelContext();

  const config = props.config;
  const {table, dims} = config;
  const vegaReadyTable = useVegaReadyTable(table, dims, frame);
  const vegaCols = useMemo(
    () => PlotState.dimNames(vegaReadyTable, dims),
    [vegaReadyTable, dims]
  );

  const {resultNode} = useMemo(
    () => TableState.tableGetResultTableNode(vegaReadyTable, inputNode, frame),
    [vegaReadyTable, inputNode, frame]
  );

  const flatResultNode = useMemo(
    () => Op.opUnnest({arr: resultNode as any}),
    [resultNode]
  );
  const result = LLReact.useNodeValue(flatResultNode);
  const plotTable = useMemo(
    () => (result.loading ? [] : (result.result as any[])),
    [result]
  );
  const flatPlotTable = useMemo(() => {
    return plotTable.map((row, index) => {
      const newRow = _.mapKeys(row, (v, k) => PlotState.fixKeyForVega(k));
      return newRow;
    });
  }, [plotTable]);

  // If the color field can actually be interpreted as a color
  // then consider it a range, else we should use the default
  // color scheme from vega.
  const colorFieldIsRange = useMemo(() => {
    for (const row of flatPlotTable) {
      if (row[vegaCols.color] != null) {
        return stringIsColorLike(String(row[vegaCols.color]));
      }
    }
    return false;
  }, [vegaCols.color, flatPlotTable]);

  // If the color field is not a range but contains data values, enumerate
  // those values for later use in a custom tooltip.
  const colorFieldValues = useMemo(() => {
    const colorValues = new Set<string>();
    for (const row of flatPlotTable) {
      if (row[vegaCols.color] != null) {
        colorValues.add(String(row[vegaCols.color]));
      }
    }
    return Array.from(colorValues);
  }, [vegaCols.color, flatPlotTable]);

  const labelFieldValues = useMemo(() => {
    const labelValues = new Set<string>();
    for (const row of flatPlotTable) {
      if (row[vegaCols.label] != null) {
        labelValues.add(String(row[vegaCols.label]));
      }
    }
    return Array.from(labelValues);
  }, [vegaCols.label, flatPlotTable]);

  const dimTypes = useMemo(
    () =>
      _.mapValues(dims, colId =>
        TableState.getTableColType(vegaReadyTable, colId)
      ),
    [dims, vegaReadyTable]
  );

  const axisTypes = useMemo(
    () =>
      _.mapValues(dimTypes, dimType =>
        PlotState.axisType(dimType, isDashboard)
      ),
    [dimTypes, isDashboard]
  );

  // Playing with automatic ranges set from column domain
  // OK so we have:
  // PanelFacet:
  //    table.groupBy('x', 'y')
  //    .select(PanelPlot())
  //    PanelPlot
  //
  // Hmm..
  // t = table.groupby('x', 'y', 'run').count()
  // PanelFacet(t, {
  //   'x': lambda row['x'],
  //   'y': lambda row['y'],
  //   'cell': PanelPlot(config={
  //      'y': row['run'],
  //      'x': row['count']
  //   })
  // The issue with this is I have to know ahead of time that I want to group by run
  //
  // What I want is this:
  // PanelFacet(table, {
  //   'x': lambda row['x'],
  //   'y': lambda row['y'],
  //   'cell': lambda cell: PanelPlot(cell, config={
  //      'y': lambda cell: cell['run'],
  //      'group_y': true,
  //      'x': lambda cell: cell.count()
  //   })
  // This allows me to think "from outside-in" which is what I'm shooting for. It gives you the
  // most emergent types of behaviors. You can say "Oh what's this Facet?", and then try it,
  // and then mess around with its inner plot only, without having come back "to the outside".
  //
  // But can we get rid of all the redundant lambda weaving above? That would make the code
  // much cleaner?

  // const domainExampleRow = TableState.getExampleRow(frame.domain);
  // const xDomainNode = useMemo(() => {
  //   return Op.opFlatten({
  //     arr: Op.opMap({
  //       arr: frame.domain as any,
  //       mapFn: Op.defineFunction({row: domainExampleRow.type}, ({row}) =>
  //         Op.opMap({
  //           arr: row,
  //           mapFn: Op.defineFunction(
  //             {row: TableState.getExampleRow(domainExampleRow).type},
  //             ({row}) => Op.opCount({arr: row})
  //           ) as any,
  //         })
  //       ) as any,
  //     }) as any,
  //   });
  // }, [frame.domain]);
  // console.log('xDomainNode', LLReact.useNodeValue(xDomainNode));

  const getColumnRangesNodes = LLReact.useClientBound(
    TableState.getColumnDomainRanges
  );
  const [colRangesNodes, setColRangesNodes] = useState<
    Awaited<ReturnType<typeof getColumnRangesNodes>> | undefined
  >();
  useEffect(() => {
    setColRangesNodes(undefined);
    getColumnRangesNodes(table, input, frame).then(res => {
      setColRangesNodes(res);
    });
  }, [getColumnRangesNodes, frame, input, table]);
  const colRangesResult = LLReact.useNodeValue(
    colRangesNodes != null ? colRangesNodes.executableRangesNode : CG.voidNode()
  );
  const colRangesLoading =
    colRangesNodes == null ||
    (colRangesNodes.executableRangesNode.nodeType !== 'void' &&
      colRangesResult.loading);

  // Sadly this is going to be a bit tricky
  // Need to call selectFunction on domain
  // But calling a function is tricky because presumably we need to refine
  // all the types...

  const vegaSpec = useMemo(() => {
    let newSpec = _.merge(
      isDashboard
        ? _.omit(_.cloneDeep(PLOT_TEMPLATE), ['params'])
        : _.cloneDeep(PLOT_TEMPLATE),
      isOrgDashboard ? _.cloneDeep(ORG_DASHBOARD_TEMPLATE_OVERLAY) : {},
      config?.vegaOverlay ?? {}
    );

    const objType = Types.listObjectType(resultNode.type);
    if (objType == null || objType === 'invalid') {
      return newSpec;
    }
    if (!Types.isTypedDict(objType)) {
      throw new Error('Invalid plot data type');
    }

    const mark: PlotState.MarkOption = PlotState.markType(
      dimTypes.x,
      dimTypes.y
    );

    if (axisTypes.x != null) {
      if (Types.isAssignableTo2(dimTypes.x, Types.numberBin)) {
        newSpec.encoding.x = {
          field: vegaCols.x + '.start',
          type: axisTypes.x.axisType,
        };
        newSpec.encoding.x2 = {
          field: vegaCols.x + '.stop',
          type: axisTypes.x.axisType,
        };
      } else {
        newSpec.encoding.x = {
          field: vegaCols.x,
          type: axisTypes.x.axisType,
        };
      }
      if (axisTypes.x.axisType === 'temporal' && axisTypes.x.timeUnit) {
        newSpec.encoding.x.timeUnit = axisTypes.x.timeUnit;
      }
    }
    if (axisTypes.y != null) {
      if (Types.isAssignableTo2(dimTypes.y, Types.numberBin)) {
        newSpec.encoding.y = {
          field: vegaCols.y + '.start',
          type: axisTypes.y.axisType,
        };
        newSpec.encoding.y2 = {
          field: vegaCols.y + '.stop',
          type: axisTypes.y.axisType,
        };
      } else {
        newSpec.encoding.y = {
          field: vegaCols.y,
          type: axisTypes.y.axisType,
        };
        if (axisTypes.y.axisType === 'temporal' && axisTypes.y.timeUnit) {
          newSpec.encoding.y.timeUnit = axisTypes.y.timeUnit;
        }
      }
    }
    if (axisTypes.color != null) {
      newSpec.encoding.color = {
        field: vegaCols.color,
        type: axisTypes.color.axisType,
      };
      if (vegaReadyTable.columnSelectFunctions[dims.label].type !== 'invalid') {
        newSpec.encoding.color.field = vegaCols.label;
        if (colorFieldIsRange) {
          newSpec.encoding.color.scale = {
            range: {
              field: vegaCols.color,
            },
          };
        }
      }
    }
    newSpec.mark.type = config.mark ?? mark;
    if (newSpec.mark.type === 'point') {
      newSpec.mark.filled = true;
    }

    const {axisSettings, legendSettings} = config;
    if (newSpec.encoding.x != null) {
      if (newSpec.encoding.x.axis == null) {
        // TODO(np): fixme (Applied on org dash only)
        newSpec.encoding.x.axis = isDashboard
          ? {
              format: '%m/%d/%y',
              grid: false,
              ...defaultFontStyleDict,
            }
          : {...defaultFontStyleDict};
      }
      // TODO(np): fixme
      if (axisSettings.x.scale != null) {
        newSpec.encoding.x.scale = axisSettings.x.scale;
      }
      if (axisSettings.x.noTitle) {
        newSpec.encoding.x.axis.title = null;
      }
      if (axisSettings.x.title != null) {
        newSpec.encoding.x.axis.title = axisSettings.x.title;
      }
      if (axisSettings.x.noLabels) {
        newSpec.encoding.x.axis.labels = false;
      }
      if (axisSettings.x.noTicks) {
        newSpec.encoding.x.axis.ticks = false;
      }
      if (
        axisSettings.x.noTitle &&
        axisSettings.x.noLabels &&
        axisSettings.x.noTicks
      ) {
        newSpec.encoding.x.axis = false;
      }
    }
    if (newSpec.encoding.y != null) {
      if (newSpec.encoding.y.axis == null) {
        newSpec.encoding.y.axis = {...defaultFontStyleDict};
      }
      // TODO(np): fixme
      if (axisSettings.y.scale != null) {
        newSpec.encoding.y.scale = axisSettings.y.scale;
      }
      if (axisSettings.y.noTitle) {
        newSpec.encoding.y.axis.title = null;
      }
      if (axisSettings.y.title != null) {
        newSpec.encoding.y.axis.title = axisSettings.y.title;
      }
      if (axisSettings.y.noLabels) {
        newSpec.encoding.y.axis.labels = false;
      }
      if (axisSettings.y.noTicks) {
        newSpec.encoding.y.axis.ticks = false;
      }
      if (
        axisSettings.y.noTitle &&
        axisSettings.y.noLabels &&
        axisSettings.y.noTicks
      ) {
        newSpec.encoding.y.axis = false;
      }

      if (
        axisSettings.y.noTitle &&
        axisSettings.y.noLabels &&
        axisSettings.y.noTicks
      ) {
        newSpec.encoding.y.axis = false;
      }
    }

    if (newSpec.encoding.color != null) {
      if (axisSettings?.color?.scale) {
        newSpec.encoding.color.scale = axisSettings.color.scale;
      }

      if (axisSettings.color && axisSettings.color.title != null) {
        newSpec.encoding.color.title = axisSettings.color.title;
      }

      if (legendSettings.color.noLegend) {
        newSpec.encoding.color.legend = false;
      } else if (!newSpec.encoding.color.legend) {
        newSpec.encoding.color.legend = {...defaultFontStyleDict};
      }

      if (newSpec.mark.type === 'line' && !newSpec.encoding.tooltip) {
        const tooltipValues: Array<{field: string; type: string}> = [];
        if (isRepoInsightsDashboard) {
          for (const colorFieldValue of colorFieldValues) {
            tooltipValues.push({
              field: colorFieldValue,
              type: 'quantitative',
            });
          }
        } else {
          for (const labelFieldValue of labelFieldValues) {
            tooltipValues.push({
              field: labelFieldValue,
              type: 'quantitative',
            });
          }
        }

        const xToolTipValue: {
          field: string;
          type: string;
          format?: string;
        } = {
          field: newSpec.encoding.x.field,
          type: newSpec.encoding.x.type,
        };

        if (
          newSpec.encoding.x.type === 'temporal' &&
          Types.isAssignableTo(
            dimTypes.x,
            Types.oneOrMany(Types.maybe({type: 'timestamp', unit: 'ms'}))
          )
        ) {
          xToolTipValue.format = '%B %d, %Y %X';
        }

        tooltipValues.push(xToolTipValue);

        const mergeSpec = {
          layer: [
            {
              encoding: {
                color: newSpec.encoding.color,
                y: newSpec.encoding.y,
              },
              layer: [
                {mark: 'line'},
                {
                  transform: [{filter: {param: 'hover', empty: false}}],
                  mark: 'point',
                  params: [
                    {
                      name: 'grid',
                      select: 'interval',
                      bind: 'scales',
                    },
                  ],
                },
              ],
            },
            {
              transform: [
                {
                  pivot: newSpec.encoding.color.field,
                  value: newSpec.encoding.y.field,
                  groupby: [newSpec.encoding.x.field],
                },
              ],
              mark: 'rule',
              encoding: {
                opacity: {
                  condition: {value: 0.3, param: 'hover', empty: false},
                  value: 0,
                },
                tooltip: tooltipValues,
              },
              params: [
                {
                  name: 'hover',
                  select: {
                    type: 'point',
                    fields: [newSpec.encoding.x.field],
                    nearest: true,
                    on: 'mouseover',
                    clear: 'mouseout',
                  },
                },
              ],
            },
          ],
        };

        delete newSpec.encoding.color;
        delete newSpec.encoding.y;

        newSpec = _.merge(newSpec, mergeSpec);
      }

      if (newSpec.mark.type === 'boxplot' && !newSpec.encoding.tooltip) {
        newSpec.mark = 'boxplot';
        newSpec.encoding.tooltip = {
          field: TableState.getTableColumnName(
            vegaReadyTable.columnNames,
            vegaReadyTable.columnSelectFunctions,
            dims.tooltip ?? dims.y
          ),
          // type is autodetected by vega
        };
      }
    }

    if (colRangesResult.result != null) {
      const colRanges = colRangesResult.result;
      if (colRanges[dims.x] != null) {
        if (_.isArray(colRanges[dims.x])) {
          newSpec.encoding.x.scale = {
            domain: colRanges[dims.x],
          };
        } else {
          let {start, end} = colRanges[dims.x];
          if (start > 0 && start < end / 2) {
            start = 0;
          }
          newSpec.encoding.x.scale = {
            domainMin: start,
            domainMax: end,
          };
        }
      }
      if (colRanges[dims.y] != null) {
        if (_.isArray(colRanges[dims.y])) {
          newSpec.encoding.y.scale = {
            domain: colRanges[dims.y],
          };
        } else {
          let {start, end} = colRanges[dims.y];
          if (start > 0 && start < end / 2) {
            start = 0;
          }
          newSpec.encoding.y.scale = {
            domainMin: start,
            domainMax: end,
          };
        }
      }
      // Weird, need to look at color to pick label...
      // But it works!
      // TODO!!!
      if (colRanges[dims.label] != null) {
        if (_.isArray(colRanges[dims.label])) {
          newSpec.encoding.color.scale = {
            domain: colRanges[dims.label],
          };
        } else {
          let {start, end} = colRanges[dims.label];
          if (start > 0 && start < end / 2) {
            start = 0;
          }
          newSpec.encoding.color.scale = {
            domainMin: start,
            domainMax: end,
          };
        }
      }
    }

    return newSpec;
  }, [
    colRangesResult.result,
    dims,
    dimTypes,
    axisTypes,
    resultNode.type,
    isDashboard,
    isOrgDashboard,
    isRepoInsightsDashboard,
    config,
    vegaReadyTable,
    colorFieldIsRange,
    colorFieldValues,
    labelFieldValues,
    vegaCols,
  ]);

  const useWeaveTooltip = useMemo(
    () => vegaSpec.layer == null && vegaSpec.mark !== 'boxplot',
    [vegaSpec]
  );

  const [toolTipPos, setTooltipPos] = useState<{
    x: number | undefined;
    y: number | undefined;
    value: any;
  }>({x: undefined, y: undefined, value: undefined});
  const handleTooltip = useCallback(
    (toolTipHandler: any, event: any, item: any, value: any) => {
      const {x, y} = calculatePosition(
        event,
        toolTipRef.current?.getBoundingClientRect()!,
        10,
        10
      );
      if (value == null) {
        setTooltipPos({x: undefined, y: undefined, value: undefined});
      } else {
        setTooltipPos({x, y, value});
      }
    },
    []
  );

  const toolTipRef = useRef<HTMLDivElement>(null);
  // console.log('PLOT TABLE', plotTable);
  // console.log('FLAT PLOT TABLE', flatPlotTable);
  // console.log('VEGA SPEC', JSON.stringify(vegaSpec, undefined, 2));
  const tooltipNode = useMemo(() => {
    const valueResultIndex = toolTipPos.value?._index;
    if (valueResultIndex == null) {
      return CG.voidNode();
    }
    const row = Op.opIndex({
      arr: resultNode,
      index: Op.constNumber(valueResultIndex),
    });
    const toolTipFn = vegaReadyTable.columnSelectFunctions[dims.tooltip];
    if (toolTipFn.nodeType === 'void' || toolTipFn.type === 'invalid') {
      return row;
    }
    return Op.opPick({
      obj: row,
      key: Op.constString(
        escapeDots(
          TableState.getTableColumnName(
            vegaReadyTable.columnNames,
            vegaReadyTable.columnSelectFunctions,
            dims.tooltip
          )
        )
      ),
    });
  }, [
    dims.tooltip,
    resultNode,
    vegaReadyTable.columnNames,
    vegaReadyTable.columnSelectFunctions,
    toolTipPos.value,
  ]);
  const {handler} = useMemo(
    () =>
      getPanelStacksForType(tooltipNode.type, undefined, {
        excludeTable: true,
        excludePlot: true,
      }),
    [tooltipNode.type]
  );
  const updateTooltipConfig = useCallback(
    (newPanelConfig: any) => {
      return updateConfig({
        table: TableState.updateColumnPanelConfig(
          vegaReadyTable,
          config.dims.tooltip,
          newPanelConfig
        ),
      });
    },
    [updateConfig, vegaReadyTable, config.dims.tooltip]
  );

  const isRepoInsightsDash =
    Object.keys(useContext(RepoInsightsDashboardContext).frame).length > 0;
  const loaderComp = isRepoInsightsDash ? (
    <SemanticLoader active inline className="cgLoader" />
  ) : (
    <Panel2Loader />
  );

  const contents = useGatedValue(
    <>
      {result.loading || colRangesLoading ? (
        loaderComp
      ) : (
        <div style={{width: '100%', height: '100%'}}>
          {useWeaveTooltip && (
            <TooltipPortal>
              <div
                ref={toolTipRef}
                style={{
                  position: 'fixed',
                  visibility: toolTipPos.x == null ? 'hidden' : 'visible',
                  borderRadius: 2,
                  padding: 4,
                  top: toolTipPos.y,
                  left: toolTipPos.x,
                  // 2147483605 is the default z-index for panel models to get over
                  // intercom. Boy that is nasty - should make better
                  zIndex: 2147483605 + 9000,
                  background: '#fff',
                  boxShadow: '1px 1px 4px rgba(0, 0, 0, 0.2)',
                  ...getPanelStackDims(handler, tooltipNode.type, config),
                }}>
                {tooltipNode.nodeType !== 'void' && handler != null && (
                  <PanelComp2
                    input={tooltipNode}
                    inputType={tooltipNode.type}
                    loading={false}
                    panelSpec={handler}
                    configMode={false}
                    context={props.context}
                    config={
                      config.table.columns[config.dims.tooltip].panelConfig
                    }
                    updateConfig={updateTooltipConfig}
                    updateContext={props.updateContext}
                  />
                )}
              </div>
            </TooltipPortal>
          )}
          <CustomPanelRenderer
            spec={vegaSpec}
            loading={false}
            slow={false}
            data={flatPlotTable}
            userSettings={{
              // TODO: I'm putting ! in here cause our fieldSettings
              // doesn't allow undefined. Fix that to allow it.
              fieldSettings: {title: config.title!},
              stringSettings: {
                title: '',
              },
            }}
            handleTooltip={useWeaveTooltip ? handleTooltip : undefined}
          />
        </div>
      )}
      {/* Plot config
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {`${plotType}, ${axisTypes.x}, ${axisTypes.y}, ${axisTypes.color}`}
      </pre>
      Vega spec
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {JSON.stringify(vegaSpec, undefined, 2)}
      </pre> */}
      {/* Compute graph query
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {toString(resultNode)}
      </pre> */}
      {/* <pre style={{fontSize: 12}}>
        {JSON.stringify(plotTable, undefined, 2)}
      </pre>  */}
      {/* Query result
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {JSON.stringify(flatPlotTable, undefined, 2)}
      </pre> */}
      {/* Input row type
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {Types.toString(exampleInputFrame.x.type)}
      </pre>
      Grouped row type
      <pre style={{marginLeft: 16, fontSize: 12}}>
        {Types.toString(exampleRowFrame.x.type)}
      </pre>{' '} */}
    </>,
    x => !result.loading
  );

  /*
  if (flatPlotTable.length === 0 && !result.loading) {
    return <PanelError message="No data" />;
  }
  */

  return (
    <div
      data-test="panel-plot-2-wrapper"
      style={{height: '100%', width: '100%'}}
      className={result.loading ? 'loading' : ''}>
      {flatPlotTable.length === 0 && !result.loading ? (
        <PanelError message="No data" />
      ) : (
        contents
      )}
    </div>
  );
};

const TooltipPortal: React.FC<{}> = props => {
  const toolTipRef = useRef(document.createElement('div'));
  useEffect(() => {
    const el = toolTipRef.current;
    document.body.appendChild(el);
    return () => {
      document.body.removeChild(el);
    };
  }, []);
  return ReactDOM.createPortal(props.children, toolTipRef.current);
};

/* eslint-disable no-template-curly-in-string */

export const Spec: Panel2.PanelSpec = {
  id: 'plot',
  ConfigComponent: PanelPlotConfig,
  Component: PanelPlot2,
  inputType,
  defaultFixedSize: {
    width: 200,
    height: (9 / 16) * 200,
  },
};

const PLOT_TEMPLATE: VisualizationSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  data: {
    name: 'wandb',
  },
  padding: 1,
  title: '${field:title}',
  mark: {
    tooltip: {
      content: 'data',
    },
  } as any,
  params: [
    {
      name: 'grid',
      select: 'interval',
      bind: 'scales',
    },
  ],
  encoding: {
    // opacity: {
    //   value: 0.6,
    // },
  },
};

const ORG_DASHBOARD_TEMPLATE_OVERLAY = {
  config: {
    legend: {
      disable: true,
    },
    axis: {
      // labels: false,
      title: null,
    },
    style: {
      cell: {
        stroke: 'transparent',
      },
    },
  },
};
