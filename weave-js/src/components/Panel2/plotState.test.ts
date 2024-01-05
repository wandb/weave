import {produce} from 'immer';
import * as _ from 'lodash';

import {
  constNode,
  constNumber,
  constString,
  Node,
  NodeOrVoidNode,
  opNumberAdd,
  opPick,
  varNode,
  voidNode,
} from '../../core';
import {
  addSeriesFromSeries,
  condensePlotConfig,
  makeDimensionShared,
  removeRedundantSeries,
} from './PanelPlot/plotState';
import * as PlotState from './PanelPlot/plotState';
import {
  migrate,
  PLOT_DIMS_UI,
  PlotConfig,
  SeriesConfig,
} from './PanelPlot/versions';
import * as v1 from './PanelPlot/versions/v1';
import * as TableState from './PanelTable/tableState';
import {
  getTableRowsNode,
  testWeave,
} from './PanelTable/tableState.test.fixtures';

interface PlotConfigFixtureParams {
  transformX?: (node: Node) => Node;
  transformY?: (node: Node) => Node;
  transformLabel?: (node: Node) => Node;
  defaultSeries?: SeriesConfig;
  empty?: boolean;
}

const weave = testWeave();

const basicPlotConfigV1 = (
  sourceNode: Node,
  params: PlotConfigFixtureParams = {}
): v1.PlotConfig => {
  const rowType = sourceNode.type;

  let xNode: NodeOrVoidNode = opPick({
    obj: varNode(rowType, 'row'),
    key: constString('a'),
  });

  let labelNode: NodeOrVoidNode = opPick({
    obj: varNode(rowType, 'row'),
    key: constString('x'),
  });

  let yNode: NodeOrVoidNode = opPick({
    obj: varNode(rowType, 'row'),
    key: constString('b'),
  });

  if (params.transformX) {
    xNode = params.transformX(xNode);
  }

  if (params.transformY) {
    yNode = params.transformY(yNode);
  }

  if (params.transformLabel) {
    labelNode = params.transformLabel(labelNode);
  }

  if (params.empty) {
    xNode = voidNode();
    yNode = voidNode();
    labelNode = voidNode();
  }

  let table = TableState.emptyTable();
  ({table} = TableState.addColumnToTable(table, xNode));
  const timeId = table.order[table.order.length - 1];
  ({table} = TableState.addColumnToTable(table, labelNode));
  const labelColId = table.order[table.order.length - 1];
  ({table} = TableState.addColumnToTable(table, yNode));
  const valueId = table.order[table.order.length - 1];

  table = TableState.appendEmptyColumn(table);
  const detailColId = table.order[table.order.length - 1];
  table = TableState.appendEmptyColumn(table);
  const tooltipColId = table.order[table.order.length - 1];
  table = TableState.appendEmptyColumn(table);
  const pointSizeID = table.order[table.order.length - 1];
  table = TableState.appendEmptyColumn(table);
  const pointShapeID = table.order[table.order.length - 1];

  const dim1 = {
    x: timeId,
    y: valueId,
    color: labelColId,
    label: labelColId,
    detail: detailColId,
    tooltip: tooltipColId,
    pointSize: pointSizeID,
    pointShape: pointShapeID,
  };

  return {
    configVersion: 1,
    table,
    dims: dim1,
    axisSettings: {x: {}, y: {}},
    legendSettings: {color: {}},
  };
};

const basicPlotConfigLatest = (
  sourceNode: Node,
  params: PlotConfigFixtureParams = {}
): PlotConfig => migrate(basicPlotConfigV1(sourceNode, params));

