import {isAssignableTo, maybe} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import React, {useCallback, useMemo, useState} from 'react';
import {Tab} from 'semantic-ui-react';

import {
  useWeaveContext,
  useWeaveRedesignedPlotConfigEnabled,
} from '../../../context';
import * as LLReact from '../../../react';
import {Button} from '../../Button';
import {VariableView} from '../ChildPanel';
import * as ConfigPanel from '../ConfigPanel';
import {ConfigSection} from '../ConfigPanel';
import {IconAddNew, IconDelete} from '../Icons';
import {LayoutTabs} from '../LayoutTabs';
import * as Panel2 from '../panel';
import {Panel2Loader} from '../PanelComp';
import {usePanelContext} from '../PanelContext';
import * as TableState from '../PanelTable/tableState';
import * as TableType from '../PanelTable/tableType';
import {useConfig} from './config';
import {ConfigDimComponent} from './ConfigDimComponent';
import {PanelPlot2Inner} from './PanelPlot2Inner';
import * as PlotState from './plotState';
import {isValidConfig} from './plotState';
import {ScaleConfigOption} from './ScaleConfigOption';
import {GroupByOption, SelectGroupBy} from './SelectGroupBy';
import * as S from './styles';
import {AxisName, inputType, PanelPlotProps} from './types';
import {defaultPlot, useVegaReadyTables} from './util';
import {PLOT_DIMS_UI, PlotConfig, SeriesConfig} from './versions';

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

  const loaderComp = <Panel2Loader />;

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

  const redesignedPlotConfigEnabled = useWeaveRedesignedPlotConfigEnabled();
  const inputNode = input;

  const weave = useWeaveContext();
  const {frame, stack, dashboardConfigOptions} = usePanelContext();

  // this migrates the config and returns a config of the latest version
  const {config} = useConfig(inputNode, props.config);

  const updateConfig = useCallback(
    (newConfig?: Partial<PlotConfig>) => {
      if (!newConfig) {
        // if config is undefined, just use the default plot
        propsUpdateConfig(
          defaultPlot(input, stack, !!redesignedPlotConfigEnabled)
        );
      } else {
        propsUpdateConfig({
          ...config,
          ...newConfig,
        });
      }
    },
    [config, propsUpdateConfig, input, stack, redesignedPlotConfigEnabled]
  );

  const resetConfig = useCallback(() => {
    updateConfig(undefined);
  }, [updateConfig]);

  const condense = useCallback(() => {
    const newConfig = PlotState.condensePlotConfig(config, weave);
    updateConfig(newConfig);
  }, [weave, config, updateConfig]);

  // const exportAsCode = useCallback(() => {
  //   if (navigator?.clipboard == null) {
  //     return;
  //   }

  //   if (config.series.length !== 1) {
  //     toast('Multi-series plots are not currently supported');
  //     return;
  //   }

  //   const series = config.series[0];

  //   const dimConfigured = (dim: keyof SeriesConfig['dims']) =>
  //     series.table.columnSelectFunctions[series.dims[dim]].type !== 'invalid';

  //   if (!dimConfigured('x') || !dimConfigured('y')) {
  //     toast(
  //       "Can't export to code: Required dimensions x and/or y are not configured"
  //     );
  //     return;
  //   }

  //   const dimArgument = (dim: keyof SeriesConfig['dims']) =>
  //     `${dim}=lambda row: ${weave.expToString(
  //       series.table.columnSelectFunctions[series.dims[dim]],
  //       null
  //     )},`;

  //   const inputTypeText = toPythonTyping(input.type);

  //   const dims: Array<keyof SeriesConfig['dims']> = [
  //     'x',
  //     'y',
  //     'label',
  //     'tooltip',
  //   ];

  //   const codeText = [
  //     '@weave.op()',
  //     `def my_panel(input: weave.Node[${inputTypeText}]) -> panels.Plot:`,
  //     '  return panels.Plot(',
  //     '    input,',
  //     ...dims.reduce<string[]>((memo, field) => {
  //       if (dimConfigured(field)) {
  //         memo.push(`    ${dimArgument(field)}`);
  //       }
  //       return memo;
  //     }, [] as string[]),
  //     '  )\n',
  //   ].join('\n');

  //   navigator.clipboard
  //     .writeText(codeText)
  //     .then(() => toast('Code copied to clipboard!'));
  // }, [config, input.type, weave]);

  const labelConfigDom = useMemo(() => {
    return (
      <>
        {['X axis', 'Y axis', 'Color legend'].map(name => {
          const dimName = name.split(' ')[0].toLowerCase() as
            | 'x'
            | 'y'
            | 'color';
          return (
            <ConfigPanel.ConfigOption key={name} label={name}>
              <ConfigPanel.TextInputConfigField
                dataTest={`${name}-label`}
                // Truncate string to prevent exploding panel for now.
                value={config.axisSettings[dimName].title}
                label=""
                onChange={(event, {value}) => {
                  const newConfig = produce(config, draft => {
                    _.set(draft, `axisSettings.${dimName}.title`, value);
                  });
                  updateConfig(newConfig);
                }}
              />
            </ConfigPanel.ConfigOption>
          );
        })}
      </>
    );
  }, [config, updateConfig]);

  // Ensure that user cannot delete the last series
  const seriesMenuItems = useCallback(
    (s: SeriesConfig, index: number) => {
      if (index === 0 && config.series.length === 1) {
        return [];
      }
      return [
        {
          key: 'Remove series',
          content: 'Remove series',
          icon: <IconDelete />,
          onClick: () => {
            updateConfig(PlotState.removeSeries(config, s));
          },
        },
      ];
    },
    [config, updateConfig]
  );

  const updateGroupBy = useCallback(
    async (
      enabled: boolean,
      seriesIndex: number,
      dimName: keyof SeriesConfig['dims'],
      value: string
    ) => {
      const fn = enabled
        ? TableState.enableGroupByCol
        : TableState.disableGroupByCol;
      let newTable = await fn(
        config.series[seriesIndex].table,
        value,
        inputNode,
        weave,
        stack
        // config.series[seriesIndex].dims[dimension.name as keyof SeriesConfig['dims']]
      );
      if (dimName === 'label') {
        newTable = await fn(
          newTable,
          config.series[seriesIndex].dims.color,
          inputNode,
          weave,
          stack
        );
      }
      const newConfig = produce(config, draft => {
        draft.series[seriesIndex].table = newTable;
      });
      updateConfig(newConfig);
    },
    [config, inputNode, stack, updateConfig, weave]
  );

  const newSeriesConfigDom = useMemo(() => {
    return (
      <>
        {config.series.map((s, i) => {
          const groupByDropdownOptions: GroupByOption[] = PLOT_DIMS_UI.filter(
            dimName => dimName !== 'mark'
          ).map(dimName => {
            return {
              value: s.dims[dimName as keyof SeriesConfig['dims']],
              label: dimName,
            };
          });
          return (
            <ConfigSection
              label={`Series ${i + 1}`}
              menuItems={seriesMenuItems(s, i)}>
              {
                <ConfigPanel.ConfigOption
                  key={`series-${i + 1}`}
                  label="Name"
                  multiline={true}>
                  <ConfigPanel.TextInputConfigField
                    dataTest={`series-${i + 1}-label`}
                    value={s.seriesName}
                    label=""
                    onChange={(event, {value}) => {
                      updateConfig(
                        produce(config, draft => {
                          draft.series[i].seriesName = value;
                        })
                      );
                    }}
                  />
                </ConfigPanel.ConfigOption>
              }
              <ConfigPanel.ConfigOption multiline={true} label="Group by">
                <SelectGroupBy
                  options={groupByDropdownOptions}
                  series={s}
                  onAdd={(dimName, value) => {
                    updateGroupBy(true, i, dimName, value);
                  }}
                  onRemove={(dimName, value) => {
                    updateGroupBy(false, i, dimName, value);
                  }}
                />
              </ConfigPanel.ConfigOption>
              {PLOT_DIMS_UI.map(dimName => {
                const dimIsShared = PlotState.isDimShared(
                  config.series,
                  dimName,
                  weave
                );
                const dimIsExpanded = config.configOptionsExpanded[dimName];
                const dimIsSharedInUI = dimIsShared && !dimIsExpanded;
                const seriesDim = PlotState.dimConstructors[dimName](s, weave);
                return (
                  <ConfigDimComponent
                    key={`${dimName}-${i}`}
                    input={input}
                    config={config}
                    updateConfig={updateConfig}
                    indentation={0}
                    isShared={dimIsSharedInUI}
                    dimension={seriesDim}
                    multiline={true}
                  />
                );
              })}
            </ConfigSection>
          );
        })}
      </>
    );
  }, [seriesMenuItems, config, weave, input, updateConfig, updateGroupBy]);

  const seriesConfigDom = useMemo(() => {
    const firstSeries = config.series[0];

    return (
      <>
        {PLOT_DIMS_UI.map(dimName => {
          const dimIsShared = PlotState.isDimShared(
            config.series,
            dimName,
            weave
          );

          const dimIsExpanded = config.configOptionsExpanded[dimName];
          const dimObject = PlotState.dimConstructors[dimName](
            firstSeries,
            weave
          );

          const dimIsSharedInUI = dimIsShared && !dimIsExpanded;
          return dimIsSharedInUI ? (
            <ConfigDimComponent
              key={dimName}
              input={input}
              config={config}
              updateConfig={updateConfig}
              indentation={0}
              isShared={dimIsSharedInUI}
              dimension={dimObject}
            />
          ) : (
            <React.Fragment key={dimName}>
              {config.series.map((s, i) => {
                const seriesDim = PlotState.dimConstructors[dimName](s, weave);
                return (
                  <ConfigDimComponent
                    key={`${dimName}-${i}`}
                    input={input}
                    config={config}
                    updateConfig={updateConfig}
                    indentation={0}
                    isShared={dimIsSharedInUI}
                    dimension={seriesDim}
                  />
                );
              })}
            </React.Fragment>
          );
        })}
      </>
    );
  }, [config, weave, input, updateConfig]);

  const vegaReadyTables = useVegaReadyTables(config.series, frame);

  const {xScaleConfigEnabled, yScaleConfigEnabled} = useMemo(() => {
    return {
      xScaleConfigEnabled: scaleConfigEnabledForAxis(`x`),
      yScaleConfigEnabled: scaleConfigEnabledForAxis(`y`),
    };

    function scaleConfigEnabledForAxis(axis: AxisName): boolean {
      return config.series.some((series, i) => {
        const vegaReadyTable = vegaReadyTables[i];
        const dimTypes = PlotState.getDimTypes(series.dims, vegaReadyTable);
        return isAssignableTo(dimTypes[axis], maybe('number'));
      });
    }
  }, [config.series, vegaReadyTables]);
  const scaleConfigEnabled = xScaleConfigEnabled || yScaleConfigEnabled;

  const scaleConfigDom = useMemo(
    () => (
      <>
        {xScaleConfigEnabled && (
          <ScaleConfigOption
            config={config}
            updateConfig={updateConfig}
            axis="x"
          />
        )}
        {yScaleConfigEnabled && (
          <ScaleConfigOption
            config={config}
            updateConfig={updateConfig}
            axis="y"
          />
        )}
      </>
    ),
    [config, updateConfig, xScaleConfigEnabled, yScaleConfigEnabled]
  );

  const [showAdvancedProperties, setShowAdvancedProperties] =
    useState<boolean>(false);
  const toggleAdvancedProperties = useCallback(() => {
    setShowAdvancedProperties(prev => !prev);
  }, []);
  const advancedPropertiesDom = useMemo(() => {
    return showAdvancedProperties ? (
      <>
        {scaleConfigDom}
        <S.AdvancedPropertiesHeader onClick={toggleAdvancedProperties}>
          Hide advanced properties
        </S.AdvancedPropertiesHeader>
      </>
    ) : (
      <S.AdvancedPropertiesHeader onClick={toggleAdvancedProperties}>
        Advanced properties
      </S.AdvancedPropertiesHeader>
    );
  }, [showAdvancedProperties, toggleAdvancedProperties, scaleConfigDom]);

  const [activeTabIndex, setActiveTabIndex] = useState<number>(0);
  const configTabs = useMemo(() => {
    if (redesignedPlotConfigEnabled) {
      return (
        <LayoutTabs
          tabNames={['Data', 'Labels']}
          renderPanel={({id}) => {
            if (id === 'Data') {
              return seriesConfigDom;
            } else if (id === 'Labels') {
              return labelConfigDom;
            }
            throw new Error('Invalid tab id');
          }}
        />
      );
    }
    const panes: Array<{menuItem: string; render: () => React.ReactElement}> = [
      {
        menuItem: 'Data',
        render: () => seriesConfigDom,
      },
      {
        menuItem: 'Labels',
        render: () => labelConfigDom,
      },
      ...(scaleConfigEnabled
        ? [
            {
              menuItem: `Scale`,
              render: () => scaleConfigDom,
            },
          ]
        : []),
    ];
    return (
      <Tab
        menu={{secondary: true, pointing: true}}
        panes={panes}
        onTabChange={(e, {activeIndex}) => {
          setActiveTabIndex(activeIndex as number);
        }}
        activeIndex={activeTabIndex}
      />
    );
  }, [
    redesignedPlotConfigEnabled,
    scaleConfigEnabled,
    activeTabIndex,
    seriesConfigDom,
    labelConfigDom,
    scaleConfigDom,
  ]);

  const seriesButtons = useMemo(
    () => (
      <>
        <Button
          size="small"
          variant="secondary"
          className="mr-12"
          onClick={resetConfig}>
          Reset & Automate Plot
        </Button>
        <Button size="small" variant="secondary" onClick={condense}>
          Condense
        </Button>
        {/* {weavePythonEcosystemEnabled && (
          <Button size="tiny" onClick={exportAsCode}>
            Export as Code
          </Button>
        )} */}
      </>
    ),
    [resetConfig, condense]
  );

  // We just get the cell frame so we can show the variables.
  // This doesn't do enough to show how grouping works. But at least it gives
  // some information for now.
  const cellFrame = useMemo(() => {
    const tableState0 = config.series[0].table;
    const rowsNode0 = TableState.tableGetResultTableNode(
      tableState0,
      input,
      weave
    ).rowsNode;
    return TableState.getCellFrame(
      input,
      rowsNode0,
      tableState0.groupBy,
      tableState0.columnSelectFunctions,
      config.series[0].dims.x
    );
  }, [config.series, input, weave]);

  const addNewSeriesDom = useMemo(() => {
    return (
      <>
        <S.AddNewSeriesContainer
          onClick={() => {
            if (config.series.length > 0) {
              const newConfig = produce(
                PlotState.addSeriesFromSeries(
                  config,
                  config.series[config.series.length - 1],
                  'y',
                  weave
                ),
                draft => {
                  draft.series[
                    draft.series.length - 1
                  ].seriesName = `Series ${draft.series.length}`;
                }
              );
              updateConfig(newConfig);
            }
          }}>
          <S.AddNewSeriesText data-testid="add-new-series-text">
            New series
          </S.AddNewSeriesText>
          <S.AddNewSeriesButton>
            <IconAddNew width="18" height="18" />
          </S.AddNewSeriesButton>
        </S.AddNewSeriesContainer>
      </>
    );
  }, [config, updateConfig, weave]);

  return useMemo(
    () =>
      redesignedPlotConfigEnabled ? (
        <>
          <ConfigSection label="Properties">
            {dashboardConfigOptions}
            <VariableView newVars={cellFrame} />
            {xScaleConfigEnabled &&
              yScaleConfigEnabled &&
              advancedPropertiesDom}
          </ConfigSection>
          {newSeriesConfigDom}
          {addNewSeriesDom}
          <ConfigSection label="Labels">{labelConfigDom}</ConfigSection>
        </>
      ) : (
        <>
          {configTabs}
          {activeTabIndex === 0 && seriesButtons}
        </>
      ),
    [
      redesignedPlotConfigEnabled,
      dashboardConfigOptions,
      cellFrame,
      labelConfigDom,
      configTabs,
      activeTabIndex,
      seriesButtons,
      xScaleConfigEnabled,
      yScaleConfigEnabled,
      addNewSeriesDom,
      advancedPropertiesDom,
      newSeriesConfigDom,
    ]
  );
};

