import copy

import pytest

import weave
from .. import graph
from weave.panels.panel_plot import Plot, Series, PlotConstants
from .test_run_segment import create_experiment


def test_run_segment_plot_config():
    last_segment = create_experiment(1000, 3, 0.8)
    config = Plot(last_segment.experiment())
    assert len(config.series) == 1
    assert all(
        isinstance(v, (graph.VoidNode, graph.ConstNode))
        for v in config.series[0].table._column_select_functions.values()
    )


def test_multi_series_plot_config_with_grouping():
    last_segment = create_experiment(1000, 3, 0.8)
    plot = Plot(last_segment.experiment())
    plot.set_x(
        lambda row: weave.ops.number_bin(
            row["step"], weave.ops.numbers_bins_equal([1, 2000], 2)
        )
    )
    plot.set_y(lambda row: weave.ops.numbers_avg(row["metric0"]))

    plot.groupby_x()
    plot.set_mark_constant("line")

    series2 = plot.series[0].clone()
    plot.add_series(series2)

    series2.set_y(lambda row: weave.ops.numbers_min(row["metric0"]))
    series2.set_y2(lambda row: weave.ops.numbers_max(row["metric0"]))
    series2.set_mark_constant("area")

    plot.groupby_x()

    assert len(plot.series) == 2
    assert all(
        isinstance(v, (graph.VoidNode, graph.ConstNode, graph.OutputNode))
        for v in list(plot.series[0].table._column_select_functions.values())
        + list(plot.series[1].table._column_select_functions.values())
    )


def test_multi_series_grouping():
    last_segment = create_experiment(1000, 3, 0.8)
    plot = Plot(last_segment.experiment())
    plot.set_x(
        lambda row: weave.ops.number_bin(
            row["step"], weave.ops.numbers_bins_equal([1, 2000], 2)
        )
    )

    plot.set_y(lambda row: weave.ops.numbers_avg(row["metric0"]))
    plot.set_mark_constant("line")

    series2 = plot.series[0].clone()
    plot.add_series(series2)

    series2.set_y(lambda row: weave.ops.numbers_min(row["metric0"]))
    series2.set_y2(lambda row: weave.ops.numbers_max(row["metric0"]))
    series2.set_mark_constant("area")

    plot2 = copy.deepcopy(plot)

    # compare plot-level grouping to series by series grouping
    plot.groupby_x()
    for series in plot2.series:
        series.groupby_x()
    assert plot == plot2


def test_overspecification_of_plot_config_raises_exception():
    last_segment = create_experiment(1000, 3, 0.8)
    ok_plot = Plot(last_segment.experiment())
    series = ok_plot.series[0]

    # cant specify both
    with pytest.raises(ValueError):
        Plot(last_segment.experiment(), series=series)

    # need at least 1
    with pytest.raises(ValueError):
        Plot()


def test_multi_series_setting():
    last_segment = create_experiment(1000, 3, 0.8)
    plot = Plot(last_segment.experiment())
    plot.set_x(
        lambda row: weave.ops.number_bin(
            row["step"], weave.ops.numbers_bins_equal([1, 2000], 2)
        )
    )

    plot.set_y(lambda row: weave.ops.numbers_avg(row["metric0"]))
    plot.set_mark_constant("line")

    series2 = plot.series[0].clone()
    plot.add_series(series2)

    series2.set_y(lambda row: weave.ops.numbers_min(row["metric0"]))
    series2.set_y2(lambda row: weave.ops.numbers_max(row["metric0"]))
    series2.set_mark_constant("area")

    plot2 = copy.deepcopy(plot)

    # compare plot-level setting to series by series setting
    plot.set_x(lambda row: row["step"])
    for series in plot2.series:
        series.set_x(lambda row: row["step"])
    assert plot == plot2


def test_constructor():
    last_segment = create_experiment(1000, 3, 0.8)
    series = Series(
        input_node=last_segment.experiment(),
        select_functions={
            "x": lambda row: row["step"],
            "y": lambda row: row["metric0"],
        },
    )
    plot = Plot(series=series)
    plot2 = Plot(series=[series])
    assert plot == plot2
    assert series.constants == PlotConstants(
        mark=None, label="series", pointShape="circle", lineStyle="solid"
    )


