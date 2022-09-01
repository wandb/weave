import numpy as np

from . import api as weave
from . import ops
from . import weave_types
from .ops_primitives import number, number_bin
from .ops_primitives.string import *

from .weave_internal import make_const_node, call_fn


def test_number_ops():
    nine = make_const_node(weave.types.Number(), 9)
    assert weave.use(nine + 3) == 12
    assert weave.use(nine - 3) == 6
    assert weave.use(nine * 3) == 27
    assert weave.use(nine / 2) == 4.5
    assert weave.use(nine % 3) == 0
    assert weave.use(nine**2) == 81

    assert weave.use(nine == 8) == False
    assert weave.use(nine == 9) == True
    assert weave.use(nine != 8) == True
    assert weave.use(nine != 9) == False
    assert weave.use(nine > 8) == True
    assert weave.use(nine > 9) == False
    assert weave.use(nine < 10) == True
    assert weave.use(nine < 9) == False
    assert weave.use(nine >= 8) == True
    assert weave.use(nine >= 9) == True
    assert weave.use(nine <= 10) == True
    assert weave.use(nine <= 9) == True
    assert weave.use(-nine) == -9
    assert weave.use(nine.pow(2)) == 81

    pi = make_const_node(weave.types.Number(), 3.14)

    assert weave.use(pi.floor()) == 3
    assert weave.use(pi.ceil()) == 4

    one = make_const_node(weave.types.Number(), 1)
    two = make_const_node(weave.types.Number(), 2)
    three = make_const_node(weave.types.Number(), 3)
    list_of_nums = ops.make_list(x1=one, x2=two, x3=three)

    assert weave.use(number.numbers_sum(list_of_nums)) == 6
    assert weave.use(number.numbers_avg(list_of_nums)) == 2
    assert weave.use(number.numbers_min(list_of_nums)) == 1
    assert weave.use(number.numbers_max(list_of_nums)) == 3


def test_string_ops():
    foo = make_const_node(weave.types.String(), "Foo")

    assert weave.use(string(foo)) == "Foo"
    assert weave.use(lastLetter(foo)) == "o"
    assert weave.use(foo == "Foo") == True
    assert weave.use(foo == "Baz") == False
    assert weave.use(foo != "Baz") == True
    assert weave.use(foo != "Foo") == False
    assert weave.use(foo + "Bar") == "FooBar"
    assert weave.use(foo.len()) == 3
    assert weave.use(foo.append("Bar")) == "FooBar"
    assert weave.use(foo.prepend("Bar")) == "BarFoo"
    assert weave.use(foo.lower()) == "foo"
    assert weave.use(foo.upper()) == "FOO"
    assert weave.use(foo.slice(0, 2)) == "Fo"
    assert weave.use(foo.slice(1, 3)) == "oo"
    assert weave.use(foo.replace("oo", "xx")) == "Fxx"

    foobar = make_const_node(weave.types.String(), "Foo bar baz")
    assert weave.use(foobar.split(" ")) == ["Foo", "bar", "baz"]
    assert weave.use(foobar.partition("bar")) == ["Foo ", "bar", " baz"]
    assert weave.use(foobar.startsWith("Foo")) == True
    assert weave.use(foobar.startsWith("bar")) == False
    assert weave.use(foobar.endsWith("baz")) == True
    assert weave.use(foobar.endsWith("bar")) == False

    num_string = make_const_node(weave.types.String(), "123")
    alpha_string = make_const_node(weave.types.String(), "ABC")

    assert weave.use(num_string.isAlpha()) == False
    assert weave.use(num_string.isNumeric()) == True
    assert weave.use(num_string.isAlnum()) == True
    assert weave.use(alpha_string.isAlpha()) == True
    assert weave.use(alpha_string.isNumeric()) == False
    assert weave.use(alpha_string.isAlnum()) == True

    foo_space = make_const_node(weave.types.String(), "  Foo  ")
    assert weave.use(foo_space.strip()) == "Foo"
    assert weave.use(foo_space.lStrip()) == "Foo  "
    assert weave.use(foo_space.rStrip()) == "  Foo"

    # assert weave.use(foo in foobar) == True # Broken
    # assert weave.use(foobar in foo) == False # Broken


def test_number_bin_generation():
    function = number_bin.numbers_bins_equal([1, 2, 3, 4], 10)
    assert function.type == weave_types.Function(
        input_types={"row": weave_types.Float()},
        output_type=number_bin.NumberBin.WeaveType(),
    )
    # extract the function from its containing node
    function = weave.use(function)
    call_node = call_fn(function, {"row": make_const_node(weave.types.Float(), 2.5)})
    result = weave.use(call_node)

    assert np.isclose(result.start, 2.4)
    assert np.isclose(result.stop, 2.7)


def test_number_bin_assignment():
    function = number_bin.numbers_bins_equal([1, 2, 3, 4], 10)
    assert function.type == weave_types.Function(
        input_types={"row": weave_types.Float()},
        output_type=number_bin.NumberBin.WeaveType(),
    )
    # create a graph representing bin assignment
    assigned_number_bin_node = number_bin.number_bin(in_=2.5, bin_fn=function)
    assigned_bin = weave.use(assigned_number_bin_node)

    assert np.isclose(assigned_bin.start, 2.4)
    assert np.isclose(assigned_bin.stop, 2.7)

    # now do one outside the original range
    assigned_number_bin_node = number_bin.number_bin(in_=7, bin_fn=function)
    assigned_bin = weave.use(assigned_number_bin_node)

    assert np.isclose(assigned_bin.start, 6.9)
    assert np.isclose(assigned_bin.stop, 7.2)
