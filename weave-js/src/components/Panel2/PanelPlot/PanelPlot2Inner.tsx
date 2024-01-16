import {ActivityDashboardContext} from '@wandb/weave/common/components/ActivityDashboardContext';
import {RepoInsightsDashboardContext} from '@wandb/weave/common/components/RepoInsightsDashboardContext';
import CustomPanelRenderer, {
  MultiTableDataType,
} from '@wandb/weave/common/components/Vega3/CustomPanelRenderer';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {useIsMounted} from '@wandb/weave/common/util/hooks';
import {
  ConstNode,
  constNode,
  constNodeUnsafe,
  constNumber,
  constString,
  escapeDots,
  filterNodes,
  isAssignableTo,
  isConstNode,
  isTaggedValue,
  isTypedDict,
  isVoidNode,
  listObjectType,
  maybe,
  Node,
  numberBin,
  oneOrMany,
  opArray,
  opIndex,
  opLimit,
  opPick,
  // opRandomlyDownsample,
  OpStore,
  opUnnest,
  taggedValueValueType,
  timestampBin,
  Type,
  typedDict,
  TypedDictType,
  union,
  voidNode,
  withFileTag,
  withoutTags,
} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import React, {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {View as VegaView, VisualizationSpec} from 'react-vega';
import {calculatePosition} from 'vega-tooltip';

import {
  useWeaveContext,
  useWeaveRedesignedPlotConfigEnabled,
} from '../../../context';
import * as LLReact from '../../../react';
import {getPanelStackDims, getPanelStacksForType} from '../availablePanels';
import {Panel2Loader, PanelComp2} from '../PanelComp';
import {usePanelContext} from '../PanelContext';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as TableState from '../PanelTable/tableState';
import {toWeaveType} from '../toWeaveType';
import {ensureValidSignals, useConcreteConfig, useConfig} from './config';
import {filterTableNodeToSelection} from './filter';
import * as PlotState from './plotState';
import {Portal} from './Portal';
import {PanelPlotRadioButtons} from './RadioButtons';
import {BrushMode, PanelPlotProps} from './types';
import {defaultPlot, getAxisTimeUnit} from './util';
import {
  getMark,
  stringHashCode,
  stringIsColorLike,
  useVegaReadyTables,
} from './util';
import {
  ConcretePlotConfig,
  LINE_SHAPES,
  MarkOption,
  PlotConfig,
  POINT_SHAPES,
  Scale,
  SeriesConfig,
} from './versions';

const recordEvent = makeEventRecorder('Plot');

// const PANELPLOT_MAX_DATAPOINTS = 2000;

/* eslint-disable no-template-curly-in-string */
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

function tooltipNoCache(
  row: any,
  s: SeriesConfig,
  flatResultNode: Node,
  opStore: OpStore
) {
  return opPick({
    obj: opIndex({
      arr: opIndex({
        arr: flatResultNode,
        index: constNumber(row._seriesIndex),
      }),
      index: constNumber(row._rowIndex),
    }),
    key: constString(
      escapeDots(
        TableState.getTableColumnName(
          s.table.columnNames,
          s.table.columnSelectFunctions,
          s.dims.tooltip,
          opStore
        )
      )
    ),
  });
}

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

const defaultFontStyleDict = {
  titleFont: 'Source Sans Pro',
  titleFontWeight: 'normal',
  titleColor: globals.gray900,
  labelFont: 'Source Sans Pro',
  labelFontWeight: 'normal',
  labelColor: globals.gray900,
  labelSeparation: 5,
};

type ExprDimNameType = (typeof PlotState.EXPRESSION_DIM_NAMES)[number];

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

/*
async function mergeRealizedTableData(
  oldTable: _.Dictionary<any>[],
  newTable: _.Dictionary<any>[]
): Promise<_.Dictionary<any>[]> {
  const flatArray = _.flatten([oldTable, newTable]);
  const uniqueArray = _.uniqBy(flatArray, '_rowIndex');
  return _.sortBy(uniqueArray, '_rowIndex');
}

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

export const PanelPlot2Inner: React.FC<PanelPlotProps> = props => {
  const isDash = useWeaveRedesignedPlotConfigEnabled();
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

  useEffect(() => {
    recordEvent('VIEW');
  }, []);

  // TODO(np): Hack to detect when we are on an activity dashboard
  const isDashboard = useIsDashboard();

  const {frame, stack} = usePanelContext();
  const {config, isRefining} = useConfig(input, props.config);

  const panelId = LLReact.useId();

  const {config: unvalidatedConcreteConfig, loading: concreteConfigLoading} =
    useConcreteConfig(config, stack, panelId.toString());

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

  const {opStore} = weave.client;

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
              opStore
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
            limit: constNumber(500),
          });
        }
      }

      // if (isDash) {
      //   node = opRandomlyDownsample({
      //     arr: node,
      //     n: constNumber(PANELPLOT_MAX_DATAPOINTS),
      //   });
      // }

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
    opStore,
  ]);

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

  const tooltipData: {[seriesIndexRowIndexString: string]: Node} =
    useMemo(() => {
      return concattedNonLineTable.reduce(
        (acc: {[seriesIndexRowIndexString: string]: Node}, row) => {
          const key = `[${row._seriesIndex},${row._rowIndex}]`;

          // check if we have a null select function, and thus are using the default tooltip
          const s = concreteConfig.series[row._seriesIndex];
          const colId = s.dims.tooltip;
          const table = vegaReadyTables[row._seriesIndex];
          const selectFn = table.columnSelectFunctions[colId];

          const unnestedRowType = listObjectType(
            listOfTableNodes[row._seriesIndex].type
          ) as TypedDictType;

          if (isVoidNode(selectFn)) {
            // use default tooltip

            const propertyTypes = PlotState.EXPRESSION_DIM_NAMES.reduce(
              (acc2: {[vegaColName: string]: Type}, dim: ExprDimNameType) => {
                const colid = s.dims[dim];

                if (
                  !isVoidNode(table.columnSelectFunctions[colid]) &&
                  !isConstNode(table.columnSelectFunctions[colid])
                ) {
                  const colNameNotVegaEscaped = TableState.getTableColumnName(
                    vegaReadyTables[row._seriesIndex].columnNames,
                    vegaReadyTables[row._seriesIndex].columnSelectFunctions,
                    s.dims[dim],
                    opStore
                  );

                  const colNameVegaEscaped = vegaCols[row._seriesIndex][dim];
                  const colType =
                    unnestedRowType.propertyTypes[colNameNotVegaEscaped];

                  if (colType != null) {
                    acc2[colNameVegaEscaped] = isTaggedValue(colType)
                      ? taggedValueValueType(colType)
                      : colType;
                  }
                }

                return acc2;
              },
              {}
            );
            const type = typedDict(propertyTypes);
            acc[key] = constNodeUnsafe(type, row);
          } else {
            // use custom tooltip
            const type = table.columnSelectFunctions[s.dims.tooltip].type;
            if (isAssignableTo(type, withFileTag('any', {type: 'file'}))) {
              // Temporary workaround for image tooltips in weave0.
              // Remove this when weave0 is retired and use the else branch instead.

              // Explanation: In weave0, constNodes constructed from table rows lack the 'file' tag needed for
              // opAssetFile in cached tooltips. To address this, we skip constNode construction for images
              // and execute the entire graph for image tooltips. This is specific to weave0 as weave1 includes
              // the 'artifact' attribute in the materialized panelplot data table, eliminating the need for this hack.

              // TODO: Remove this workaround when weave0 is phased out.

              // NOTE: The graph below represents the original (non-caching) tooltip behavior.

              acc[key] = tooltipNoCache(row, s, flatResultNode, opStore);
            } else {
              const colNameNotVegaEscaped = TableState.getTableColumnName(
                vegaReadyTables[row._seriesIndex].columnNames,
                vegaReadyTables[row._seriesIndex].columnSelectFunctions,
                s.dims.tooltip,
                opStore
              );

              const colNameVegaEscaped = vegaCols[row._seriesIndex].tooltip;

              const unnestedType =
                unnestedRowType.propertyTypes[colNameNotVegaEscaped];

              if (unnestedType == null) {
                acc[key] = tooltipNoCache(row, s, flatResultNode, opStore);
              } else {
                acc[key] = constNodeUnsafe(
                  isTaggedValue(unnestedType)
                    ? taggedValueValueType(unnestedType)
                    : unnestedType,
                  row[colNameVegaEscaped]
                );
              }
            }
          }

          return acc;
        },
        {}
      );
    }, [
      concattedNonLineTable,
      concreteConfig.series,
      vegaReadyTables,
      listOfTableNodes,
      vegaCols,
      flatResultNode,
      opStore,
    ]);

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

  const signalDomainX = concreteConfig.signals.domain.x;
  const xScaleAndDomain = useMemo(
    () => (signalDomainX ? {scale: {domain: signalDomainX}} : {}),
    [signalDomainX]
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
        fixKeyForVegaTable(key, vegaReadyTable, opStore);

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
          // If we haven't zoomed in, and we have quantitative data, use the extent of the x values
          let xScaleAndDomainFromData = {};
          if (xAxisType === 'quantitative' && _.isEmpty(xScaleAndDomain)) {
            xScaleAndDomainFromData = {
              scale: {
                domain: {
                  data: newSpec.data.name,
                  field: fixedXKey,
                },
              },
            };
          }
          newSpec.encoding.x = {
            field: fixedXKey,
            type: xAxisType,
            ...xScaleAndDomain,
            ...xScaleAndDomainFromData,
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
          scale:
            colorAxisType === 'quantitative' || colorAxisType === 'temporal'
              ? {scheme: 'plasma'}
              : {range: globals.WB_RUN_COLORS},
        };
        if (
          vegaReadyTable.columnSelectFunctions[dims.label].type !== 'invalid'
        ) {
          newSpec.encoding.color.field = vegaCols[i].label;
          if (colorFieldIsRange) {
            // map the color field to the range of the color scale
            const labelKey = vegaCols[i].label;
            const colorKey = vegaCols[i].color;

            const nonNullDims: ExprDimNameType[] =
              PlotState.EXPRESSION_DIM_NAMES.filter(
                dim =>
                  !isVoidNode(
                    series.table.columnSelectFunctions[series.dims[dim]]
                  )
              );

            const mapping = flatPlotTable.reduce((acc, row) => {
              if (nonNullDims.every(dim => row[vegaCols[i][dim]] != null)) {
                acc[row[labelKey]] = row[colorKey];
              }
              return acc;
            }, {} as {[key: string]: string});

            const scale = {
              domain: Object.keys(mapping),
              range: Object.values(mapping),
            };

            newSpec.encoding.color.scale = scale;
          }
        }
      } else if (series.uiState.label === 'dropdown') {
        newSpec.encoding.color = {
          datum: PlotState.defaultSeriesName(series, weave),
          title: 'series',
          legend: concreteConfig.legendSettings.color.noLegend
            ? false
            : {...defaultFontStyleDict},
          scale: {range: globals.WB_RUN_COLORS},
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
            opStore
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
    opStore,
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
    vegaCols,
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
    if (toolTipPos.value == null) {
      return voidNode();
    }

    if (isLineTooltip) {
      return tooltipLineData[toolTipPos.value] ?? voidNode();
    }

    const key = `[${toolTipPos.value?._seriesIndex},${toolTipPos.value?._rowIndex}]`;
    return tooltipData[key] ?? voidNode();
  }, [toolTipPos.value, tooltipLineData, isLineTooltip, tooltipData]);

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
      const newSeries = produce(config.series, (draft: any) => {
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
                    borderRadius: 4,
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
