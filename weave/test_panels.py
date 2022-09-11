import pytest
from rich import print

from .panels.panel_group2 import Group2
from .panels.panel_slider2 import Slider2
from . import weave_internal
import weave


def test_panel_id():
    panel = Group2(items={})
    assert panel.id == "group2"
    assert panel.to_json()["id"] == "group2"


def test_simple_nested():
    panel = Group2(
        vars={"a": weave_internal.make_const_node(weave.types.Int(), 5)},
        items={
            "item": Group2(
                vars={"b": weave_internal.make_const_node(weave.types.Int(), 9)},
                items={"item_inner": lambda a, b: a + b},
            )
        },
    )
    panel._normalize()
    assert str(panel.items["item"].items["item_inner"]) == "add(a, b)"


def test_simple_nested_outer_lambda():
    panel = Group2(
        vars={"a": weave_internal.make_const_node(weave.types.Int(), 5)},
        items={
            "item": lambda a: Group2(
                vars={"b": weave_internal.make_const_node(weave.types.Int(), 9)},
                items={"item_inner": lambda b: a + b},
            )
        },
    )
    panel._normalize()
    assert str(panel.items["item"].items["item_inner"]) == "add(a, b)"


def test_controlled_state_out():
    panel = Group2(
        items={"my_slider": Slider2(), "val": lambda my_slider: my_slider.value}
    )
    panel._normalize()
    # panel.items['val'] will have been converted to a node, stringifying it
    # produces an expression string.
    assert str(panel.items["val"]) == "my_slider.value"


@pytest.mark.skip()
def test_nested():
    # Doesn't quite work, we get the wrong type for
    # a.items['a2'] (we get Panel, actually want Panel[number] I think?)
    panel = Group2(
        items={
            "a": Group2(items={"a1": 5, "a2": lambda a1: a1 + 5}),
            "b": Group2(
                items={"b1": lambda a: a.items["a1"], "b2": lambda a: a.items["a2"]}
            ),
        }
    )
    panel.normalize()
    print("NORM", panel)
    assert 1 == 2


@pytest.mark.skip()
def test_synced():
    panel = Group2(
        vars={"num": 0},
        items={
            "a": lambda num: Slider2(num),
            "b": lambda num: Slider2(num),
            "c": lambda num: num,
        },
    )
    print(panel.to_json())
    assert 1 == 2


# def test_select_row():
#     panel = Group2(
#         items={"step": Slider2(), "table": panellambda my_slider: my_slider.value}
# )