describe('test multiple series', () => {
  it('test migration of panelplot v1 config', async () => {
    const sourceNode = await getTableRowsNode();
    const basicConfig = basicPlotConfigV1(sourceNode);

    const migrated = migrate(basicConfig);
    const y2colName =
      migrated.series[0].table.order[migrated.series[0].table.order.length - 1];
    const expectedResult: PlotConfig = {
      configVersion: 15,
      axisSettings: {
        ...basicConfig.axisSettings,
        color: {},
      },
      vegaOverlay: basicConfig.vegaOverlay,
      legendSettings: {
        ...basicConfig.legendSettings,
        x: {noLegend: false},
        y: {noLegend: false},
        pointShape: {noLegend: false},
        pointSize: {noLegend: false},
        lineStyle: {noLegend: false},
      },
      configOptionsExpanded: PLOT_DIMS_UI.reduce((acc, val) => {
        acc[val] = false;
        return acc;
      }, {} as {[K in (typeof PLOT_DIMS_UI)[number]]: boolean}),
      series: [
        {
          dims: {
            ...basicConfig.dims,
            y2: y2colName,
          },
          table: {
            ...basicConfig.table,
            columnSelectFunctions: {
              ...basicConfig.table.columnSelectFunctions,
              [y2colName]: voidNode(),
            },
            columnNames: {
              ...basicConfig.table.columnNames,
              [y2colName]: '',
            },
            columns: {
              ...basicConfig.table.columns,
              [y2colName]: {
                panelConfig: undefined,
                panelId: '',
              },
            },
            order: [...basicConfig.table.order, y2colName],
          },
          constants: {
            mark: basicConfig.mark || null,
            lineStyle: 'solid',
            pointShape: 'circle',
            label: 'series',
          },
          uiState: {
            pointShape: 'expression',
            label: 'expression',
          },
        },
      ],
      signals: {
        domain: {
          x: constNode('none', null),
          y: constNode('none', null),
        },
        selection: {},
      },
    };

    expect(migrated).toEqual(expectedResult);
  });

  it('test condense / removeRedundant on two identical series produces original series', async () => {
    const sourceNode = await getTableRowsNode();
    const [basicConfig, basicConfig2] = _.times(2, () =>
      migrate(basicPlotConfigV1(sourceNode))
    );

    const mergedConfig: PlotConfig = {
      ...basicConfig,
      series: [...basicConfig.series, ...basicConfig2.series],
    };

    expect(removeRedundantSeries(mergedConfig, weave)).toEqual(basicConfig);
    expect(condensePlotConfig(mergedConfig, weave)).toEqual(basicConfig);
  });

  it('test condense / removeRedundant properly respects voidNodes', async () => {
    const sourceNode = await getTableRowsNode();
    const basicConfig = basicPlotConfigLatest(sourceNode);
    const basicConfig2 = produce(basicConfig, draft => {
      const table = draft.series[0].table;
      // set y selectFunc to voidNode -- this should be considered degenerate with the series from the first
      // config and be removed as a result
      draft.series[0].table = TableState.updateColumnSelect(
        table,
        draft.series[0].dims.y,
        voidNode()
      );
    });

    const mergedConfig: PlotConfig = {
      ...basicConfig,
      series: [...basicConfig.series, ...basicConfig2.series],
    };

    expect(removeRedundantSeries(mergedConfig, weave)).toEqual(basicConfig);
    expect(condensePlotConfig(mergedConfig, weave)).toEqual(basicConfig);
  });

  it('test collapseDim on nondegenerate series', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'y',
      weave
    );

    // y should be expanded, and all other dims should be shared/collapsed
    PLOT_DIMS_UI.forEach(dim => {
      expect(config.configOptionsExpanded[dim]).toEqual(dim === 'y');
    });

    // now update the series so that the X's differ
    config = produce(config, draft => {
      const series = draft.series[0];
      const oldSelectFunc = series.table.columnSelectFunctions[
        series.dims.x
      ] as any;
      const addend = constNumber(1) as any;
      const newSelectFunc = opNumberAdd({lhs: oldSelectFunc, rhs: addend});
      series.table = TableState.updateColumnSelect(
        series.table,
        series.dims.x,
        newSelectFunc
      );
      draft.configOptionsExpanded.x = true;
    });

    // removing degenerate series should do nothing
    expect(removeRedundantSeries(config, weave)).toEqual(config);

    // condensing should just set y to be shared
    expect(condensePlotConfig(config, weave)).toEqual(
      produce(config, draft => {
        draft.configOptionsExpanded.y = false;
        const series = draft.series[1];
        series.table = TableState.updateColumnSelect(
          series.table,
          series.dims.y,
          draft.series[0].table.columnSelectFunctions[draft.series[0].dims.y]
        );
      })
    );
  });

  it('test collapseDim on degenerate dimension and double void dimension', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'y',
      weave
    );

    // expand tooltip dimension
    config = produce(config, draft => {
      draft.configOptionsExpanded.tooltip = true;
    });

    // y should be expanded, and all other dims should be shared/collapsed
    PLOT_DIMS_UI.forEach(dim => {
      expect(config.configOptionsExpanded[dim]).toEqual(
        ['y', 'tooltip'].includes(dim)
      );
    });

    // now set the tooltip selectfunctions to all be voidnodes
    config = produce(config, draft => {
      draft.series.forEach(s => {
        s.table = TableState.updateColumnSelect(
          s.table,
          s.dims.tooltip,
          voidNode()
        );
      });
    });

    // now update the series so that the X's differ
    config = produce(config, draft => {
      const series = draft.series[0];
      const oldSelectFunc = series.table.columnSelectFunctions[
        series.dims.x
      ] as any;
      const addend = constNumber(1) as any;
      const newSelectFunc = opNumberAdd({lhs: oldSelectFunc, rhs: addend});
      series.table = TableState.updateColumnSelect(
        series.table,
        series.dims.x,
        newSelectFunc
      );
      draft.configOptionsExpanded.x = true;
    });

    // removing degenerate series should do nothing
    expect(removeRedundantSeries(config, weave)).toEqual(config);

    // condensing should set y to be shared and set tooltip to be shared
    expect(condensePlotConfig(config, weave)).toEqual(
      produce(config, draft => {
        draft.configOptionsExpanded.y = false;
        draft.configOptionsExpanded.tooltip = false;
        const series = draft.series[1];
        series.table = TableState.updateColumnSelect(
          series.table,
          series.dims.y,
          draft.series[0].table.columnSelectFunctions[draft.series[0].dims.y]
        );
      })
    );
  });

  it('test configIsValid on invalid config', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'y',
      weave
    );

    // now update the series so that the Y's are of different types original
    // is number and now this is string
    config = produce(config, draft => {
      const series = draft.series[0];
      const newSelectFunc = constString('test');
      series.table = TableState.updateColumnSelect(
        series.table,
        series.dims.x,
        newSelectFunc
      );
      draft.configOptionsExpanded.x = true;
    });

    expect(PlotState.isValidConfig(config).valid).toBe(false);
  });

  it('test remove redundant series AND collapse redundant dimensions', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);

    // add one redundant series
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'y',
      weave
    );

    // add one series that will not be redundant, we will update x
    config = addSeriesFromSeries(config, config.series[0], 'x', weave);

    // at this point x & y should be expanded, and all other dims should be shared/collapsed
    PLOT_DIMS_UI.forEach(dim => {
      expect(config.configOptionsExpanded[dim]).toEqual(
        ['x', 'y'].includes(dim)
      );
    });

    // now update the third series so that the X's differ
    config = produce(config, draft => {
      const series = draft.series[2];
      const oldSelectFunc = series.table.columnSelectFunctions[
        series.dims.x
      ] as any;
      const addend = constNumber(1) as any;
      const newSelectFunc = opNumberAdd({lhs: oldSelectFunc, rhs: addend});
      series.table = TableState.updateColumnSelect(
        series.table,
        series.dims.x,
        newSelectFunc
      );
    });

    // condensing should just set y to be shared
    expect(condensePlotConfig(config, weave)).toEqual(
      produce(config, draft => {
        draft.configOptionsExpanded.y = false;
        draft.series = [draft.series[0], draft.series[2]];
      })
    );
  });

  it('test collapse non redundant mark dimension', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);

    // add one redundant series
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'mark',
      weave
    );

    // update the series so that marks are very similar but still different enough to not be redundant
    config = produce(config, draft => {
      draft.series[0].constants.mark = 'point';
      draft.series[1].constants.mark = 'point';

      draft.series[0].table = TableState.updateColumnSelect(
        draft.series[0].table,
        draft.series[0].dims.pointShape,
        constString('circle')
      );

      draft.series[1].table = TableState.updateColumnSelect(
        draft.series[1].table,
        draft.series[1].dims.pointShape,
        constString('triangle-up')
      );

      draft.series[0].table = TableState.updateColumnSelect(
        draft.series[0].table,
        draft.series[0].dims.pointSize,
        constNumber(100)
      );

      draft.series[1].table = TableState.updateColumnSelect(
        draft.series[1].table,
        draft.series[1].dims.pointSize,
        constNumber(100)
      );
    });

    // condensing should have no effect
    expect(condensePlotConfig(config, weave)).toEqual(
      produce(config, draft => {
        draft.configOptionsExpanded.mark = true;
        draft.series = [draft.series[0], draft.series[1]];
      })
    );
  });

  it('test makeDimensionShared', async () => {
    const sourceNode = await getTableRowsNode();
    const originalConfig = basicPlotConfigLatest(sourceNode);

    // add one redundant series
    let config = addSeriesFromSeries(
      originalConfig,
      originalConfig.series[0],
      'mark',
      weave
    );

    // update the series so that marks are very similar but still different enough to not be redundant
    config = produce(config, draft => {
      draft.series[0].constants.mark = 'point';
      draft.series[1].constants.mark = 'point';

      draft.series[0].table = TableState.updateColumnSelect(
        draft.series[0].table,
        draft.series[0].dims.pointShape,
        constString('circle')
      );

      draft.series[1].table = TableState.updateColumnSelect(
        draft.series[1].table,
        draft.series[1].dims.pointShape,
        constString('triangle-up')
      );

      draft.series[0].table = TableState.updateColumnSelect(
        draft.series[0].table,
        draft.series[0].dims.pointSize,
        constNumber(100)
      );

      draft.series[1].table = TableState.updateColumnSelect(
        draft.series[1].table,
        draft.series[1].dims.pointSize,
        constNumber(100)
      );
    });

    expect(
      makeDimensionShared(config, config.series[0], 'mark', weave)
    ).toEqual(
      produce(config, draft => {
        draft.configOptionsExpanded.mark = false;
        draft.series = [draft.series[0], draft.series[0]];
      })
    );
  });
});
