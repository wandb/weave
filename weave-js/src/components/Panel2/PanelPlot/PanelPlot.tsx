import {ActivityDashboardContext} from '@wandb/weave/common/components/ActivityDashboardContext';
import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import HighlightedIcon from '@wandb/weave/common/components/HighlightedIcon';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {RepoInsightsDashboardContext} from '@wandb/weave/common/components/RepoInsightsDashboardContext';
import CustomPanelRenderer, {
  MultiTableDataType,
} from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import * as globals from '@wandb/weave/common/css/globals.styles';
import * as S from './styles';
import {
  constNode,
  constFunction,
  ConstNode,
  constNodeUnsafe,
  constNone,
  constNumber,
  constString,
  constStringList,
  escapeDots,
  Frame,
  isAssignableTo,
  isConstNode,
  isTypedDict,
  isVoidNode,
  list,
  listObjectType,
  maybe,
  Node,
  numberBin,
  timestampBin,
  oneOrMany,
  opAnd,
  opArray,
  opDict,
  opContains,
  opDateToNumber,
  opFilter,
  opIndex,
  // opMap,
  // opMerge,
  opNumberGreaterEqual,
  opNumberLessEqual,
  opPick,
  // opRandomlyDownsample,
  opRunId,
  opRunName,
  OpStore,
  opUnnest,
  OutputNode,
  Stack,
  Type,
  typedDict,
  TypedDictType,
  union,
  varNode,
  voidNode,
  withoutTags,
  filterNodes,
  taggedValueValueType,
  isTaggedValue,
  opLimit,
} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import React, {
  FC,
  memo,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import ReactDOM from 'react-dom';
import {View as VegaView, VisualizationSpec} from 'react-vega';
import {Button, MenuItemProps, Tab} from 'semantic-ui-react';
import {calculatePosition} from 'vega-tooltip';

import {useWeaveContext, useWeaveDashUiEnable} from '../../../context';
import * as LLReact from '../../../react';
import {getPanelStackDims, getPanelStacksForType} from '../availablePanels';
import {VariableView} from '../ChildPanel';
import * as ConfigPanel from '../ConfigPanel';
import {LayoutTabs} from '../LayoutTabs';
import * as Panel2 from '../panel';
import {Panel2Loader, PanelComp2} from '../PanelComp';
import {PanelContextProvider, usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
// import {makePromiseUsable} from '../PanelTable/hooks';
import * as TableState from '../PanelTable/tableState';
import {useTableStatesWithRefinedExpressions} from '../PanelTable/tableStateReact';
import * as TableType from '../PanelTable/tableType';
import * as PlotState from './plotState';
import {
  DimensionLike,
  ExpressionDimName,
  isValidConfig,
  DIM_NAME_MAP,
  DASHBOARD_DIM_NAME_MAP,
} from './plotState';
import {PanelPlotRadioButtons} from './RadioButtons';
import {
  AnyPlotConfig,
  ConcretePlotConfig,
  AxisSelections,
  ContinuousSelection,
  DEFAULT_SCALE_TYPE,
  DiscreteSelection,
  LAZY_PATHS,
  LINE_SHAPES,
  MarkOption,
  PLOT_DIMS_UI,
  PlotConfig,
  POINT_SHAPES,
  Scale,
  SCALE_TYPES,
  ScaleType,
  SeriesConfig,
} from './versions';
import {toWeaveType} from '../toWeaveType';
import {ConfigSection} from '../ConfigPanel';
import {IconButton} from '../../IconButton';
import {Tooltip} from '../../Tooltip';
import {IconLockedConstrained, IconUnlockedUnconstrained} from '../../Icon';
import {
  IconAddNew,
  IconCheckmark,
  IconDelete,
  IconFullScreenModeExpand,
  IconMinimizeMode,
  IconOverflowHorizontal,
  IconWeave,
} from '../Icons';
import styled from 'styled-components';
import {PopupMenu, Section} from '../../Sidebar/PopupMenu';
import {Option} from '@wandb/weave/common/util/uihelpers';
import {useIsMounted} from '@wandb/weave/common/util/hooks';

const recordEvent = makeEventRecorder('Plot');

// const PANELPLOT_MAX_DATAPOINTS = 2000;
const DOMAIN_DATAFETCH_EXTRA_EXTENT = 2;

const defaultFontStyleDict = {
  titleFont: 'Source Sans Pro',
  titleFontWeight: 'normal',
  titleColor: globals.gray900,
  labelFont: 'Source Sans Pro',
  labelFontWeight: 'normal',
  labelColor: globals.gray900,
  labelSeparation: 5,
};

export const BRUSH_MODES = ['zoom' as const, 'select' as const];
type BrushMode = (typeof BRUSH_MODES)[number];

type DimOption = {
  text: string;
  icon: string;
  onClick: () => void;
};

type DimOptionOrSection = DimOption | DimOption[];

function useIsOrgDashboard() {
  return Object.keys(useContext(ActivityDashboardContext).frame).length > 0;
}

function useIsRepoInsightsDashboard() {
  return Object.keys(useContext(RepoInsightsDashboardContext).frame).length > 0;
}

function useIsDashboard() {
  const isOrgDashboard = useIsOrgDashboard();
  const isRepoInsightsDashboard = useIsRepoInsightsDashboard();
  return isOrgDashboard || isRepoInsightsDashboard;
}

function defaultPlot(
  inputNode: Node,
  stack: Stack,
  enableDashUi: boolean
): PlotConfig {
  return PlotState.setDefaultSeriesNames(
    PlotState.defaultPlot(inputNode, stack),
    enableDashUi
  );
}

const useConfig = (
  inputNode: Node,
  propsConfig?: AnyPlotConfig
): {config: PlotConfig; isRefining: boolean} => {
  const {stack} = usePanelContext();
  const weave = useWeaveContext();
  const enableDashUi = useWeaveDashUiEnable();

  const newConfig = useMemo(() => {
    return PlotState.setDefaultSeriesNames(
      PlotState.panelPlotDefaultConfig(inputNode, propsConfig, stack),
      !!enableDashUi
    );
  }, [propsConfig, inputNode, stack, enableDashUi]);

  const defaultColNameStrippedConfig = useMemo(
    () =>
      produce(newConfig, draft => {
        draft.series.forEach(s => {
          ['pointShape' as const, 'pointSize' as const].forEach(colName => {
            if (s.table.columnNames[s.dims[colName]] === colName) {
              s.table = TableState.updateColumnName(
                s.table,
                s.dims[colName],
                ''
              );
            }
          });
        });
      }),
    [newConfig]
  );

  const tableStates = useMemo(
    () => defaultColNameStrippedConfig.series.map(s => s.table),
    [defaultColNameStrippedConfig.series]
  );

  const loadable = useTableStatesWithRefinedExpressions(
    tableStates,
    inputNode,
    stack,
    weave
  );

  const configWithRefinedExpressions = useMemo(() => {
    return loadable.loading
      ? newConfig
      : produce(newConfig, draft => {
          draft.series.forEach((s, i) => {
            s.table = loadable.result[i];
          });
        });
  }, [loadable, newConfig]);

  const final = useMemo(
    () => ({
      config: configWithRefinedExpressions,
      isRefining: loadable.loading,
    }),
    [configWithRefinedExpressions, loadable.loading]
  );

  return final;
};

const inputType = TableType.GeneralTableLikeType;
export type PanelPlotProps = Panel2.PanelProps<typeof inputType, AnyPlotConfig>;

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

const stringHashCode = (str: string) => {
  let hash = 0;
  if (str.length === 0) {
    return hash;
  }
  for (let i = 0; i < str.length; i++) {
    const chr = str.charCodeAt(i);
    hash = (hash << 5) - hash + chr; // tslint:disable-line no-bitwise
    hash |= 0; // tslint:disable-line no-bitwise
  }
  return hash;
};

const ensureValidSignals = (config: ConcretePlotConfig): ConcretePlotConfig => {
  // ensure that the domain is valid for the axis type
  return produce(config, draft =>
    ['x' as const, 'y' as const].forEach(axisName => {
      ['domain' as const, 'selection' as const].forEach(signalName => {
        if (
          !PlotState.isValidDomainForAxisType(
            draft.signals[signalName][axisName],
            PlotState.getAxisType(draft.series[0], axisName)
          )
        ) {
          draft.signals[signalName][axisName] = undefined;
        }
      });
    })
  );
};

const useConcreteConfig = (
  config: PlotConfig,
  input: Node,
  stack: Stack,
  panelId: string
): {config: ConcretePlotConfig; loading: boolean} => {
  const lazyConfigElementsNode = useMemo(
    () =>
      opDict(
        LAZY_PATHS.reduce((acc, path) => {
          let elementNode = PlotState.getThroughArray(config, path.split('.'));
          if (_.isArray(elementNode)) {
            elementNode = opArray(
              elementNode.reduce((innerAcc, node, i) => {
                innerAcc[i] = node;
                return innerAcc;
              }, {} as any) as any
            );
          }
          if (elementNode == null) {
            elementNode = constNone();
          }
          acc[path] = elementNode;
          return acc;
        }, {} as any)
      ),
    [config]
  );

  const concreteConfigUse = LLReact.useNodeValue(lazyConfigElementsNode, {
    callSite: 'PanelPlot.concreteConfig.' + panelId,
  });
  const concreteConfigEvaluationResult = concreteConfigUse.result as
    | {[K in (typeof LAZY_PATHS)[number]]: any}
    | undefined;

  const concreteConfigLoading = concreteConfigUse.loading;

  return useMemo(() => {
    let loading: boolean = false;
    let newConfig: ConcretePlotConfig;
    if (concreteConfigLoading) {
      newConfig = PlotState.defaultConcretePlot(
        // Don't use the actual input.type here, defaultConcretePlot is expensive!
        // but we don't need a hydrated config in the loading case.
        constNode(list(typedDict({})), []),
        stack
      );
      loading = true;
    } else {
      // generate the new config with the concrete values obtained from the execution of the lazy paths
      newConfig = produce(config, draft => {
        LAZY_PATHS.forEach(path => {
          PlotState.setThroughArray(
            draft,
            path.split('.'),
            concreteConfigEvaluationResult![path],
            false
          );
        });
      }) as any;
    }

    return {config: newConfig, loading};
  }, [concreteConfigEvaluationResult, concreteConfigLoading, config, stack]);
};

const PanelPlotConfigInner: React.FC<PanelPlotProps> = props => {
  const {input, updateConfig: propsUpdateConfig} = props;

  const enableDashUi = useWeaveDashUiEnable();
  const inputNode = input;

  const weave = useWeaveContext();
  const {frame, stack, dashboardConfigOptions} = usePanelContext();

  // this migrates the config and returns a config of the latest version
  const {config} = useConfig(inputNode, props.config);

  const updateConfig = useCallback(
    (newConfig?: Partial<PlotConfig>) => {
      if (!newConfig) {
        // if config is undefined, just use the default plot
        propsUpdateConfig(defaultPlot(input, stack, !!enableDashUi));
      } else {
        propsUpdateConfig({
          ...config,
          ...newConfig,
        });
      }
    },
    [config, propsUpdateConfig, input, stack, enableDashUi]
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
                label={''}
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
          const groupByDropdownOptions: Option[] = PLOT_DIMS_UI.filter(
            dimName => dimName !== 'mark'
          ).map(dimName => {
            return {
              key: dimName,
              text: dimName,
              value: s.dims[dimName as keyof SeriesConfig['dims']],
            };
          });
          return (
            <ConfigSection
              label={`Series ${i + 1}`}
              menuItems={seriesMenuItems(s, i)}>
              {
                <ConfigPanel.ConfigOption
                  key={`series-${i + 1}`}
                  label={'Name'}
                  multiline={true}>
                  <ConfigPanel.TextInputConfigField
                    dataTest={`series-${i + 1}-label`}
                    value={s.seriesName}
                    label={''}
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
                <ConfigPanel.ModifiedDropdownConfigField
                  multiple
                  options={groupByDropdownOptions}
                  value={s.table.groupBy.filter(value =>
                    // In updateGroupBy above, if the dim is label, color also gets added
                    // as another dimension to group by. It's confusing to the user
                    // so we hide the automatic color grouping in the UI
                    // TODO: need to discuss with shawn on grouping logic
                    groupByDropdownOptions.some(o => o.value === value)
                  )}
                  onChange={(event, {value}) => {
                    const values = value as string[];
                    const valueToAdd = values.filter(
                      x => !s.table.groupBy.includes(x)
                    );
                    const valueToRemove = s.table.groupBy.filter(
                      x => !values.includes(x)
                    );
                    if (valueToAdd.length > 0) {
                      const dimName = groupByDropdownOptions.find(
                        o => o.value === valueToAdd[0]
                      )?.text as keyof SeriesConfig['dims'];
                      updateGroupBy(true, i, dimName, valueToAdd[0]);
                    } else if (valueToRemove.length > 0) {
                      const dimName = groupByDropdownOptions.find(
                        o => o.value === valueToRemove[0]
                      )?.text as keyof SeriesConfig['dims'];
                      updateGroupBy(false, i, dimName, valueToRemove[0]);
                    }
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
            axis={`x`}
          />
        )}
        {yScaleConfigEnabled && (
          <ScaleConfigOption
            config={config}
            updateConfig={updateConfig}
            axis={`y`}
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
    return (
      <>
        {showAdvancedProperties ? (
          <div onClick={toggleAdvancedProperties}>
            {scaleConfigDom}
            <S.AdvancedPropertiesHeader>
              Hide advanced properties
            </S.AdvancedPropertiesHeader>
          </div>
        ) : (
          <S.AdvancedPropertiesHeader onClick={toggleAdvancedProperties}>
            Advanced properties
          </S.AdvancedPropertiesHeader>
        )}
      </>
    );
  }, [showAdvancedProperties, toggleAdvancedProperties, scaleConfigDom]);

  const [activeTabIndex, setActiveTabIndex] = useState<number>(0);
  const configTabs = useMemo(() => {
    if (enableDashUi) {
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
    enableDashUi,
    scaleConfigEnabled,
    activeTabIndex,
    seriesConfigDom,
    labelConfigDom,
    scaleConfigDom,
  ]);

  const seriesButtons = useMemo(
    () => (
      <>
        <Button size="mini" onClick={resetConfig}>
          {'Reset & Automate Plot'}
        </Button>
        <Button size="mini" onClick={condense}>
          {'Condense'}
        </Button>
        {/* {weavePythonEcosystemEnabled && (
          <Button size="tiny" onClick={exportAsCode}>
            {'Export as Code'}
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
          <S.AddNewSeriesText>New series</S.AddNewSeriesText>
          <S.AddNewSeriesButton>
            <IconAddNew width="18" height="18" />
          </S.AddNewSeriesButton>
        </S.AddNewSeriesContainer>
      </>
    );
  }, [config, updateConfig, weave]);

  return useMemo(
    () =>
      enableDashUi ? (
        <>
          <ConfigSection label={`Properties`}>
            {dashboardConfigOptions}
            <VariableView newVars={cellFrame} />
            {xScaleConfigEnabled &&
              yScaleConfigEnabled &&
              advancedPropertiesDom}
          </ConfigSection>
          {newSeriesConfigDom}
          {addNewSeriesDom}
          <ConfigSection label={`Labels`}>{labelConfigDom}</ConfigSection>
        </>
      ) : (
        <>
          {configTabs}
          {activeTabIndex === 0 && seriesButtons}
        </>
      ),
    [
      enableDashUi,
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

type AxisName = `x` | `y`;

type ScaleOption = {text: string; value: ScaleType};
const SCALE_TYPE_OPTIONS: ScaleOption[] = SCALE_TYPES.map(t => ({
  text: _.capitalize(t),
  value: t,
}));

type ScalePropWithDefault = {
  scaleProp: keyof Scale;
  default: number;
  min?: number;
  max?: number;
};

const SCALE_TYPE_SPECIFIC_PROPS: {
  [scaleType: string]: ScalePropWithDefault | undefined;
} = {
  log: {scaleProp: `base`, default: 10, min: 0},
};

type ScaleConfigOptionProps = Pick<PanelPlotProps, `updateConfig`> & {
  config: PlotConfig;
  axis: AxisName;
};

const ScaleConfigOptionComp: FC<ScaleConfigOptionProps> = ({
  updateConfig,
  config,
  axis,
}) => {
  const currentScaleType =
    getScaleValue<ScaleType>(`scaleType`) ?? DEFAULT_SCALE_TYPE;

  const scaleTypeSpecificProp = SCALE_TYPE_SPECIFIC_PROPS[currentScaleType];
  const scaleTypeSpecificPropValue: number | undefined =
    scaleTypeSpecificProp != null
      ? getScaleValue<number>(scaleTypeSpecificProp.scaleProp) ??
        scaleTypeSpecificProp.default
      : undefined;

  return (
    <>
      <ConfigPanel.ConfigOption label={`${axis.toUpperCase()} Axis Scale`}>
        <ConfigPanel.ModifiedDropdownConfigField
          options={SCALE_TYPE_OPTIONS}
          value={currentScaleType}
          onChange={(event, {value}) => {
            setScaleValue(`scaleType`, value as ScaleType);
          }}
        />
      </ConfigPanel.ConfigOption>
      {scaleTypeSpecificProp != null && (
        <ConfigPanel.ConfigOption
          label={`${axis.toUpperCase()} ${_.capitalize(
            currentScaleType
          )} ${_.capitalize(scaleTypeSpecificProp.scaleProp)}`}>
          <ConfigPanel.NumberInputConfigField
            min={scaleTypeSpecificProp.min}
            max={scaleTypeSpecificProp.max}
            value={scaleTypeSpecificPropValue}
            onChange={value => {
              if (value != null) {
                setScaleValue(scaleTypeSpecificProp.scaleProp, value);
              }
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
    </>
  );

  function getScaleValue<T extends ScaleType | number>(
    scaleProp: keyof Scale
  ): T | undefined {
    return _.get(config, getNestedScaleKey(scaleProp));
  }

  function setScaleValue<T extends ScaleType | number>(
    scaleProp: keyof Scale,
    value: T
  ): void {
    const newConfig = produce(config, draft => {
      _.set(draft, getNestedScaleKey(scaleProp), value);
    });
    updateConfig(newConfig);
  }

  function getNestedScaleKey(scaleProp: keyof Scale): string {
    return `axisSettings.${axis}.scale.${scaleProp}`;
  }
};

const ScaleConfigOption = memo(ScaleConfigOptionComp);

const useLoader = () => {
  return <Panel2Loader />;
};

const stringIsColorLike = (val: string): boolean => {
  return (
    val.match('^#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$') != null || // matches hex code
    (val.startsWith('rgb(') && val.endsWith(')')) || // rgb
    (val.startsWith('hsl(') && val.endsWith(')')) // hsl
  );
};

type DimComponentInputType = {
  input: PanelPlotProps['input'];
  config: PlotConfig;
  updateConfig: (config?: Partial<PlotConfig>) => void;
  indentation: number;
  isShared: boolean;
  dimension: DimensionLike;
  extraOptions?: DimOptionOrSection[];
  multiline?: boolean;
};

const ConfigDimLabel: React.FC<
  Omit<DimComponentInputType, 'extraOptions'> & {
    postfixComponent?: React.ReactElement;
    multiline?: boolean;
    enableDashUi?: boolean;
  }
> = props => {
  const dimName = props.dimension.name;
  const seriesIndexStr =
    props.isShared || props.config.series.length === 1
      ? ''
      : ` ${props.config.series.indexOf(props.dimension.series) + 1}`;
  const label = props.enableDashUi
    ? DASHBOARD_DIM_NAME_MAP[dimName]
    : DIM_NAME_MAP[dimName] + seriesIndexStr;

  return (
    <div
      style={{
        paddingLeft: 10 * props.indentation,
        borderLeft:
          props.indentation > 0 && props.enableDashUi
            ? `2px solid ${globals.MOON_200}`
            : 'none',
      }}>
      <ConfigPanel.ConfigOption
        label={label}
        data-test={`${props.dimension.name}-dim-config`}
        postfixComponent={props.postfixComponent}
        multiline={props.multiline}>
        {props.children}
      </ConfigPanel.ConfigOption>
    </div>
  );
};

const WeaveExpressionDimConfig: React.FC<{
  dimName: ExpressionDimName;
  input: PanelPlotProps['input'];
  series: SeriesConfig[];
  config: PlotConfig;
  updateConfig: PanelPlotProps['updateConfig'];
}> = props => {
  const {config, input, updateConfig, series} = props;

  const seriesIndices = useMemo(
    () => series.map(s => config.series.indexOf(s)),
    [series, config.series]
  );
  const updateDims = useCallback(
    (node: Node) => {
      const newConfig = produce(config, draft => {
        seriesIndices.forEach(i => {
          const s = draft.series[i];
          s.table = TableState.updateColumnSelect(
            s.table,
            s.dims[props.dimName],
            node
          );
        });
      });
      updateConfig(newConfig);
    },
    [config, props.dimName, seriesIndices, updateConfig]
  );
  const weave = useWeaveContext();

  const tableConfigs = useMemo(() => series.map(s => s.table), [series]);
  const rowsNodes = useMemo(() => {
    return series.map(
      s => TableState.tableGetResultTableNode(s.table, input, weave).rowsNode
    );
  }, [series, input, weave]);
  const colIds = useMemo(
    () => series.map(s => s.dims[props.dimName]),
    [series, props.dimName]
  );

  const cellFrames = useMemo(
    () =>
      rowsNodes.map((rowsNode, i) => {
        const tableState = tableConfigs[i];
        const colId = colIds[i];
        return TableState.getCellFrame(
          input,
          rowsNode,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          colId
        );
      }),
    [rowsNodes, input, tableConfigs, colIds]
  );

  return (
    <PanelContextProvider newVars={cellFrames[0]}>
      <ConfigPanel.ExpressionConfigField
        expr={tableConfigs[0].columnSelectFunctions[colIds[0]]}
        setExpression={updateDims as any}
      />
    </PanelContextProvider>
  );
};

const ConfigDimComponent: React.FC<DimComponentInputType> = props => {
  const {
    updateConfig,
    config,
    dimension,
    isShared,
    indentation,
    input,
    extraOptions,
    multiline,
  } = props;
  const weave = useWeaveContext();
  const enableDashUi = useWeaveDashUiEnable();
  const makeUnsharedDimDropdownOptions = useCallback(
    (series: SeriesConfig, dimName: (typeof PLOT_DIMS_UI)[number]) => {
      const removeSeriesDropdownOption =
        config.series.length > 1
          ? {
              text: 'Remove series',
              icon: 'wbic-ic-delete',
              onClick: () => {
                updateConfig(PlotState.removeSeries(config, series));
              },
            }
          : null;

      const addSeriesDropdownOption = {
        text: 'Add series from this series',
        icon: 'wbic-ic-plus',
        onClick: () => {
          const newConfig = PlotState.addSeriesFromSeries(
            config,
            series,
            dimName,
            weave
          );
          updateConfig(newConfig);
        },
      };

      const collapseDimDropdownOption =
        config.series.length > 1
          ? {
              text: 'Collapse dimension',
              icon: 'wbic-ic-collapse',
              onClick: () => {
                updateConfig(
                  PlotState.makeDimensionShared(config, series, dimName, weave)
                );
              },
            }
          : null;

      return enableDashUi
        ? []
        : [
            removeSeriesDropdownOption,
            addSeriesDropdownOption,
            collapseDimDropdownOption,
            enableDashUi,
          ];
    },
    [config, updateConfig, weave, enableDashUi]
  );

  const makeSharedDimDropdownOptions = useCallback(
    (dimName: (typeof PLOT_DIMS_UI)[number]) => {
      const expandDim =
        config.series.length > 1
          ? {
              text: 'Expand dimension',
              icon: 'wbic-ic-expand',
              onClick: () => {
                const newConfig = produce(config, draft => {
                  draft.configOptionsExpanded[dimName] = true;
                });
                updateConfig(newConfig);
              },
            }
          : null;

      return enableDashUi ? [] : [expandDim];
    },
    [config, updateConfig, enableDashUi]
  );

  const uiStateOptions = useMemo(() => {
    if (!PlotState.isDropdownWithExpression(dimension)) {
      return [null];
    }

    // return true if an expression can be directly switched to a constant
    const isDirectlySwitchable = (
      dim: PlotState.DropdownWithExpressionDimension
    ): boolean => {
      const options = dim.dropdownDim.options;
      const expressionValue = dim.expressionDim.state().value;
      const expressionIsConst = expressionValue.nodeType === 'const';
      return options.some(
        o =>
          expressionIsConst &&
          _.isEqual(o.value, (expressionValue as ConstNode).val) &&
          o.representableAsExpression
      );
    };

    const clickHandler = (
      dim: PlotState.DropdownWithExpressionDimension,
      kernel: (
        series: SeriesConfig,
        dimension: PlotState.DropdownWithExpressionDimension
      ) => void
    ): void => {
      const newConfig = produce(config, draft => {
        const seriesToIterateOver = isShared
          ? draft.series
          : _.compact([
              draft.series.find(series => _.isEqual(series, dim.series)),
            ]);
        seriesToIterateOver.forEach(s => kernel(s, dim));
      });

      updateConfig(newConfig);
    };

    return [
      [
        {
          text: 'Input method',
          icon: null,
          disabled: true,
        },
        {
          text: 'Select via dropdown',
          icon: !enableDashUi ? (
            'wbic-ic-list'
          ) : dimension.mode() === `dropdown` ? (
            <IconCheckmark />
          ) : (
            <IconBlank />
          ),
          active: dimension.mode() === 'dropdown',
          onClick: () => {
            clickHandler(dimension, (s, dim) => {
              if (s.uiState[dim.name] === 'expression') {
                s.uiState[dim.name] = 'dropdown';
                const expressionValue = dim.expressionDim.state().value;

                // If the current expression has a corresponding dropdown option, use that dropdown value
                if (isDirectlySwitchable(dim)) {
                  s.constants[dim.name] = (expressionValue as ConstNode)
                    .val as any;
                }
              }
            });
          },
        },
        {
          text: 'Enter a Weave Expression',
          icon: !enableDashUi ? (
            'wbic-ic-xaxis'
          ) : dimension.mode() === `expression` ? (
            <IconCheckmark />
          ) : (
            <IconBlank />
          ),

          active: dimension.mode() === 'expression',
          onClick: () => {
            clickHandler(dimension, (s, dim) => {
              if (s.uiState[dim.name] === 'dropdown') {
                s.uiState[dim.name] = 'expression';

                // If the current dropdown is representable as an expression, use that expression
                if (isDirectlySwitchable(dim)) {
                  const colId = s.dims[dim.name];
                  s.table = TableState.updateColumnSelect(
                    s.table,
                    colId,
                    constString(s.constants[dim.name])
                  );
                }
              }
            });
          },
        },
      ],
    ];
  }, [config, updateConfig, isShared, dimension, enableDashUi]);

  const topLevelDimOptions = useCallback(
    (dimName: (typeof PLOT_DIMS_UI)[number]) => {
      return isShared
        ? makeSharedDimDropdownOptions(dimName)
        : makeUnsharedDimDropdownOptions(dimension.series, dimName);
    },
    [
      makeSharedDimDropdownOptions,
      makeUnsharedDimDropdownOptions,
      dimension.series,
      isShared,
    ]
  );

  const dimOptions = useMemo(
    () =>
      _.compact([
        ...(PlotState.isTopLevelDimension(dimension.name)
          ? topLevelDimOptions(dimension.name)
          : []),
        ...uiStateOptions,
        ...(extraOptions || []),
      ]),
    [dimension, uiStateOptions, topLevelDimOptions, extraOptions]
  );

  const postFixComponent = useMemo(() => {
    if (!enableDashUi) {
      return (
        <PopupDropdown
          position="left center"
          trigger={
            <div>
              <HighlightedIcon>
                <LegacyWBIcon name="overflow" />
              </HighlightedIcon>
            </div>
          }
          options={dimOptions.filter(o => !Array.isArray(o))}
          sections={dimOptions.filter(o => Array.isArray(o)) as DimOption[][]}
        />
      );
    }

    const nonArrayDimOptions = dimOptions.filter(
      o => !Array.isArray(o)
    ) as DimOption[];
    const arrayDimOptions = dimOptions.filter(o =>
      Array.isArray(o)
    ) as DimOption[][];

    const menuItems: MenuItemProps[] =
      nonArrayDimOptions.map(dimOptionToMenuItem);
    const menuSections: Section[] = arrayDimOptions.map(opts => ({
      label: opts[0].text,
      items: opts.slice(1).map(dimOptionToMenuItem),
    }));

    const zeroMenuOptions =
      uiStateOptions.length === 1 &&
      uiStateOptions[0] === null &&
      extraOptions == null;

    const dimName = dimension.name as (typeof PLOT_DIMS_UI)[number];

    return (
      <>
        {!zeroMenuOptions && (
          <PopupMenu
            position="bottom left"
            trigger={
              <ConfigDimMenuButton>
                <IconOverflowHorizontal />
              </ConfigDimMenuButton>
            }
            items={menuItems}
            sections={menuSections}
          />
        )}
        {config.series.length > 1 &&
          indentation === 0 &&
          (isShared ? (
            <Tooltip
              position="top right"
              trigger={
                <S.ConstrainedIconContainer
                  onClick={() => {
                    // "expanding" the dimension means unconstraining it
                    const newConfig = produce(config, draft => {
                      draft.configOptionsExpanded[dimName] = true;
                    });
                    updateConfig(newConfig);
                  }}>
                  <IconLockedConstrained width={18} height={18} />
                </S.ConstrainedIconContainer>
              }>
              Remove constraint across series
            </Tooltip>
          ) : (
            <Tooltip
              position="top right"
              trigger={
                <S.UnconstrainedIconContainer
                  // "sharing" the dimension means constraining it
                  onClick={() => {
                    updateConfig(
                      PlotState.makeDimensionShared(
                        config,
                        dimension.series,
                        dimName,
                        weave
                      )
                    );
                  }}>
                  <IconUnlockedUnconstrained width={18} height={18} />
                </S.UnconstrainedIconContainer>
              }>
              Constrain dimension across series
            </Tooltip>
          ))}
      </>
    );

    function dimOptionToMenuItem({
      text,
      icon,
      onClick,
    }: DimOption): MenuItemProps {
      return {
        key: text,
        content: text,
        icon: convertIcon(icon),
        onClick,
      };
    }

    function convertIcon(iconStr: ReactNode): ReactNode {
      if (typeof iconStr !== `string`) {
        return iconStr;
      }
      switch (iconStr) {
        case `wbic-ic-delete`:
          return <IconDelete />;
        case `wbic-ic-plus`:
          return <IconAddNew />;
        case `wbic-ic-collapse`:
          // TODO: replace with proper icon
          return <IconMinimizeMode />;
        case `wbic-ic-expand`:
          // TODO: replace with proper icon
          return <IconFullScreenModeExpand />;
        case null:
          return null;
        default:
          return <IconWeave />;
      }
    }
  }, [
    dimOptions,
    enableDashUi,
    config,
    dimension.name,
    dimension.series,
    extraOptions,
    indentation,
    isShared,
    uiStateOptions,
    updateConfig,
    weave,
  ]);

  if (PlotState.isDropdownWithExpression(dimension)) {
    return (
      <ConfigDimComponent
        {...props}
        dimension={
          dimension.mode() === 'expression'
            ? dimension.expressionDim
            : dimension.dropdownDim
        }
        extraOptions={uiStateOptions as DimOptionOrSection[]}
      />
    );
  } else if (PlotState.isGroup(dimension)) {
    const primary = dimension.primaryDimension();
    return (
      <>
        {dimension.activeDimensions().map(dim => {
          const isPrimary = dim.equals(primary);
          return (
            <ConfigDimComponent
              {...props}
              key={dim.name}
              indentation={isPrimary ? indentation : indentation + 1}
              dimension={dim}
            />
          );
        })}
      </>
    );
  } else if (PlotState.isDropdown(dimension)) {
    const dimName = dimension.name;
    return (
      <ConfigDimLabel
        {...props}
        postfixComponent={postFixComponent}
        multiline={enableDashUi && multiline}
        enableDashUi={enableDashUi}>
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          placeholder={dimension.defaultState().compareValue}
          value={dimension.state().value}
          options={dimension.options}
          onChange={(e, {value}) => {
            const newSeries = produce(config.series, draft => {
              draft.forEach(s => {
                if (isShared || _.isEqual(s, dimension.series)) {
                  // @ts-ignore
                  s.constants[dimName] = value;
                }
              });
            });
            updateConfig({
              series: newSeries,
            });
          }}
        />
      </ConfigDimLabel>
    );
  } else if (PlotState.isWeaveExpression(dimension)) {
    return (
      <>
        <ConfigDimLabel
          {...props}
          postfixComponent={postFixComponent}
          multiline={enableDashUi && multiline}
          enableDashUi={enableDashUi}>
          <WeaveExpressionDimConfig
            dimName={dimension.name}
            input={input}
            config={config}
            updateConfig={updateConfig}
            series={isShared ? config.series : [dimension.series]}
          />
        </ConfigDimLabel>
      </>
    );
  }
  return <></>;
};

const useVegaReadyTables = (series: SeriesConfig[], frame: Frame) => {
  // This function assigns smart defaults for the color of a point based on the label.

  return useMemo(() => {
    const tables = series.map(s => s.table);
    const allDims = series.map(s => s.dims);

    return tables.map((table, i) => {
      const dims = allDims[i];
      const labelSelectFn = table.columnSelectFunctions[dims.label];
      if (labelSelectFn.nodeType !== 'void') {
        const labelType = TableState.getTableColType(table, dims.label);
        if (frame.runColors != null) {
          if (isAssignableTo(labelType, maybe('run'))) {
            let retTable = TableState.updateColumnSelect(
              table,
              dims.color,
              opPick({
                obj: varNode(frame.runColors.type, 'runColors'),
                key: opRunId({
                  run: labelSelectFn,
                }),
              })
            );

            retTable = TableState.updateColumnSelect(
              retTable,
              dims.label,
              opRunName({
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
              opPick({
                obj: varNode(frame.runColors.type, 'runColors'),
                key: opRunId({
                  run: labelSelectFn.fromOp.inputs.run,
                }),
              })
            );
          }
        }

        if (
          isAssignableTo(
            labelType,
            oneOrMany(maybe(union(['number', 'string', 'boolean'])))
          )
        ) {
          return TableState.updateColumnSelect(
            table,
            dims.color,
            labelSelectFn
          );
        }
      }
      return table;
    });
  }, [series, frame.runColors]);
};

function fixKeyForVegaTable(
  key: string,
  table: TableState.TableState,
  opStore: OpStore
) {
  return PlotState.fixKeyForVega(
    TableState.getTableColumnName(
      table.columnNames,
      table.columnSelectFunctions,
      key,
      opStore
    )
  );
}

function filterTableNodeToContinuousSelection(
  node: Node,
  colId: string,
  table: TableState.TableState,
  domain: ContinuousSelection,
  opStore: OpStore
): OutputNode {
  return opFilter({
    arr: node,
    filterFn: constFunction({row: listObjectType(node.type)}, ({row}) => {
      const colName = escapeDots(
        TableState.getTableColumnName(
          table.columnNames,
          table.columnSelectFunctions,
          colId,
          opStore
        )
      );

      let colNode = opPick({obj: row, key: constString(colName)});

      const domainDiff = domain[1] - domain[0];
      if (isAssignableTo(colNode.type, maybe(timestampBin))) {
        return opAnd({
          lhs: opNumberGreaterEqual({
            lhs: opDateToNumber({
              date: opPick({obj: colNode, key: constString('start')}),
            }),
            rhs: constNumber(
              domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
          rhs: opNumberLessEqual({
            lhs: opDateToNumber({
              date: opPick({obj: colNode, key: constString('stop')}),
            }),
            rhs: constNumber(
              domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
        });
      } else if (isAssignableTo(colNode.type, maybe(numberBin))) {
        return opAnd({
          lhs: opNumberGreaterEqual({
            lhs: opPick({obj: colNode, key: constString('start')}),
            rhs: constNumber(
              domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
          rhs: opNumberLessEqual({
            lhs: opPick({obj: colNode, key: constString('stop')}),
            rhs: constNumber(
              domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
            ),
          }),
        });
      }
      if (
        isAssignableTo(
          colNode.type,
          maybe({
            type: 'timestamp',
            unit: 'ms',
          })
        )
      ) {
        colNode = opDateToNumber({date: colNode});
      }

      return opAnd({
        lhs: opNumberGreaterEqual({
          lhs: colNode,
          rhs: constNumber(
            domain[0] - DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
          ),
        }),
        rhs: opNumberLessEqual({
          lhs: colNode,
          rhs: constNumber(
            domain[1] + DOMAIN_DATAFETCH_EXTRA_EXTENT * domainDiff
          ),
        }),
      });
    }),
  });
}
/*

async function mergeRealizedTableData(
  oldTable: _.Dictionary<any>[],
  newTable: _.Dictionary<any>[]
): Promise<_.Dictionary<any>[]> {
  const flatArray = _.flatten([oldTable, newTable]);
  const uniqueArray = _.uniqBy(flatArray, '_rowIndex');
  return _.sortBy(uniqueArray, '_rowIndex');
}
*/

function filterTableNodeToDiscreteSelection(
  node: Node,
  colId: string,
  table: TableState.TableState,
  domain: DiscreteSelection,
  opStore: OpStore
): OutputNode {
  return opFilter({
    arr: node,
    filterFn: constFunction({row: listObjectType(node.type)}, ({row}) => {
      const colName = escapeDots(
        TableState.getTableColumnName(
          table.columnNames,
          table.columnSelectFunctions,
          colId,
          opStore
        )
      );

      const colNode = opPick({obj: row, key: constString(colName)});
      const permittedValues = constStringList(domain);

      return opContains({
        arr: permittedValues,
        element: colNode,
      });
    }),
  });
}

function filterTableNodeToSelection(
  node: Node,
  axisDomains: AxisSelections,
  series: SeriesConfig,
  axisName: 'x' | 'y',
  opStore: OpStore
): Node {
  const axisType = PlotState.getAxisType(series, axisName);
  const domain = axisDomains[axisName];
  const {table, dims} = series;
  const colId = dims[axisName];
  if (domain) {
    if (axisType === 'quantitative' || axisType === 'temporal') {
      return filterTableNodeToContinuousSelection(
        node,
        colId,
        table,
        domain as ContinuousSelection,
        opStore
      );
    } else if (axisType === 'nominal' || axisType === 'ordinal') {
      return filterTableNodeToDiscreteSelection(
        node,
        colId,
        table,
        domain as DiscreteSelection,
        opStore
      );
    }
    throw new Error('Invalid domain type');
  }
  return node;
}

function getMark(
  series: SeriesConfig,
  tableNode: Node,
  vegaReadyTable: TableState.TableState
): NonNullable<MarkOption> {
  if (series.constants.mark) {
    return series.constants.mark;
  }
  let mark: MarkOption = 'point';
  const objType = listObjectType(tableNode.type);
  const dimTypes = PlotState.getDimTypes(series.dims, vegaReadyTable);

  if (objType != null && objType !== 'invalid') {
    if (!isTypedDict(objType)) {
      throw new Error('Invalid plot data type');
    }
    if (
      isAssignableTo(dimTypes.x, maybe('number')) &&
      isAssignableTo(dimTypes.y, maybe('number'))
    ) {
      mark = 'point';
    } else if (
      isAssignableTo(
        dimTypes.x,
        union(['none', 'string', 'date', numberBin, timestampBin])
      ) &&
      isAssignableTo(dimTypes.y, maybe('number'))
    ) {
      mark = 'bar';
    } else if (
      isAssignableTo(dimTypes.x, maybe('number')) &&
      isAssignableTo(dimTypes.y, union(['string', 'date']))
    ) {
      mark = 'bar';
    } else if (
      isAssignableTo(dimTypes.x, list(maybe('number'))) &&
      isAssignableTo(dimTypes.y, union(['string', 'number']))
    ) {
      mark = 'boxplot';
    } else if (
      isAssignableTo(dimTypes.y, list(maybe('number'))) &&
      isAssignableTo(dimTypes.x, union(['string', 'number']))
    ) {
      mark = 'boxplot';
    } else if (
      isAssignableTo(dimTypes.x, list('number')) &&
      isAssignableTo(dimTypes.y, list('number'))
    ) {
      mark = 'line';
    }
  }

  return mark;
}

type VegaTimeUnit = 'yearweek' | 'yearmonth';

// Color axis type gets a separate function because color axes can share multiple scales - one for each axis type.
function getColorAxisType(
  series: SeriesConfig,
  vegaReadyTable: TableState.TableState
): PlotState.VegaAxisType | undefined {
  let colorAxisType: PlotState.VegaAxisType | undefined;
  const dimTypes = PlotState.getDimTypes(series.dims, vegaReadyTable);
  if (dimTypes.color != null) {
    if (isAssignableTo(dimTypes.color, oneOrMany(maybe('number')))) {
      colorAxisType = 'quantitative';
    } else if (
      isAssignableTo(
        dimTypes.color,
        oneOrMany(maybe(union(['string', 'boolean'])))
      )
    ) {
      colorAxisType = 'nominal';
    }
  }
  return colorAxisType;
}

function getAxisTimeUnit(isDashboard: boolean): VegaTimeUnit {
  return isDashboard ? 'yearweek' : 'yearmonth';
}
/*
const useMergeTables = makePromiseUsable(
  (
    currentData: _.Dictionary<any>[][] | undefined,
    newFlatPlotTables: _.Dictionary<any>[][],
    isLoading: boolean
  ): Promise<_.Dictionary<any>[][]> => {
    if (!isLoading && currentData) {
      return Promise.all(
        newFlatPlotTables.map((table, i) =>
          mergeRealizedTableData(currentData?.[i] ?? [], table)
        )
      );
    }
    return Promise.resolve(currentData || []);
  }
);

const useLatestData = (
  newFlatPlotTables: _.Dictionary<any>[][],
  isLoading: boolean,
  series: SeriesConfig[]
) => {
  const [latestData, setLatestData] = useState<_.Dictionary<any>[][]>([]);
  const seriesRef = useRef<SeriesConfig[]>(series);
  const {result: mergedTables, loading} = useMergeTables(
    latestData,
    newFlatPlotTables,
    isLoading
  );

  if (seriesRef.current !== series) {
    // invalidate prior data
    seriesRef.current = series;
    setLatestData([]);
    return {latestData: [], loading: true};
  } else if (mergedTables !== latestData && !loading) {
    setLatestData(mergedTables);
  } else if (
    loading &&
    latestData.length === 0 &&
    newFlatPlotTables.length > 0
  ) {
    setLatestData(newFlatPlotTables);
  }

  return {latestData, loading};
};
*/

const PanelPlot2Inner: React.FC<PanelPlotProps> = props => {
  const isDash = useWeaveDashUiEnable();
  const weave = useWeaveContext();
  const {
    input,
    updateConfig: propsUpdateConfig,
    updateConfig2: propsUpdateConfig2,
  } = props;
  const isMounted = useIsMounted();

  const [brushMode, setBrushMode] = useState<BrushMode>('zoom');

  // for use in vega callbacks, to ensure we get the latest value
  const brushModeRef = useRef<BrushMode>(brushMode);
  brushModeRef.current = brushMode;

  const isOrgDashboard = useIsOrgDashboard();
  // const isRepoInsightsDashboard = useIsRepoInsightsDashboard();

  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  // TODO(np): Hack to detect when we are on an activity dashboard
  const isDashboard = useIsDashboard();

  const {frame, stack} = usePanelContext();
  const {config, isRefining} = useConfig(input, props.config);

  const panelId = LLReact.useId();

  const {config: unvalidatedConcreteConfig, loading: concreteConfigLoading} =
    useConcreteConfig(config, input, stack, panelId.toString());

  const updateConfig = useCallback(
    (newConfig?: Partial<PlotConfig>) => {
      if (!newConfig) {
        // if config is undefined, just use the default plot
        propsUpdateConfig(defaultPlot(input, stack, !!isDash));
      } else {
        propsUpdateConfig({
          ...config,
          ...newConfig,
        });
      }
    },
    [config, propsUpdateConfig, input, stack, isDash]
  );

  const inputNode = input;

  const updateConfig2 = useCallback(
    (change: (oldConfig: PlotConfig) => PlotConfig) => {
      return propsUpdateConfig2!(change as any);
    },
    [propsUpdateConfig2]
  );

  const updateConfig2Ref = useRef<typeof updateConfig2>(updateConfig2);
  updateConfig2Ref.current = updateConfig2;

  const updateConfigRef = useRef<typeof updateConfig>(updateConfig);
  updateConfigRef.current = updateConfig;

  const concreteConfig = useMemo(
    () => ensureValidSignals(unvalidatedConcreteConfig),
    [unvalidatedConcreteConfig]
  );

  const configRef = useRef<PlotConfig>(config);
  configRef.current = config;

  const concreteConfigRef = useRef<ConcretePlotConfig>(concreteConfig);
  concreteConfigRef.current = concreteConfig;

  // side effect
  useEffect(() => {
    if (config.configVersion !== props.config?.configVersion) {
      // persist the migrated config
      updateConfig(config);
    }
  }, [config, props.config, updateConfig]);

  const vegaReadyTables = useVegaReadyTables(config.series, frame);
  const vegaCols = useMemo(
    () =>
      vegaReadyTables.map((vegaReadyTable, i) =>
        PlotState.dimNames(vegaReadyTable, config.series[i].dims, weave)
      ),
    [config.series, vegaReadyTables, weave]
  );

  const listOfTableNodes = useMemo(() => {
    return vegaReadyTables.map(val =>
      opUnnest({
        arr: TableState.tableGetResultTableNode(val, inputNode, weave)
          .resultNode,
      })
    );
  }, [vegaReadyTables, inputNode, weave]);

  const flatResultNode = useMemo(() => {
    const arrayArg: {
      [key: number]: ReturnType<
        typeof TableState.tableGetResultTableNode
      >['resultNode'];
    } = {};

    const reduced = vegaReadyTables.reduce((acc, val, i) => {
      let node: Node = listOfTableNodes[i];

      if (isDash) {
        const series = config.series[i];

        const mark = getMark(series, node, series.table);
        if (['bar', 'line', 'point', 'area'].includes(mark)) {
          ['x' as const].forEach(axisName => {
            node = filterTableNodeToSelection(
              node,
              concreteConfig.signals.domain,
              series,
              axisName,
              weave.client.opStore
            );
          });
        }
        // If we have a nominal axis, limit it. We can end up with
        // tons of unique values and Vega will basically hang.
        const xAxisType = PlotState.getAxisType(concreteConfig.series[0], 'x');
        const yAxisType = PlotState.getAxisType(concreteConfig.series[0], 'y');
        if (xAxisType === 'nominal' || yAxisType === 'nominal') {
          node = opLimit({
            arr: node,
            limit: constNumber(50),
          });
        }
      }

      /*
      if (isDash) {
        node = opRandomlyDownsample({
          arr: node,
          n: constNumber(PANELPLOT_MAX_DATAPOINTS),
        });
      }
      */

      acc[i] = node;

      return acc;
    }, arrayArg);
    return opArray(reduced as any);
  }, [
    vegaReadyTables,
    listOfTableNodes,
    isDash,
    config.series,
    concreteConfig.series,
    concreteConfig.signals.domain,
    weave.client.opStore,
  ]); // , isDash]);

  const flatResultNodeRef = useRef(flatResultNode);

  const flatResultNodeDidChange = flatResultNode !== flatResultNodeRef.current;

  flatResultNodeRef.current = flatResultNode;

  const result = LLReact.useNodeValue(flatResultNode, {
    callSite: 'PanelPlot.flatResultNode.' + panelId,
    skip: isRefining || concreteConfigLoading,
  });

  // enables domain sharing

  const makeHandleRootUpdate = useCallback(
    (dimName: 'x' | 'y') => {
      return (newVal: Node) => {
        const currDomain = configRef.current.signals.domain[dimName];
        if (!weave.isExpLogicallyEqual(newVal, currDomain)) {
          updateConfig2((oldConfig: PlotConfig) => {
            return {
              ...oldConfig,
              signals: {
                ...oldConfig.signals,
                domain: {...oldConfig.signals.domain, [dimName]: newVal as any},
              },
            };
          });
        }
      };
    },
    [updateConfig2, weave]
  );

  const handleRootUpdateX = useMemo(
    () => makeHandleRootUpdate('x'),
    [makeHandleRootUpdate]
  );

  const handleRootUpdateY = useMemo(
    () => makeHandleRootUpdate('y'),
    [makeHandleRootUpdate]
  );

  const handleRootUpdate = useMemo(
    () => ({
      x: handleRootUpdateX,
      y: handleRootUpdateY,
    }),
    [handleRootUpdateX, handleRootUpdateY]
  );
  const handleRootUpdateRef = useRef(handleRootUpdate);
  handleRootUpdateRef.current = handleRootUpdate;

  const mutateDomainX = LLReact.useMutation(
    config.signals.domain.x,
    'set',
    handleRootUpdateX,
    false
  );

  const mutateDomainY = LLReact.useMutation(
    config.signals.domain.y,
    'set',
    handleRootUpdateY,
    false
  );

  const mutateDomain = useMemo(
    () => ({x: mutateDomainX, y: mutateDomainY}),
    [mutateDomainX, mutateDomainY]
  );

  const mutateDomainRef = useRef(mutateDomain);
  mutateDomainRef.current = mutateDomain;

  const loading = useMemo(
    () => result.loading || concreteConfigLoading || isRefining,
    [result.loading, concreteConfigLoading, isRefining]
  );

  const plotTables = useMemo(
    () => (loading ? [] : (result.result as any[][])),
    [result, loading]
  );

  const hasLine = useMemo(
    () =>
      concreteConfig == null || loading
        ? false
        : concreteConfig.series
            .map((s, i) => getMark(s, listOfTableNodes[i], vegaReadyTables[i]))
            .some(mark => mark === 'line'),
    [concreteConfig, loading, listOfTableNodes, vegaReadyTables]
  );

  const flatPlotTables = useMemo(
    () =>
      plotTables.map((table, i) =>
        table.map((row, j) =>
          _.set(
            _.set(
              _.mapKeys(row, (v, k) => PlotState.fixKeyForVega(k)),
              '_seriesIndex',
              i
            ),
            '_rowIndex',
            j
          )
        )
      ),
    [plotTables]
  );

  /* TODO: fix
  const {latestData: flatPlotTables} = useLatestData(
    newFlatPlotTables,
    isRefining || result.loading,
    config.series
  );
  */

  function scaleToVegaScale(s: Scale) {
    return _.mapKeys(_.omitBy(s, _.isNil), (v, k) =>
      k === 'scaleType' ? 'type' : k
    );
  }

  type DiscreteMappingScale = {domain: string[]; range: number[][]};
  const lineStyleScale: DiscreteMappingScale = useMemo(() => {
    const scale: DiscreteMappingScale = {
      domain: [],
      range: [],
    };

    const strokeDashesSeen = new Set<
      Omit<SeriesConfig['constants']['lineStyle'], 'series'>
    >();

    const getStrokeDash = (
      lineStyle: SeriesConfig['constants']['lineStyle']
    ): number[] => {
      // this is the default vega-lite dash sequence, see
      // https://github.com/vega/vega-lite/pull/5860/files#diff-c61ed7fffbf0c752e59f1f7e079f673919d871991fab41de7c4f4e7903e1c2cbR206
      const dashMap = {
        solid: [1, 0],
        dashed: [4, 2],
        'short-dashed': [2, 1],
        dotted: [1, 1],
        'dot-dashed': [1, 2, 4, 2],
      };

      if (lineStyle !== 'series') {
        strokeDashesSeen.add(lineStyle);
        return dashMap[lineStyle];
      }
      if (strokeDashesSeen.size === LINE_SHAPES.length - 1) {
        strokeDashesSeen.clear();
      }
      for (const dash of LINE_SHAPES) {
        if (dash === 'series') {
          continue;
        }
        if (!strokeDashesSeen.has(dash)) {
          strokeDashesSeen.add(dash);
          return dashMap[dash];
        }
      }
      return dashMap.solid;
    };

    flatPlotTables
      .filter(
        (table, i) =>
          getMark(
            concreteConfig.series[i],
            listOfTableNodes[i],
            vegaReadyTables[i]
          ) === 'line'
      )
      .forEach((table, i) => {
        scale.domain.push(
          PlotState.defaultSeriesName(concreteConfig.series[i], weave)
        );
        scale.range.push(
          getStrokeDash(concreteConfig.series[i].constants.lineStyle)
        );
      });
    return scale;
  }, [
    weave,
    concreteConfig.series,
    flatPlotTables,
    listOfTableNodes,
    vegaReadyTables,
  ]);

  const colorFieldIsRangeForSeries = useMemo(
    () =>
      flatPlotTables.map((table, i) =>
        table.some(row => stringIsColorLike(String(row[vegaCols[i].color])))
      ),
    [flatPlotTables, vegaCols]
  );

  const [toolTipsEnabled, setToolTipsEnabled] = useState<boolean>(true);
  const tooltipsEnabledRef = useRef<boolean>(toolTipsEnabled);
  tooltipsEnabledRef.current = toolTipsEnabled;
  const setToolTipsEnabledRef =
    useRef<typeof setToolTipsEnabled>(setToolTipsEnabled);
  setToolTipsEnabledRef.current = setToolTipsEnabled;

  const concattedTable = useMemo(() => flatPlotTables.flat(), [flatPlotTables]);

  const getMarkForRow = useCallback(
    (row: any): MarkOption => {
      const s = concreteConfig.series[row._seriesIndex];
      return getMark(
        s,
        listOfTableNodes[row._seriesIndex],
        vegaReadyTables[row._seriesIndex]
      );
    },
    [concreteConfig.series, listOfTableNodes, vegaReadyTables]
  );

  const concattedLineTable = useMemo(() => {
    return concattedTable.filter(row => {
      const mark = getMarkForRow(row);
      return mark === 'line';
    });
  }, [concattedTable, getMarkForRow]);

  const concattedNonLineTable = useMemo(() => {
    return concattedTable.filter(row => {
      const mark = getMarkForRow(row);
      return mark !== 'line';
    });
  }, [concattedTable, getMarkForRow]);

  const normalizedTable = useMemo(() => {
    const colNameLookups = vegaCols.map(mapping => _.invert(mapping));
    return concattedLineTable.map(row =>
      _.mapKeys(row, (v, k) =>
        ['_rowIndex', '_seriesIndex'].includes(k)
          ? k
          : colNameLookups[row._seriesIndex][k]
      )
    );
  }, [concattedLineTable, vegaCols]);

  const tooltipData: {[seriesIndexRowIndexString: string]: ConstNode} =
    useMemo(() => {
      type ExprDimNameType = (typeof PlotState.EXPRESSION_DIM_NAMES)[number];

      return concattedNonLineTable.reduce(
        (acc: {[seriesIndexRowIndexString: string]: ConstNode}, row) => {
          const key = `[${row._seriesIndex},${row._rowIndex}]`;

          // check if we have a null select function, and thus are using the default tooltip
          const s = concreteConfig.series[row._seriesIndex];
          const colId = s.dims.tooltip;
          const selectFn = s.table.columnSelectFunctions[colId];
          if (isVoidNode(selectFn)) {
            // use default tooltip
            const nonNullDims: ExprDimNameType[] = [];

            const propertyTypes = PlotState.EXPRESSION_DIM_NAMES.reduce(
              (acc: {[vegaColName: string]: Type}, dim: ExprDimNameType) => {
                const colId = s.dims[dim];

                if (!isVoidNode(s.table.columnSelectFunctions[colId])) {
                  nonNullDims.push(dim);
                  const colType = s.table.columnSelectFunctions[colId].type;

                  acc[vegaCols[row._seriesIndex][dim]] = isTaggedValue(colType)
                    ? taggedValueValueType(colType)
                    : colType;
                }

                return acc;
              },
              {}
            );
            const type = typedDict(propertyTypes);

            acc[key] = constNodeUnsafe(type, row);
          } else {
            // use custom tooltip
            acc[key] = constNodeUnsafe(
              s.table.columnSelectFunctions[s.dims.tooltip].type,
              row[vegaCols[row._seriesIndex].tooltip]
            );
          }

          return acc;
        },
        {}
      );
    }, [concattedNonLineTable, concreteConfig.series, vegaCols]);

  const tooltipLineData: {[x: string]: ConstNode} = useMemo(() => {
    // concatenate all plot tables into one and group by x value
    const showSeries = concreteConfig.series.length > 1;
    return _.mapValues(
      _.groupBy(concattedLineTable, row => row[vegaCols[row._seriesIndex].x]),
      rows => {
        // TODO: see if this should be renamed
        const nodeValue: {[key: string]: any} = {};
        const nodeType: {[key: string]: Type} = {};
        const {nodeValue: value, nodeType: type} = rows.reduce(
          (acc, row) => {
            const {nodeValue: currNodeValue, nodeType: currNodeType} = acc;
            const rowType = listObjectType(
              listOfTableNodes[row._seriesIndex].type
            );
            if (!isTypedDict(rowType)) {
              throw new Error('expected typed dict');
            }
            const mappedPropTypes = _.mapValues(
              _.mapKeys(rowType.propertyTypes, (v, k) =>
                PlotState.fixKeyForVega(k)
              ),
              (v, k) => (v && isTaggedValue(v) ? taggedValueValueType(v) : v)
            );
            const series = concreteConfig.series[row._seriesIndex];
            const seriesName = PlotState.defaultSeriesName(series, weave);

            // x
            const xColName = vegaCols[row._seriesIndex].x;
            const xVal = row[xColName];

            const yColName = vegaCols[row._seriesIndex].y;
            const yVal = row[yColName];

            // do a domain check
            // TODO: make this work for discrete domains
            let returnEarly = false;
            ['x' as const, 'y' as const].forEach(axis => {
              const domain = concreteConfig.signals.domain[axis];
              if (domain) {
                if (
                  !PlotState.selectionContainsValue(
                    domain,
                    axis === 'x' ? xVal : yVal
                  )
                ) {
                  returnEarly = true;
                }
              }
            });

            if (returnEarly) {
              return acc;
            }

            currNodeValue[xColName] = xVal;
            currNodeType[xColName] = mappedPropTypes[xColName];

            // y or tooltip
            const tooltipSelectFn =
              vegaReadyTables[row._seriesIndex].columnSelectFunctions[
                series.dims.tooltip
              ];
            const label = row[vegaCols[row._seriesIndex].label];
            const key = showSeries
              ? `${seriesName}${label != null ? ', ' + label : ''}`
              : label || seriesName;

            if (isVoidNode(tooltipSelectFn)) {
              currNodeValue[key] = row[vegaCols[row._seriesIndex].y];
              currNodeType[key] = mappedPropTypes[vegaCols[row._seriesIndex].y];
            } else {
              currNodeValue[key] = row[vegaCols[row._seriesIndex].tooltip];
              currNodeType[key] =
                mappedPropTypes[vegaCols[row._seriesIndex].tooltip];
            }
            return {nodeValue: currNodeValue, nodeType: currNodeType};
          },
          {nodeValue, nodeType}
        );

        return constNodeUnsafe(typedDict(type), value);
      }
    );
  }, [
    concreteConfig.series,
    concattedLineTable,
    vegaCols,
    listOfTableNodes,
    weave,
    vegaReadyTables,
    concreteConfig.signals.domain,
  ]);

  const brushableAxes = useMemo(() => {
    const brushTypes = ['x' as const, 'y' as const].map(axisName => {
      // Sum and count operations are "extensive" properties meaning
      // they depend on the size of the sample, while other operations
      // like min/max/avg are "intensive" properties meaning they do not.
      // (thanks gpt-4 for these definitions!)
      // We like to configure the plot such that it rebins
      // along the groupby axis (e.g. time) after zooming, which means
      // the amount of points falling in each bin will change. The result
      // of extensive operations will differ given the new bin size in
      // these cases, and the data ends up "below" where it was when
      // the user initiated the zoom. So we just disable brushing on
      // extensive axes, and let the plot figure out the new extent
      // automatically.
      const seriesHasUnstableAggs = listOfTableNodes.map((n, i) => {
        const series = config.series[i];
        const seriesSelectFn =
          series.table.columnSelectFunctions[series.dims[axisName]];
        return (
          filterNodes(
            seriesSelectFn,
            selFn =>
              selFn.nodeType === 'output' &&
              (selFn.fromOp.name === 'count' ||
                selFn.fromOp.name.endsWith('sum'))
          ).length > 0
        );
      });
      if (seriesHasUnstableAggs.includes(true)) {
        return undefined;
      }
      const seriesTypes = listOfTableNodes.reduce((acc, node, i) => {
        const dimName = PlotState.dimNamesRaw(
          config.series[i].table,
          config.series[i].dims,
          weave
        )[axisName];
        const rowType = withoutTags(listObjectType(node.type)) as TypedDictType;
        const dimType = rowType.propertyTypes[dimName];
        if (dimType != null) {
          acc.push(dimType);
        }
        return acc;
      }, [] as Type[]);

      const uniqueTypes = _.uniqBy(seriesTypes, JSON.stringify);

      let axisType: Type | undefined = 'invalid';
      if (uniqueTypes.length > 2) {
        return undefined;
      } else if (uniqueTypes.length === 2 && !uniqueTypes.includes('invalid')) {
        return undefined;
      } else if (uniqueTypes.length === 2) {
        uniqueTypes.forEach(type => {
          if (type !== 'invalid') {
            axisType = type;
          }
        });
      } else {
        axisType = uniqueTypes.values().next().value;
      }

      if (axisType == null) {
        return undefined;
      }

      if (
        isAssignableTo(axisType, oneOrMany(maybe('number'))) ||
        isAssignableTo(axisType, oneOrMany(maybe(numberBin)))
      ) {
        return 'quantitative';
      }

      if (
        isAssignableTo(axisType, oneOrMany(maybe({type: 'timestamp'}))) ||
        isAssignableTo(axisType, oneOrMany(maybe(timestampBin)))
      ) {
        return 'temporal';
      }

      return undefined;
    });
    type BrushType = 'temporal' | 'quantitative';
    const brushTypesResult: {x?: BrushType; y?: BrushType} = {};
    if (brushTypes[0] != null) {
      brushTypesResult.x = brushTypes[0];
    }
    if (brushTypes[1] != null) {
      brushTypesResult.y = brushTypes[1];
    }
    return brushTypesResult;
  }, [listOfTableNodes, config.series, weave]);

  const xScaleAndDomain = useMemo(
    () =>
      concreteConfig.signals.domain.x
        ? {scale: {domain: concreteConfig.signals.domain.x}}
        : {},
    [concreteConfig.signals.domain.x]
  );
  const yScaleAndDomain = useMemo(
    () =>
      concreteConfig.signals.domain.y
        ? {scale: {domain: concreteConfig.signals.domain.y}}
        : {},
    [concreteConfig.signals.domain.y]
  );

  const [globalColorScales, setGlobalColorScales] = useState<any[]>();

  const hasLineRef = useRef(hasLine);
  hasLineRef.current = hasLine;
  const globalColorScalesRef = useRef(globalColorScales);
  globalColorScalesRef.current = globalColorScales;
  const setGlobalColorScalesRef = useRef(setGlobalColorScales);
  setGlobalColorScalesRef.current = setGlobalColorScales;
  const needsNewColorScaleRef = useRef(true);

  const layerSpecs = useMemo(() => {
    const dataSpecs = flatPlotTables.map((flatPlotTable, i) => {
      const vegaReadyTable = vegaReadyTables[i];
      const series = concreteConfig.series[i];
      // filter out weave1 _type key
      const dims = _.omitBy(series.dims, (v, k) =>
        k.startsWith('_')
      ) as SeriesConfig['dims'];
      const dimTypes = PlotState.getDimTypes(dims, vegaReadyTable);
      const colorFieldIsRange = colorFieldIsRangeForSeries[i];

      const objType = listObjectType(listOfTableNodes[i].type);

      if (!isTypedDict(objType)) {
        throw new Error('Invalid plot data type');
      }

      const xAxisType = PlotState.getAxisType(concreteConfig.series[0], 'x');
      const yAxisType = PlotState.getAxisType(concreteConfig.series[0], 'y');

      const xTimeUnit = getAxisTimeUnit(isDashboard);
      const yTimeUnit = getAxisTimeUnit(isDashboard);

      const colorAxisType = getColorAxisType(series, vegaReadyTable);

      const mark: NonNullable<MarkOption> = getMark(
        series,
        listOfTableNodes[i],
        vegaReadyTable
      );

      const newSpec = _.merge(
        _.cloneDeep(PLOT_TEMPLATE),
        isOrgDashboard ? _.cloneDeep(ORG_DASHBOARD_TEMPLATE_OVERLAY) : {},
        concreteConfig?.vegaOverlay ?? {}
      );

      // create the data spec for the layer
      newSpec.data = {name: `wandb-${i}`};
      newSpec.name = `Layer${i + 1}`;
      newSpec.transform = [];

      const fixKeyForVega = (key: string) =>
        fixKeyForVegaTable(key, vegaReadyTable, weave.client.opStore);

      if (xAxisType != null) {
        const fixedXKey = fixKeyForVega(dims.x);
        if (
          isAssignableTo(dimTypes.x, maybe(numberBin)) ||
          isAssignableTo(dimTypes.x, maybe(timestampBin))
        ) {
          if (mark === 'bar') {
            newSpec.encoding.x = {
              field: fixedXKey + '.start',
              type: xAxisType,
            };
            newSpec.encoding.x2 = {
              field: fixedXKey + '.stop',
              type: xAxisType,
            };
          } else {
            newSpec.transform.push({
              calculate: `0.5 * (datum['${fixedXKey}'].stop + datum['${fixedXKey}'].start)`,
              as: `${fixedXKey}_center`,
            });
            newSpec.encoding.x = {
              field: `${fixedXKey}_center`,
              type: xAxisType,
            };
          }
        } else {
          newSpec.encoding.x = {
            field: fixedXKey,
            type: xAxisType,
            ...xScaleAndDomain,
          };
        }
        if (xAxisType === 'temporal' && xTimeUnit && isDashboard) {
          newSpec.encoding.x.timeUnit = xTimeUnit;
        }
      }

      newSpec.mark.type = mark;
      newSpec.mark.clip = true; // ensures that marks don't overflow the plot area

      if (yAxisType != null) {
        const fixedYKey = fixKeyForVega(dims.y);
        if (
          isAssignableTo(dimTypes.y, maybe(numberBin)) &&
          newSpec.mark.type !== 'area'
        ) {
          newSpec.encoding.y = {
            field: fixedYKey + '.start',
            type: yAxisType,
          };
          newSpec.encoding.y2 = {
            field: fixedYKey + '.stop',
            type: yAxisType,
          };
        } else if (
          newSpec.mark.type === 'area' &&
          isAssignableTo(dimTypes.y2, dimTypes.y)
        ) {
          const fixedY2Key = fixKeyForVega(dims.y2);
          newSpec.encoding.y = {
            field: fixedYKey,
            type: yAxisType,
          };
          newSpec.encoding.y2 = {
            field: fixedY2Key,
            type: yAxisType,
          };
          newSpec.mark.opacity = 0.2;
        } else {
          newSpec.encoding.y = {
            field: fixedYKey,
            type: yAxisType,
          };
          if (yAxisType === 'temporal' && yTimeUnit) {
            newSpec.encoding.y.timeUnit = yTimeUnit;
          }
        }
      }

      if (colorAxisType != null && series.uiState.label === 'expression') {
        newSpec.encoding.color = {
          field: fixKeyForVega(dims.color),
          type: colorAxisType,
        };
        if (
          vegaReadyTable.columnSelectFunctions[dims.label].type !== 'invalid'
        ) {
          newSpec.encoding.color.field = fixKeyForVega(dims.label);
          if (colorFieldIsRange) {
            newSpec.encoding.color.scale = {
              range: {field: fixKeyForVega(dims.color)},
            };
          }
        }
      } else if (series.uiState.label === 'dropdown') {
        newSpec.encoding.color = {
          datum: PlotState.defaultSeriesName(series, weave),
          title: 'series',
          legend: concreteConfig.legendSettings.color.noLegend
            ? false
            : {...defaultFontStyleDict},
        };
      }

      if (newSpec.mark.type === 'point') {
        newSpec.mark.filled = true;

        if (dims.pointSize && !isAssignableTo(dimTypes.pointSize, 'invalid')) {
          const pointSizeKey = fixKeyForVega(dims.pointSize);
          let pointSizeIsConst = false;
          const pointSizesSeen = new Set<number>();
          if (isAssignableTo(dimTypes.pointSize, 'number')) {
            for (const row of flatPlotTable) {
              pointSizesSeen.add(row[pointSizeKey]);
            }
            if (pointSizesSeen.size <= 1) {
              pointSizeIsConst = true;
            }
          }

          // if the expression provided for the point size evaluates to a
          // column where every cell is the same number, then interpret the
          // point not as an encoding but as a direct specification of the
          // point size in absolute units. otherwise, encode the values
          // using the default vega-lite scale.
          if (pointSizeIsConst) {
            newSpec.mark.size = pointSizesSeen.values().next().value;
          } else {
            newSpec.encoding.size = {
              field: fixKeyForVega(dims.pointSize),
              legend: concreteConfig.legendSettings.pointSize.noLegend
                ? false
                : {...defaultFontStyleDict},
            };

            if (isAssignableTo(dimTypes.pointSize, maybe('number'))) {
              newSpec.encoding.size.type = 'quantitative';
            }
          }
        }

        if (
          dims.pointShape &&
          !isAssignableTo(dimTypes.pointShape, 'invalid') &&
          series.uiState.pointShape === 'expression'
        ) {
          const pointShapeKey = fixKeyForVega(dims.pointShape);
          const pointShapesShouldBeEncoded = !(
            isAssignableTo(dimTypes.pointShape, 'string') &&
            flatPlotTable.every(row =>
              POINT_SHAPES.includes(row[pointShapeKey])
            )
          );

          newSpec.encoding.shape = {
            legend: concreteConfig.legendSettings.pointShape.noLegend
              ? false
              : {...defaultFontStyleDict},
            field: fixKeyForVega(dims.pointShape),
          };

          if (!pointShapesShouldBeEncoded) {
            newSpec.encoding.shape.scale = null;
          }
        }

        if (series.uiState.pointShape === 'dropdown') {
          if (series.constants.pointShape !== 'series') {
            newSpec.mark.shape = series.constants.pointShape;
          } else {
            newSpec.encoding.shape = {
              legend: concreteConfig.legendSettings.pointShape.noLegend
                ? false
                : {...defaultFontStyleDict},
              datum: PlotState.defaultSeriesName(series, weave),
              title: 'series',
            };
          }
        }
      }

      if (newSpec.mark.type === 'line') {
        const lineStyle = {
          mark: {
            type: 'line',
          },
          encoding: {
            strokeDash: {
              datum: PlotState.defaultSeriesName(series, weave),
              legend:
                concreteConfig.series.length > 1 &&
                !concreteConfig.legendSettings.lineStyle.noLegend
                  ? {...defaultFontStyleDict}
                  : false,
              title: 'series',
              scale: lineStyleScale,
            },
          },
        };

        newSpec.mark = {...newSpec.mark, ...lineStyle.mark};
        newSpec.encoding.strokeDash = lineStyle.encoding.strokeDash;
      }

      if (newSpec.mark.type === 'boxplot' && !newSpec.encoding.tooltip) {
        newSpec.mark = 'boxplot';
        newSpec.encoding.tooltip = {
          field: TableState.getTableColumnName(
            vegaReadyTable.columnNames,
            vegaReadyTable.columnSelectFunctions,
            dims.tooltip ?? dims.y,
            weave.client.opStore
          ),
        };
      }

      if (newSpec.mark.type === 'bar') {
        // If we have start and end for an x or y dimension, but only
        // center for the other dimension, tell vega to aggregate the
        // other dimension. Since we always provide pre-computed to
        // vega, the aggregation has no effect on the actual data. But
        // This fixes an issue where Vega will only draw the "top" of
        // the bar.
        if (newSpec.encoding.x2 != null && newSpec.encoding.y2 == null) {
          newSpec.encoding.y.aggregate = 'sum';
        } else if (newSpec.encoding.y2 != null && newSpec.encoding.x2 == null) {
          newSpec.encoding.x.aggregate = 'sum';
        }
      }

      if (!newSpec.encoding.tooltip) {
        newSpec.transform = [
          {
            calculate: `datum`,
            as: '__row',
          },
        ];
        newSpec.encoding.tooltip = {
          field: '__row',
        };
      }

      if (!newSpec.encoding.y) {
        newSpec.encoding.y = {};
      }

      if (!_.isEmpty(yScaleAndDomain)) {
        newSpec.encoding.y = _.merge(newSpec.encoding.y ?? {}, yScaleAndDomain);
      }

      newSpec.name = `Series-${i}`;
      return newSpec;
    });

    const lineSpecs = dataSpecs.filter(spec => spec.mark.type === 'line');
    const otherSpecs = dataSpecs.filter(spec => spec.mark.type !== 'line');

    if (dataSpecs.length === 0) {
      return dataSpecs;
    }

    const scalesAndDomains = {
      x: xScaleAndDomain,
      y: yScaleAndDomain,
      // force view to rerender after setting globalColorScale
      color: {
        scale: null,
        name: stringHashCode(
          JSON.stringify(
            globalColorScales?.map(scale => ({
              domain: scale.domain(),
              range: scale.range(),
              type: scale.type,
            })) ?? ''
          )
        ),
        type: 'ordinal',
      },
    };

    const dummyEncodings = dataSpecs.reduce((acc, spec) => {
      ['x' as const, 'y' as const, 'color' as const].forEach(key => {
        if (spec.encoding[key] && !acc[key]) {
          acc[key] = {
            field: key,
            type: spec.encoding[key].type,
            legend: false,
            ...scalesAndDomains[key],
          };
        }
      });
      return acc;
    }, {});

    const lineTooltipSpec = {
      data: {name: `wandb-${concreteConfig.series.length}`},
      encoding: _.pick(dummyEncodings, ['x']),
      layer: [
        {
          encoding: _.pick(dummyEncodings, ['y', 'color']),
          layer: [
            {
              transform: [{filter: {param: 'hover', empty: false}}],
              mark: 'point',
            },
          ],
        },
        {
          transform: [
            {
              pivot: 'color',
              value: 'y',
              groupby: ['x'],
            },
          ],
          mark: 'rule',
          encoding: {
            opacity: {
              condition: {value: 0.3, param: `hover`, empty: false},
              value: 0,
            },
            tooltip: {
              field: 'x',
            },
          },
          params: [
            {
              name: `hover`,
              select: {
                type: 'point',
                fields: ['x'],
                nearest: true,
                // capture mouse move events even when no button is pressed (i.e., when hovering).
                on: 'mouseover[event.buttons === 0]',
                clear: 'mouseout',
              },
            },
          ],
        },
      ],
    };

    let brushSpec: any[] = [];

    if (!isDashboard) {
      brushSpec = [
        {
          // filter out all data from this spec, this is just for rendering the brush zoom.
          transform: [{filter: 'false'}],
          data: {name: `wandb-${concreteConfig.series.length}`},
          encoding: _.pick(dummyEncodings, ['x', 'y']),
          mark: 'point',
          params: [
            {
              name: 'brush',
              select: {
                type: 'interval',
                encodings: Object.keys(brushableAxes),
              },
            },
          ],
        },
      ];
    }

    return [
      ...lineSpecs,
      ...(hasLine ? [lineTooltipSpec] : []),
      ...otherSpecs,
      ...brushSpec,
    ];
  }, [
    weave,
    lineStyleScale,
    flatPlotTables,
    vegaReadyTables,
    colorFieldIsRangeForSeries,
    listOfTableNodes,
    isOrgDashboard,
    concreteConfig.series,
    concreteConfig?.vegaOverlay,
    concreteConfig.legendSettings,
    isDashboard,
    hasLine,
    brushableAxes,
    xScaleAndDomain,
    yScaleAndDomain,
    globalColorScales,
  ]);

  useEffect(() => {
    if (flatResultNodeDidChange) {
      needsNewColorScaleRef.current = true;
    }
  }, [flatResultNodeDidChange]);

  const dataToPassToCustomPanelRenderer: MultiTableDataType = useMemo(() => {
    const data: MultiTableDataType = {};
    flatPlotTables.forEach((table, i) => {
      data[`wandb-${i}`] = table.filter(row => {
        // filter last table to domain, if set
        if (
          layerSpecs[i].mark?.type === 'line' &&
          (row[vegaCols[i].x] == null || row[vegaCols[i].y] == null)
        ) {
          return false;
        }

        for (const axis of [`x`, `y`] as const) {
          if (
            concreteConfig.axisSettings[axis].scale?.scaleType === `log` &&
            row[vegaCols[i][axis]] <= 0
          ) {
            return false;
          }
        }

        return true;
      });
    });
    const lineTooltipData = normalizedTable.filter(row => {
      for (const axis of [`x`, `y`] as const) {
        const domain = concreteConfig.signals.domain[axis];
        if (domain) {
          if (!PlotState.selectionContainsValue(domain, row[axis])) {
            return false;
          }
        }
      }

      return true;
    });

    if (globalColorScales) {
      lineTooltipData.forEach(row => {
        if (row.label != null) {
          const scale = globalColorScales?.[row._seriesIndex];
          if (scale) {
            row.color = scale(row.label);
          }
        }
      });
    }
    if (hasLine || !isDashboard) {
      data[`wandb-${concreteConfig.series.length}`] = lineTooltipData;
    }
    return data;
  }, [
    hasLine,
    isDashboard,
    flatPlotTables,
    vegaCols,
    layerSpecs,
    normalizedTable,
    concreteConfig.axisSettings,
    concreteConfig.series,
    concreteConfig.signals.domain,
    globalColorScales,
  ]);

  const vegaSpec = useMemo(() => {
    const newSpec: any = {layer: layerSpecs};
    const axisSettings = concreteConfig.axisSettings;
    const legendSettings = concreteConfig.legendSettings;
    newSpec.encoding = {x: {axis: {}}, y: {axis: {}}, color: {axis: {}}};
    if (layerSpecs.some(spec => spec.encoding?.x != null)) {
      ['x' as const, 'y' as const, 'color' as const].forEach(axisName => {
        newSpec.encoding[axisName] = {};
        newSpec.encoding[axisName].axis = {};
      });

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
      newSpec.encoding.x.scale = scaleToVegaScale(axisSettings.x.scale);
    }
    if (axisSettings.x.noTitle) {
      newSpec.encoding.x.axis.title = null;
    } else {
      newSpec.encoding.x.axis.title =
        axisSettings.x.title ??
        PlotState.defaultAxisLabel(concreteConfig.series, 'x', weave);
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
    } else {
      // set the maximum length of x axis labels to be 75 pixels
      newSpec.encoding.x.axis.labelLimit = 75;
    }
    if (newSpec.encoding.y != null) {
      newSpec.encoding.y.axis = {...defaultFontStyleDict};
      // TODO(np): fixme
      if (axisSettings.y.scale != null) {
        newSpec.encoding.y.scale = scaleToVegaScale(axisSettings.y.scale);
      }
      if (axisSettings.y.noTitle) {
        newSpec.encoding.y.axis.title = null;
      } else {
        newSpec.encoding.y.axis.title =
          axisSettings.y.title ??
          PlotState.defaultAxisLabel(concreteConfig.series, 'y', weave);
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
    }

    if (newSpec.encoding.color != null) {
      if (axisSettings?.color?.scale != null) {
        newSpec.encoding.color.scale = scaleToVegaScale(
          axisSettings.color.scale
        );
      }

      if (axisSettings.color && axisSettings.color.noTitle) {
        newSpec.encoding.color.title = null;
      } else {
        newSpec.encoding.color.title =
          axisSettings.color?.title ??
          PlotState.defaultAxisLabel(concreteConfig.series, 'label', weave);
      }

      if (legendSettings.color.noLegend) {
        newSpec.encoding.color.legend = false;
      } else if (!newSpec.encoding.color.legend) {
        newSpec.encoding.color.legend = {...defaultFontStyleDict};
      }
    }
    return newSpec;
  }, [
    weave,
    concreteConfig.series,
    isDashboard,
    layerSpecs,
    concreteConfig.axisSettings,
    concreteConfig.legendSettings,
  ]);

  // get the series object from the config by its index
  const getSeriesBySeriesIndex = useCallback(
    (index: number | undefined) => {
      if (index !== undefined) {
        return config.series[index];
      }
      return undefined;
    },
    [config.series]
  );

  const toolTipRef = useRef<HTMLDivElement>(null);
  const onNewVegaView = useCallback(
    (vegaView: VegaView) => {
      // draw the brush
      let action = vegaView;
      const brushStore = {
        unit: `layer_${concreteConfig.series.length + (hasLine ? 1 : 0)}`,
        fields: [] as Array<{field: string; channel: string; type: string}>,
      };

      ['x' as const, 'y' as const].forEach(axisName => {
        const axisSelection = concreteConfig.signals.selection[axisName];
        if (axisSelection) {
          action = action.signal(`brush_${axisName}`, axisSelection);
          brushStore.fields.push({
            field: axisName,
            channel: axisName,
            type: PlotState.selectionIsContinuous(axisSelection) ? 'R' : 'E',
          });
        }
      });

      if (brushStore.fields.length > 0) {
        action = action.data('brush_store', brushStore);
      }

      action.run();

      // extract scales and set them for line tooltips

      let hasUnit = true;
      try {
        vegaView.signal('unit');
      } catch (e) {
        hasUnit = false;
      }

      if (hasUnit) {
        vegaView.addSignalListener('unit', (name, value) => {
          const currHasLine = hasLineRef.current;
          const currConfig = concreteConfigRef.current;
          const currSetGlobalColorScales = setGlobalColorScalesRef.current;
          const currNeedsNewColorScale = needsNewColorScaleRef.current;

          if (currHasLine && currNeedsNewColorScale) {
            const colorScales = currConfig.series.map((spec, i) => {
              try {
                return vegaView.scale(`Series_${i}_color`);
              } catch (e) {
                return vegaView.scale('color');
              }
            });
            currSetGlobalColorScales(colorScales);
            needsNewColorScaleRef.current = false;
          }
        });
      }

      vegaView.addEventListener('mouseup', async () => {
        const currBrushMode = brushModeRef.current;
        const currUpdateConfig2 = updateConfig2Ref.current;
        const currMutateDomain = mutateDomainRef.current;
        const currConcreteConfig = concreteConfigRef.current;
        const currSetToolTipsEnabled = setToolTipsEnabledRef.current;
        const signalName = `brush`;
        const dataName = `brush_store`;

        const selection = vegaView.getState({
          signals: name => name === signalName,
          data: (name?: string) => !!name && name.includes(dataName),
        });

        const signal = selection?.signals[signalName];
        const data = selection?.data[dataName];

        if (!_.isEmpty(signal)) {
          const settingName = currBrushMode === 'zoom' ? 'domain' : 'selection';

          if (settingName === 'domain') {
            (Object.keys(brushableAxes) as Array<'x' | 'y'>).forEach(
              dimName => {
                const axisSignal: [number, number] | string[] = signal[dimName];
                const currentSetting =
                  currConcreteConfig.signals.domain[dimName];

                let newDomain: Node;
                if (brushableAxes[dimName] === 'temporal') {
                  newDomain = constNode(
                    {type: 'list', objectType: {type: 'timestamp'}},
                    axisSignal as number[]
                  );
                } else {
                  newDomain = constNode(toWeaveType(axisSignal), axisSignal);
                }

                if (!_.isEqual(currentSetting, axisSignal)) {
                  currMutateDomain[dimName]({
                    val: newDomain,
                  });
                }

                // need to clear out the old selection, if there is one
                currUpdateConfig2((oldConfig: PlotConfig) => {
                  return produce(oldConfig, draft => {
                    draft.signals.selection[dimName] = undefined;
                  });
                });
              }
            );
          } else {
            currUpdateConfig2((oldConfig: PlotConfig) => {
              return produce(oldConfig, draft => {
                ['x' as const, 'y' as const].forEach(dimName => {
                  const axisSignal: [number, number] | string[] =
                    signal[dimName];
                  draft.signals.selection[dimName] = axisSignal;
                });
              });
            });
          }
        } else if (
          _.isEmpty(data) &&
          !(
            _.isEmpty(currConcreteConfig.signals.selection.x) &&
            _.isEmpty(currConcreteConfig.signals.selection.y)
          )
        ) {
          currUpdateConfig2((oldConfig: PlotConfig) => {
            return produce(oldConfig, draft => {
              ['x' as const, 'y' as const].forEach(dimName => {
                draft.signals.selection[dimName] = undefined;
              });
            });
          });
        }

        setTimeout(() => {
          currSetToolTipsEnabled(true);
        }, 600);
      });

      vegaView.addEventListener('dblclick', async () => {
        const currConfig = configRef.current;
        const currMutateDomain = mutateDomainRef.current;

        if (
          ['x' as const, 'y' as const].some(dimName => {
            const currentSettingNode = currConfig.signals.domain[dimName];
            return !(
              isConstNode(currentSettingNode) &&
              currentSettingNode.type === 'none'
            );
          })
        ) {
          ['x' as const, 'y' as const].forEach(dimName => {
            currMutateDomain[dimName]({
              val: constNode('none', null),
            });
          });
        }
      });
      vegaView.addEventListener('mousedown', async () => {
        const currSetToolTipsEnabled = setToolTipsEnabledRef.current;
        currSetToolTipsEnabled(false);
      });
    },
    [
      concreteConfig.series.length,
      concreteConfig.signals.selection,
      hasLine,
      brushableAxes,
    ]
  );

  const [toolTipPos, setTooltipPos] = useState<{
    x: number | undefined;
    y: number | undefined;
    value: any;
  }>({x: undefined, y: undefined, value: undefined});

  const currentlySelectedSeries = useMemo(() => {
    if (toolTipPos.value != null && toolTipPos.value._seriesIndex == null) {
      return getSeriesBySeriesIndex(0);
    }

    return getSeriesBySeriesIndex(toolTipPos.value?._seriesIndex);
  }, [getSeriesBySeriesIndex, toolTipPos.value]);

  const seriesIndex = useMemo(() => {
    if (currentlySelectedSeries) {
      return config.series.indexOf(currentlySelectedSeries);
    }
    return undefined;
  }, [config.series, currentlySelectedSeries]);

  const handleTooltip = useCallback(
    (toolTipHandler: any, event: any, item: any, value: any) => {
      if (!isMounted()) {
        return;
      }
      let {x, y}: {x?: number; y?: number} = {};

      if (value == null) {
        setTooltipPos({x: undefined, y: undefined, value: undefined});
      } else {
        try {
          calculatePosition(
            event,
            toolTipRef.current?.getBoundingClientRect()!,
            10,
            10
          );
        } catch (e) {
          setTooltipPos({x: undefined, y: undefined, value: undefined});
          return;
        }

        x = event.x + 10;
        y = event.y + 10;

        setTooltipPos({x, y, value});
      }
    },
    [isMounted]
  );

  const isLineTooltip = useMemo(
    () => toolTipPos.value != null && !_.isPlainObject(toolTipPos.value),
    [toolTipPos]
  );

  // TODO: this only needs to be one node ... update after getting line tooltip working
  const tooltipNode = useMemo(() => {
    if (isLineTooltip) {
      return tooltipLineData[toolTipPos.value] ?? voidNode();
    }

    const tooltipSeriesIndex = toolTipPos.value?._seriesIndex;
    const valueResultIndex = toolTipPos.value?._rowIndex;
    const s = config.series[tooltipSeriesIndex];

    if (tooltipSeriesIndex == null || valueResultIndex == null) {
      return voidNode();
    }

    const row = opIndex({
      arr: opIndex({
        arr: flatResultNode,
        index: constNumber(tooltipSeriesIndex),
      }),
      index: constNumber(valueResultIndex),
    });
    const toolTipFn =
      vegaReadyTables[tooltipSeriesIndex].columnSelectFunctions[s.dims.tooltip];
    if (toolTipFn.nodeType === 'void' || toolTipFn.type === 'invalid') {
      return row;
    }
    return opPick({
      obj: row,
      key: constString(
        escapeDots(
          TableState.getTableColumnName(
            s.table.columnNames,
            s.table.columnSelectFunctions,
            s.dims.tooltip,
            weave.client.opStore
          )
        )
      ),
    });
  }, [
    config.series,
    toolTipPos.value,
    flatResultNode,
    vegaReadyTables,
    weave.client.opStore,
    tooltipLineData,
    isLineTooltip,
  ]);

  const handler = useMemo(
    () =>
      getPanelStacksForType(tooltipNode.type, undefined, {
        excludeTable: true,
        excludePlot: true,
        excludeBarChart: true,
      }).handler,
    [tooltipNode]
  );

  const [isMouseOver, setIsMouseOver] = useState<boolean>(false);
  const panelPlotDivRef = useRef<HTMLDivElement>(document.createElement('div'));

  useEffect(() => {
    const onMouseMove = (e: any) => {
      if (
        panelPlotDivRef.current &&
        e.target &&
        panelPlotDivRef.current.contains(e.target)
      ) {
        setIsMouseOver(true);
      } else {
        setIsMouseOver(false);
      }
    };

    document.addEventListener('mousemove', onMouseMove);

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
    };
  }, []);

  const updateTooltipConfig = useMemo(() => {
    const noop = (newPanelConfig: any) => {};

    if (isLineTooltip) {
      return noop;
    }

    const tooltipSeriesIndex = toolTipPos.value?._seriesIndex;
    const valueResultIndex = toolTipPos.value?._rowIndex;

    if (tooltipSeriesIndex == null || valueResultIndex == null) {
      return noop;
    }

    return (newPanelConfig: any) => {
      const newSeries = produce(config.series, draft => {
        const draftSeries = draft[tooltipSeriesIndex];
        draftSeries.table = TableState.updateColumnPanelConfig(
          draftSeries.table,
          draftSeries.dims.tooltip,
          newPanelConfig
        );
      });
      return updateConfig({series: newSeries});
    };
  }, [config.series, updateConfig, isLineTooltip, toolTipPos]);

  const loaderComp = <Panel2Loader />;

  // Hardcode plot colors for now.
  if (vegaSpec.encoding.color == null) {
    vegaSpec.encoding.color = {};
  }
  if (vegaSpec.encoding.color.scale == null) {
    vegaSpec.encoding.color.scale = {};
  }
  vegaSpec.encoding.color.scale.range = globals.WB_RUN_COLORS;

  return (
    <div
      data-test="panel-plot-2-wrapper"
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        justifyContent: 'center',
        position: 'relative',
        alignItems: 'flex-start',
      }}
      ref={panelPlotDivRef}
      className={loading ? 'loading' : ''}>
      {loading ? (
        <div style={{width: '100%', height: '100%'}}>{loaderComp}</div>
      ) : (
        <>
          {isDash && isMouseOver && (
            <div
              style={{
                position: 'absolute',
                bottom: '10px',
                right: '10px',
                zIndex: 1,
              }}>
              <PanelPlotRadioButtons
                currentValue={brushMode}
                setMode={setBrushMode}
              />
            </div>
          )}
          <div
            data-test-weave-id="plot"
            // Use overflow hidden so we don't get scrollbars during resizing,
            // which cause measurement changes and flashes.
            style={{width: '100%', height: '100%', overflow: 'hidden'}}>
            {toolTipsEnabled && (
              <Portal>
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
                  {tooltipNode.nodeType !== 'void' && handler && (
                    <PanelComp2
                      input={tooltipNode}
                      inputType={tooltipNode.type}
                      loading={false}
                      panelSpec={handler}
                      configMode={false}
                      context={props.context}
                      config={
                        config.series[seriesIndex ?? 0].table.columns[
                          config.series[seriesIndex ?? 0].dims.tooltip
                        ].panelConfig
                      }
                      updateConfig={updateTooltipConfig}
                      updateContext={props.updateContext}
                    />
                  )}
                </div>
              </Portal>
            )}
            <CustomPanelRenderer
              spec={vegaSpec}
              loading={false}
              slow={false}
              data={dataToPassToCustomPanelRenderer}
              userSettings={{
                // TODO: I'm putting ! in here cause our fieldSettings
                // doesn't allow undefined. Fix that to allow it.
                fieldSettings: {title: config.title!},
                stringSettings: {
                  title: '',
                },
              }}
              handleTooltip={handleTooltip}
              onNewView={onNewVegaView}
              legendCutoffWidth={isDash ? 350 : undefined}
            />
          </div>
        </>
      )}
    </div>
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

const Portal: React.FC<{}> = props => {
  const ref = useRef(document.createElement('div'));
  useEffect(() => {
    const el = ref.current;
    document.body.appendChild(el);
    return () => {
      document.body.removeChild(el);
    };
  }, []);
  return ReactDOM.createPortal(props.children, ref.current);
};

/* eslint-disable no-template-curly-in-string */

export const Spec: Panel2.PanelSpec = {
  id: 'plot',
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

const PLOT_TEMPLATE: VisualizationSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  data: {
    name: 'wandb',
  },
  padding: 1,
  title: '${field:title}',
  mark: {
    // tooltip: true,
  } as any,
  params: [],
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

export default Spec;

const ConfigDimMenuButton = styled(IconButton).attrs({small: true})`
  margin-left: 4px;
  padding: 3px;
`;

const IconBlank = styled.svg`
  width: 18px;
  height: 18px;
`;
