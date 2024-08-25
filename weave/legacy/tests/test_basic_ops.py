from weave.legacy.weave import api as weave
from weave.legacy.weave import box, ops
from weave.legacy.weave.ops_primitives import number
from weave.legacy.weave.ops_primitives.string import *
from weave.legacy.weave.weave_internal import make_const_node


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
    assert weave.use(nine.toString()) == "9"

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

    assert weave.use(num_string.toNumber()) == 123
    assert weave.use(alpha_string.toNumber()) == None

    # assert weave.use(foo in foobar) == True # Broken
    # assert weave.use(foobar in foo) == False # Broken


def test_null_consuming_numbers_ops():
    data = [box.box(1), box.box(None), box.box(2)]

    assert weave.use(number.numbers_sum(data)) == 3
    assert weave.use(number.numbers_avg(data)) == 1.5
    assert weave.use(number.numbers_min(data)) == 1
    assert weave.use(number.numbers_max(data)) == 2
    assert number.numbers_max(data).type == weave.types.optional(weave.types.Int())
    assert number.numbers_avg(data).type == weave.types.optional(weave.types.Number())

    data = [box.box(None), box.box(None), box.box(None)]
    assert weave.use(number.numbers_sum(data)) == None
    assert weave.use(number.numbers_avg(data)) == None
    assert weave.use(number.numbers_min(data)) == None
    assert weave.use(number.numbers_max(data)) == None
    assert number.numbers_max(data).type == weave.types.NoneType()

    data = []
    assert weave.use(number.numbers_sum(data)) == None
    assert weave.use(number.numbers_avg(data)) == None
    assert weave.use(number.numbers_min(data)) == None
    assert weave.use(number.numbers_max(data)) == None
    assert number.numbers_max(data).type == weave.types.NoneType()


def test_null_vararg_ops():
    assert weave.use(ops.dict_(index=None, id=None)) == {"index": None, "id": None}
    assert weave.use(ops.make_list(index=None, id=None)) == [None, None]