const useLoader = () => {
  return <Panel2Loader />;
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
    return <div style={{height: '100%', width: '100%'}}>{loaderComp}</div>;
  } else if (typedInputNodeUse.result.nodeType === 'void') {
    return <div style={{height: '100%', width: '100'}}></div>;
  } else {
    return (
      <div style={{height: '100%', width: '100%'}}>
        <PanelPlot2Inner {...newProps} />
      </div>
    );
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'plot',
  icon: 'chart-horizontal-bars',
  category: 'Data',
  initialize: async (weave, inputNode, stack) => {
    // Can't happen, id was selected based on Node type
    if (inputNode.nodeType === 'void') {
      throw new Error('Plot input node is null');
    }
    // TODO: PanelPlot default relies on stack for its config, but we pass
    // it in empty!
    const tableNormInput = await weave.refineNode(
      TableType.normalizeTableLike(inputNode),
      stack
    );
    return PlotState.panelPlotDefaultConfig(tableNormInput, undefined, stack);
  },
  ConfigComponent: PanelPlotConfig,
  Component: PanelPlot2,
  inputType,
  defaultFixedSize: {
    width: 200,
    height: (9 / 16) * 200,
  },
  isValid: (config: PlotConfig): boolean => {
    return isValidConfig(config).valid;
  },
};

export default Spec;