def test_actual_config_value(fixed_random_seed):
    last_segment = create_experiment(1000, 3, 0.8)
    plot = Plot(last_segment.experiment())
    plot.set_x(
        lambda row: weave.ops.number_bin(
            row["step"], weave.ops.numbers_bins_equal([1, 2000], 2)
        )
    )
    plot.set_y(lambda row: weave.ops.numbers_avg(row["metric0"]))
    plot.set_mark_constant("line")

    series2 = plot.series[0].clone()
    plot.add_series(series2)

    series2.set_y(lambda row: weave.ops.numbers_min(row["metric0"]))
    series2.set_y2(lambda row: weave.ops.numbers_max(row["metric0"]))
    series2.set_mark_constant("area")

    assert plot.config == {
        "series": [
            {
                "table": {
                    "autoColumns": False,
                    "columns": {
                        "LEWVQ43VQJ7UVS": {"panelId": "", "panelConfig": None},
                        "KRDEEO6PKRDH36": {"panelId": "", "panelConfig": None},
                        "K5CG252HAV2FLZ": {"panelId": "", "panelConfig": None},
                        "9ORNJG56OGUUS2": {"panelId": "", "panelConfig": None},
                        "BJB2AY8D1P5JPO": {"panelId": "", "panelConfig": None},
                        "EPBPZ7OF3CU3BT": {"panelId": "", "panelConfig": None},
                        "PJ3TAMZ9RE8CSQ": {"panelId": "", "panelConfig": None},
                        "NQV4ZUZP68VEFU": {"panelId": "", "panelConfig": None},
                    },
                    "preFilterFunction": {"nodeType": "void", "type": "invalid"},
                    "columnNames": {
                        "LEWVQ43VQJ7UVS": "",
                        "KRDEEO6PKRDH36": "",
                        "K5CG252HAV2FLZ": "",
                        "9ORNJG56OGUUS2": "",
                        "BJB2AY8D1P5JPO": "",
                        "EPBPZ7OF3CU3BT": "",
                        "PJ3TAMZ9RE8CSQ": "",
                        "NQV4ZUZP68VEFU": "",
                    },
                    "columnSelectFunctions": {
                        "LEWVQ43VQJ7UVS": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"start": "float", "stop": "float"},
                            },
                            "fromOp": {
                                "name": "number-pybin",
                                "inputs": {
                                    "in_": {
                                        "nodeType": "output",
                                        "type": "int",
                                        "fromOp": {
                                            "name": "typedDict-pick",
                                            "inputs": {
                                                "self": {
                                                    "nodeType": "var",
                                                    "type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "step": "int",
                                                            "string_col": "string",
                                                            "metric0": "float",
                                                            "metric1": "float",
                                                            "metric2": "float",
                                                            "metric3": "float",
                                                            "metric4": "float",
                                                            "metric5": "float",
                                                            "metric6": "float",
                                                            "metric7": "float",
                                                            "metric8": "float",
                                                            "metric9": "float",
                                                            "metric10": "float",
                                                            "metric11": "float",
                                                            "metric12": "float",
                                                            "metric13": "float",
                                                            "metric14": "float",
                                                            "metric15": "float",
                                                            "metric16": "float",
                                                            "metric17": "float",
                                                            "metric18": "float",
                                                            "metric19": "float",
                                                            "metric20": "float",
                                                            "metric21": "float",
                                                            "metric22": "float",
                                                            "metric23": "float",
                                                            "metric24": "float",
                                                            "metric25": "float",
                                                            "metric26": "float",
                                                            "metric27": "float",
                                                            "metric28": "float",
                                                            "metric29": "float",
                                                            "metric30": "float",
                                                            "metric31": "float",
                                                            "metric32": "float",
                                                            "metric33": "float",
                                                            "metric34": "float",
                                                            "metric35": "float",
                                                            "metric36": "float",
                                                            "metric37": "float",
                                                            "metric38": "float",
                                                            "metric39": "float",
                                                            "metric40": "float",
                                                            "metric41": "float",
                                                            "metric42": "float",
                                                            "metric43": "float",
                                                            "metric44": "float",
                                                            "metric45": "float",
                                                            "metric46": "float",
                                                            "metric47": "float",
                                                            "metric48": "float",
                                                            "metric49": "float",
                                                            "metric50": "float",
                                                            "metric51": "float",
                                                            "metric52": "float",
                                                            "metric53": "float",
                                                            "metric54": "float",
                                                            "metric55": "float",
                                                            "metric56": "float",
                                                            "metric57": "float",
                                                            "metric58": "float",
                                                            "metric59": "float",
                                                            "metric60": "float",
                                                            "metric61": "float",
                                                            "metric62": "float",
                                                            "metric63": "float",
                                                            "metric64": "float",
                                                            "metric65": "float",
                                                            "metric66": "float",
                                                            "metric67": "float",
                                                            "metric68": "float",
                                                            "metric69": "float",
                                                            "metric70": "float",
                                                            "metric71": "float",
                                                            "metric72": "float",
                                                            "metric73": "float",
                                                            "metric74": "float",
                                                            "metric75": "float",
                                                            "metric76": "float",
                                                            "metric77": "float",
                                                            "metric78": "float",
                                                            "metric79": "float",
                                                            "metric80": "float",
                                                            "metric81": "float",
                                                            "metric82": "float",
                                                            "metric83": "float",
                                                            "metric84": "float",
                                                            "metric85": "float",
                                                            "metric86": "float",
                                                            "metric87": "float",
                                                            "metric88": "float",
                                                            "metric89": "float",
                                                            "metric90": "float",
                                                            "metric91": "float",
                                                            "metric92": "float",
                                                            "metric93": "float",
                                                            "metric94": "float",
                                                            "metric95": "float",
                                                            "metric96": "float",
                                                            "metric97": "float",
                                                            "metric98": "float",
                                                            "run_name": "string",
                                                        },
                                                    },
                                                    "varName": "row",
                                                },
                                                "key": {
                                                    "nodeType": "const",
                                                    "type": "string",
                                                    "val": "step",
                                                },
                                            },
                                        },
                                    },
                                    "bin_fn": {
                                        "nodeType": "output",
                                        "type": {
                                            "type": "function",
                                            "inputTypes": {"row": "number"},
                                            "outputType": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "start": "float",
                                                    "stop": "float",
                                                },
                                            },
                                        },
                                        "fromOp": {
                                            "name": "numbers-pybinsequal",
                                            "inputs": {
                                                "arr": {
                                                    "nodeType": "output",
                                                    "type": {
                                                        "type": "list",
                                                        "objectType": "int",
                                                    },
                                                    "fromOp": {
                                                        "name": "get",
                                                        "inputs": {
                                                            "uri": {
                                                                "nodeType": "const",
                                                                "type": "string",
                                                                "val": "local-artifact:///tmp/weave/pytest/weave/tests/test_plot.py::test_actual_config_value (setup)/list/dc9ffba8da33b6d87d72d4525afcd383",
                                                            }
                                                        },
                                                    },
                                                },
                                                "bins": {
                                                    "nodeType": "const",
                                                    "type": "int",
                                                    "val": 2,
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "KRDEEO6PKRDH36": {
                            "nodeType": "output",
                            "type": "number",
                            "fromOp": {
                                "name": "numbers-avg",
                                "inputs": {
                                    "numbers": {
                                        "nodeType": "output",
                                        "type": "float",
                                        "fromOp": {
                                            "name": "typedDict-pick",
                                            "inputs": {
                                                "self": {
                                                    "nodeType": "var",
                                                    "type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "step": "int",
                                                            "string_col": "string",
                                                            "metric0": "float",
                                                            "metric1": "float",
                                                            "metric2": "float",
                                                            "metric3": "float",
                                                            "metric4": "float",
                                                            "metric5": "float",
                                                            "metric6": "float",
                                                            "metric7": "float",
                                                            "metric8": "float",
                                                            "metric9": "float",
                                                            "metric10": "float",
                                                            "metric11": "float",
                                                            "metric12": "float",
                                                            "metric13": "float",
                                                            "metric14": "float",
                                                            "metric15": "float",
                                                            "metric16": "float",
                                                            "metric17": "float",
                                                            "metric18": "float",
                                                            "metric19": "float",
                                                            "metric20": "float",
                                                            "metric21": "float",
                                                            "metric22": "float",
                                                            "metric23": "float",
                                                            "metric24": "float",
                                                            "metric25": "float",
                                                            "metric26": "float",
                                                            "metric27": "float",
                                                            "metric28": "float",
                                                            "metric29": "float",
                                                            "metric30": "float",
                                                            "metric31": "float",
                                                            "metric32": "float",
                                                            "metric33": "float",
                                                            "metric34": "float",
                                                            "metric35": "float",
                                                            "metric36": "float",
                                                            "metric37": "float",
                                                            "metric38": "float",
                                                            "metric39": "float",
                                                            "metric40": "float",
                                                            "metric41": "float",
                                                            "metric42": "float",
                                                            "metric43": "float",
                                                            "metric44": "float",
                                                            "metric45": "float",
                                                            "metric46": "float",
                                                            "metric47": "float",
                                                            "metric48": "float",
                                                            "metric49": "float",
                                                            "metric50": "float",
                                                            "metric51": "float",
                                                            "metric52": "float",
                                                            "metric53": "float",
                                                            "metric54": "float",
                                                            "metric55": "float",
                                                            "metric56": "float",
                                                            "metric57": "float",
                                                            "metric58": "float",
                                                            "metric59": "float",
                                                            "metric60": "float",
                                                            "metric61": "float",
                                                            "metric62": "float",
                                                            "metric63": "float",
                                                            "metric64": "float",
                                                            "metric65": "float",
                                                            "metric66": "float",
                                                            "metric67": "float",
                                                            "metric68": "float",
                                                            "metric69": "float",
                                                            "metric70": "float",
                                                            "metric71": "float",
                                                            "metric72": "float",
                                                            "metric73": "float",
                                                            "metric74": "float",
                                                            "metric75": "float",
                                                            "metric76": "float",
                                                            "metric77": "float",
                                                            "metric78": "float",
                                                            "metric79": "float",
                                                            "metric80": "float",
                                                            "metric81": "float",
                                                            "metric82": "float",
                                                            "metric83": "float",
                                                            "metric84": "float",
                                                            "metric85": "float",
                                                            "metric86": "float",
                                                            "metric87": "float",
                                                            "metric88": "float",
                                                            "metric89": "float",
                                                            "metric90": "float",
                                                            "metric91": "float",
                                                            "metric92": "float",
                                                            "metric93": "float",
                                                            "metric94": "float",
                                                            "metric95": "float",
                                                            "metric96": "float",
                                                            "metric97": "float",
                                                            "metric98": "float",
                                                            "run_name": "string",
                                                        },
                                                    },
                                                    "varName": "row",
                                                },
                                                "key": {
                                                    "nodeType": "const",
                                                    "type": "string",
                                                    "val": "metric0",
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                        "K5CG252HAV2FLZ": {"nodeType": "void", "type": "invalid"},
                        "9ORNJG56OGUUS2": {"nodeType": "void", "type": "invalid"},
                        "BJB2AY8D1P5JPO": {"nodeType": "void", "type": "invalid"},
                        "EPBPZ7OF3CU3BT": {"nodeType": "void", "type": "invalid"},
                        "PJ3TAMZ9RE8CSQ": {"nodeType": "void", "type": "invalid"},
                        "NQV4ZUZP68VEFU": {"nodeType": "void", "type": "invalid"},
                    },
                    "order": [
                        "LEWVQ43VQJ7UVS",
                        "KRDEEO6PKRDH36",
                        "K5CG252HAV2FLZ",
                        "9ORNJG56OGUUS2",
                        "BJB2AY8D1P5JPO",
                        "EPBPZ7OF3CU3BT",
                        "PJ3TAMZ9RE8CSQ",
                        "NQV4ZUZP68VEFU",
                    ],
                    "groupBy": [],
                    "sort": [],
                    "pageSize": 10,
                    "page": 0,
                },
                "dims": {
                    "x": "LEWVQ43VQJ7UVS",
                    "y": "KRDEEO6PKRDH36",
                    "color": "K5CG252HAV2FLZ",
                    "label": "9ORNJG56OGUUS2",
                    "tooltip": "BJB2AY8D1P5JPO",
                    "pointSize": "EPBPZ7OF3CU3BT",
                    "pointShape": "PJ3TAMZ9RE8CSQ",
                    "y2": "NQV4ZUZP68VEFU",
                },
                "constants": {
                    "mark": "line",
                    "pointShape": "circle",
                    "label": "series",
                    "lineStyle": "solid",
                },
                "uiState": {"pointShape": "expression", "label": "expression"},
            },
            {
                "table": {
                    "autoColumns": False,
                    "columns": {
                        "LEWVQ43VQJ7UVS": {"panelId": "", "panelConfig": None},
                        "KRDEEO6PKRDH36": {"panelId": "", "panelConfig": None},
                        "K5CG252HAV2FLZ": {"panelId": "", "panelConfig": None},
                        "9ORNJG56OGUUS2": {"panelId": "", "panelConfig": None},
                        "BJB2AY8D1P5JPO": {"panelId": "", "panelConfig": None},
                        "EPBPZ7OF3CU3BT": {"panelId": "", "panelConfig": None},
                        "PJ3TAMZ9RE8CSQ": {"panelId": "", "panelConfig": None},
                        "NQV4ZUZP68VEFU": {"panelId": "", "panelConfig": None},
                    },
                    "preFilterFunction": {"nodeType": "void", "type": "invalid"},
                    "columnNames": {
                        "LEWVQ43VQJ7UVS": "",
                        "KRDEEO6PKRDH36": "",
                        "K5CG252HAV2FLZ": "",
                        "9ORNJG56OGUUS2": "",
                        "BJB2AY8D1P5JPO": "",
                        "EPBPZ7OF3CU3BT": "",
                        "PJ3TAMZ9RE8CSQ": "",
                        "NQV4ZUZP68VEFU": "",
                    },
                    "columnSelectFunctions": {
                        "LEWVQ43VQJ7UVS": {
                            "nodeType": "output",
                            "type": {
                                "type": "typedDict",
                                "propertyTypes": {"start": "float", "stop": "float"},
                            },
                            "fromOp": {
                                "name": "number-pybin",
                                "inputs": {
                                    "in_": {
                                        "nodeType": "output",
                                        "type": "int",
                                        "fromOp": {
                                            "name": "typedDict-pick",
                                            "inputs": {
                                                "self": {
                                                    "nodeType": "var",
                                                    "type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "step": "int",
                                                            "string_col": "string",
                                                            "metric0": "float",
                                                            "metric1": "float",
                                                            "metric2": "float",
                                                            "metric3": "float",
                                                            "metric4": "float",
                                                            "metric5": "float",
                                                            "metric6": "float",
                                                            "metric7": "float",
                                                            "metric8": "float",
                                                            "metric9": "float",
                                                            "metric10": "float",
                                                            "metric11": "float",
                                                            "metric12": "float",
                                                            "metric13": "float",
                                                            "metric14": "float",
                                                            "metric15": "float",
                                                            "metric16": "float",
                                                            "metric17": "float",
                                                            "metric18": "float",
                                                            "metric19": "float",
                                                            "metric20": "float",
                                                            "metric21": "float",
                                                            "metric22": "float",
                                                            "metric23": "float",
                                                            "metric24": "float",
                                                            "metric25": "float",
                                                            "metric26": "float",
                                                            "metric27": "float",
                                                            "metric28": "float",
                                                            "metric29": "float",
                                                            "metric30": "float",
                                                            "metric31": "float",
                                                            "metric32": "float",
                                                            "metric33": "float",
                                                            "metric34": "float",
                                                            "metric35": "float",
                                                            "metric36": "float",
                                                            "metric37": "float",
                                                            "metric38": "float",
                                                            "metric39": "float",
                                                            "metric40": "float",
                                                            "metric41": "float",
                                                            "metric42": "float",
                                                            "metric43": "float",
                                                            "metric44": "float",
                                                            "metric45": "float",
                                                            "metric46": "float",
                                                            "metric47": "float",
                                                            "metric48": "float",
                                                            "metric49": "float",
                                                            "metric50": "float",
                                                            "metric51": "float",
                                                            "metric52": "float",
                                                            "metric53": "float",
                                                            "metric54": "float",
                                                            "metric55": "float",
                                                            "metric56": "float",
                                                            "metric57": "float",
                                                            "metric58": "float",
                                                            "metric59": "float",
                                                            "metric60": "float",
                                                            "metric61": "float",
                                                            "metric62": "float",
                                                            "metric63": "float",
                                                            "metric64": "float",
                                                            "metric65": "float",
                                                            "metric66": "float",
                                                            "metric67": "float",
                                                            "metric68": "float",
                                                            "metric69": "float",
                                                            "metric70": "float",
                                                            "metric71": "float",
                                                            "metric72": "float",
                                                            "metric73": "float",
                                                            "metric74": "float",
                                                            "metric75": "float",
                                                            "metric76": "float",
                                                            "metric77": "float",
                                                            "metric78": "float",
                                                            "metric79": "float",
                                                            "metric80": "float",
                                                            "metric81": "float",
                                                            "metric82": "float",
                                                            "metric83": "float",
                                                            "metric84": "float",
                                                            "metric85": "float",
                                                            "metric86": "float",
                                                            "metric87": "float",
                                                            "metric88": "float",
                                                            "metric89": "float",
                                                            "metric90": "float",
                                                            "metric91": "float",
                                                            "metric92": "float",
                                                            "metric93": "float",
                                                            "metric94": "float",
                                                            "metric95": "float",
                                                            "metric96": "float",
                                                            "metric97": "float",
                                                            "metric98": "float",
                                                            "run_name": "string",
                                                        },
                                                    },
                                                    "varName": "row",
                                                },
                                                "key": {
                                                    "nodeType": "const",
                                                    "type": "string",
                                                    "val": "step",
                                                },
                                            },
                                        },
                                    },
                                    "bin_fn": {
                                        "nodeType": "output",
                                        "type": {
                                            "type": "function",
                                            "inputTypes": {"row": "number"},
                                            "outputType": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "start": "float",
                                                    "stop": "float",
                                                },
                                            },
                                        },
                                        "fromOp": {
                                            "name": "numbers-pybinsequal",
                                            "inputs": {
                                                "arr": {
                                                    "nodeType": "output",
                                                    "type": {
                                                        "type": "list",
                                                        "objectType": "int",
                                                    },
                                                    "fromOp": {
                                                        "name": "get",
                                                        "inputs": {
                                                            "uri": {
                                                                "nodeType": "const",
                                                                "type": "string",
                                                                "val": "local-artifact:///tmp/weave/pytest/weave/tests/test_plot.py::test_actual_config_value (setup)/list/dc9ffba8da33b6d87d72d4525afcd383",
                                                            }
                                                        },
                                                    },
                                                },
                                                "bins": {
                                                    "nodeType": "const",
                                                    "type": "int",
                                                    "val": 2,
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "KRDEEO6PKRDH36": {
                            "nodeType": "output",
                            "type": "number",
                            "fromOp": {
                                "name": "numbers-min",
                                "inputs": {
                                    "numbers": {
                                        "nodeType": "output",
                                        "type": "float",
                                        "fromOp": {
                                            "name": "typedDict-pick",
                                            "inputs": {
                                                "self": {
                                                    "nodeType": "var",
                                                    "type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "step": "int",
                                                            "string_col": "string",
                                                            "metric0": "float",
                                                            "metric1": "float",
                                                            "metric2": "float",
                                                            "metric3": "float",
                                                            "metric4": "float",
                                                            "metric5": "float",
                                                            "metric6": "float",
                                                            "metric7": "float",
                                                            "metric8": "float",
                                                            "metric9": "float",
                                                            "metric10": "float",
                                                            "metric11": "float",
                                                            "metric12": "float",
                                                            "metric13": "float",
                                                            "metric14": "float",
                                                            "metric15": "float",
                                                            "metric16": "float",
                                                            "metric17": "float",
                                                            "metric18": "float",
                                                            "metric19": "float",
                                                            "metric20": "float",
                                                            "metric21": "float",
                                                            "metric22": "float",
                                                            "metric23": "float",
                                                            "metric24": "float",
                                                            "metric25": "float",
                                                            "metric26": "float",
                                                            "metric27": "float",
                                                            "metric28": "float",
                                                            "metric29": "float",
                                                            "metric30": "float",
                                                            "metric31": "float",
                                                            "metric32": "float",
                                                            "metric33": "float",
                                                            "metric34": "float",
                                                            "metric35": "float",
                                                            "metric36": "float",
                                                            "metric37": "float",
                                                            "metric38": "float",
                                                            "metric39": "float",
                                                            "metric40": "float",
                                                            "metric41": "float",
                                                            "metric42": "float",
                                                            "metric43": "float",
                                                            "metric44": "float",
                                                            "metric45": "float",
                                                            "metric46": "float",
                                                            "metric47": "float",
                                                            "metric48": "float",
                                                            "metric49": "float",
                                                            "metric50": "float",
                                                            "metric51": "float",
                                                            "metric52": "float",
                                                            "metric53": "float",
                                                            "metric54": "float",
                                                            "metric55": "float",
                                                            "metric56": "float",
                                                            "metric57": "float",
                                                            "metric58": "float",
                                                            "metric59": "float",
                                                            "metric60": "float",
                                                            "metric61": "float",
                                                            "metric62": "float",
                                                            "metric63": "float",
                                                            "metric64": "float",
                                                            "metric65": "float",
                                                            "metric66": "float",
                                                            "metric67": "float",
                                                            "metric68": "float",
                                                            "metric69": "float",
                                                            "metric70": "float",
                                                            "metric71": "float",
                                                            "metric72": "float",
                                                            "metric73": "float",
                                                            "metric74": "float",
                                                            "metric75": "float",
                                                            "metric76": "float",
                                                            "metric77": "float",
                                                            "metric78": "float",
                                                            "metric79": "float",
                                                            "metric80": "float",
                                                            "metric81": "float",
                                                            "metric82": "float",
                                                            "metric83": "float",
                                                            "metric84": "float",
                                                            "metric85": "float",
                                                            "metric86": "float",
                                                            "metric87": "float",
                                                            "metric88": "float",
                                                            "metric89": "float",
                                                            "metric90": "float",
                                                            "metric91": "float",
                                                            "metric92": "float",
                                                            "metric93": "float",
                                                            "metric94": "float",
                                                            "metric95": "float",
                                                            "metric96": "float",
                                                            "metric97": "float",
                                                            "metric98": "float",
                                                            "run_name": "string",
                                                        },
                                                    },
                                                    "varName": "row",
                                                },
                                                "key": {
                                                    "nodeType": "const",
                                                    "type": "string",
                                                    "val": "metric0",
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                        "K5CG252HAV2FLZ": {"nodeType": "void", "type": "invalid"},
                        "9ORNJG56OGUUS2": {"nodeType": "void", "type": "invalid"},
                        "BJB2AY8D1P5JPO": {"nodeType": "void", "type": "invalid"},
                        "EPBPZ7OF3CU3BT": {"nodeType": "void", "type": "invalid"},
                        "PJ3TAMZ9RE8CSQ": {"nodeType": "void", "type": "invalid"},
                        "NQV4ZUZP68VEFU": {
                            "nodeType": "output",
                            "type": "number",
                            "fromOp": {
                                "name": "numbers-max",
                                "inputs": {
                                    "numbers": {
                                        "nodeType": "output",
                                        "type": "float",
                                        "fromOp": {
                                            "name": "typedDict-pick",
                                            "inputs": {
                                                "self": {
                                                    "nodeType": "var",
                                                    "type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "step": "int",
                                                            "string_col": "string",
                                                            "metric0": "float",
                                                            "metric1": "float",
                                                            "metric2": "float",
                                                            "metric3": "float",
                                                            "metric4": "float",
                                                            "metric5": "float",
                                                            "metric6": "float",
                                                            "metric7": "float",
                                                            "metric8": "float",
                                                            "metric9": "float",
                                                            "metric10": "float",
                                                            "metric11": "float",
                                                            "metric12": "float",
                                                            "metric13": "float",
                                                            "metric14": "float",
                                                            "metric15": "float",
                                                            "metric16": "float",
                                                            "metric17": "float",
                                                            "metric18": "float",
                                                            "metric19": "float",
                                                            "metric20": "float",
                                                            "metric21": "float",
                                                            "metric22": "float",
                                                            "metric23": "float",
                                                            "metric24": "float",
                                                            "metric25": "float",
                                                            "metric26": "float",
                                                            "metric27": "float",
                                                            "metric28": "float",
                                                            "metric29": "float",
                                                            "metric30": "float",
                                                            "metric31": "float",
                                                            "metric32": "float",
                                                            "metric33": "float",
                                                            "metric34": "float",
                                                            "metric35": "float",
                                                            "metric36": "float",
                                                            "metric37": "float",
                                                            "metric38": "float",
                                                            "metric39": "float",
                                                            "metric40": "float",
                                                            "metric41": "float",
                                                            "metric42": "float",
                                                            "metric43": "float",
                                                            "metric44": "float",
                                                            "metric45": "float",
                                                            "metric46": "float",
                                                            "metric47": "float",
                                                            "metric48": "float",
                                                            "metric49": "float",
                                                            "metric50": "float",
                                                            "metric51": "float",
                                                            "metric52": "float",
                                                            "metric53": "float",
                                                            "metric54": "float",
                                                            "metric55": "float",
                                                            "metric56": "float",
                                                            "metric57": "float",
                                                            "metric58": "float",
                                                            "metric59": "float",
                                                            "metric60": "float",
                                                            "metric61": "float",
                                                            "metric62": "float",
                                                            "metric63": "float",
                                                            "metric64": "float",
                                                            "metric65": "float",
                                                            "metric66": "float",
                                                            "metric67": "float",
                                                            "metric68": "float",
                                                            "metric69": "float",
                                                            "metric70": "float",
                                                            "metric71": "float",
                                                            "metric72": "float",
                                                            "metric73": "float",
                                                            "metric74": "float",
                                                            "metric75": "float",
                                                            "metric76": "float",
                                                            "metric77": "float",
                                                            "metric78": "float",
                                                            "metric79": "float",
                                                            "metric80": "float",
                                                            "metric81": "float",
                                                            "metric82": "float",
                                                            "metric83": "float",
                                                            "metric84": "float",
                                                            "metric85": "float",
                                                            "metric86": "float",
                                                            "metric87": "float",
                                                            "metric88": "float",
                                                            "metric89": "float",
                                                            "metric90": "float",
                                                            "metric91": "float",
                                                            "metric92": "float",
                                                            "metric93": "float",
                                                            "metric94": "float",
                                                            "metric95": "float",
                                                            "metric96": "float",
                                                            "metric97": "float",
                                                            "metric98": "float",
                                                            "run_name": "string",
                                                        },
                                                    },
                                                    "varName": "row",
                                                },
                                                "key": {
                                                    "nodeType": "const",
                                                    "type": "string",
                                                    "val": "metric0",
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    },
                    "order": [
                        "LEWVQ43VQJ7UVS",
                        "KRDEEO6PKRDH36",
                        "K5CG252HAV2FLZ",
                        "9ORNJG56OGUUS2",
                        "BJB2AY8D1P5JPO",
                        "EPBPZ7OF3CU3BT",
                        "PJ3TAMZ9RE8CSQ",
                        "NQV4ZUZP68VEFU",
                    ],
                    "groupBy": [],
                    "sort": [],
                    "pageSize": 10,
                    "page": 0,
                },
                "dims": {
                    "x": "LEWVQ43VQJ7UVS",
                    "y": "KRDEEO6PKRDH36",
                    "color": "K5CG252HAV2FLZ",
                    "label": "9ORNJG56OGUUS2",
                    "tooltip": "BJB2AY8D1P5JPO",
                    "pointSize": "EPBPZ7OF3CU3BT",
                    "pointShape": "PJ3TAMZ9RE8CSQ",
                    "y2": "NQV4ZUZP68VEFU",
                },
                "constants": {
                    "mark": "area",
                    "pointShape": "circle",
                    "label": "series",
                    "lineStyle": "solid",
                },
                "uiState": {"pointShape": "expression", "label": "expression"},
            },
        ],
        "axisSettings": {
            "x": {"noLabels": False, "noTitle": False, "noTicks": False},
            "y": {"noLabels": False, "noTitle": False, "noTicks": False},
            "color": {"noLabels": False, "noTitle": False, "noTicks": False},
        },
        "legendSettings": {
            "x": {"noLegend": False},
            "y": {"noLegend": False},
            "color": {"noLegend": False},
        },
        "configOptionsExpanded": {
            "x": False,
            "y": False,
            "label": False,
            "tooltip": False,
            "mark": False,
        },
        "configVersion": 7,
    }
