# Weave Technical Overview

Contents

- What is Weave
- Weave Types
- Weave Ops
- Weave Panels


# What is Weave

Weave is new kind of visual development environment, designed for developing AI-powered software.

Building and working with AI models is a fuzzy process. The work is iterative, experimental, analytical, and visual.

This evolving technical overview accompanies our interactive notebooks to document and explain Weave in more detail.


# Weave Types

## Basic Types

Follow along in this notebook to render interactive Weave Panels: [basic weave types](../examples/experimental/skip_test/basic_weave_types.ipynb)

In the code samples below, `weave.save()` creates an object in the Weave node graph and `weave.use()` computes the existing graph and returns the value.

### Number

The Weave Number type handles numeric types, inlcuding Python integers and floats. 

```
>>> num = weave.save(5, "num")
>>> num.type
Int()
>>> decimal = weave.save(9.123, "decimal")
>>> decimal.type
Float()
>>> sum_so_far = num + decimal
>>> sum_so_far.type
Number()
```

### Number ops

The following operations can be called on Number:

**Operands**

Relations between two Weave nodes

- basic comparison ops: !=, ==, >, >=, <, <=
- basic mathematical operations: +, -, \*, /, //, \*\*, %

**Ecosystem ops**

Weave ops callable on a single Weave node via dot notation

```
>>> weave.use(sum_so_far.ceil())
>>> 10
```

* more advanced math: `sin`, `cos`
* formatting numerical values: `abs`, `ceil`, `round`, `toString`, `toTimestamp`
* relevant generics: `isNone`, `json_dumps`

**Advanced: Making distributions and histogram panels**

These advanced ops are not relevant for every instance of a number. They are convenient shorthand to return common
statistical distributions, configure histogram bins, and set up Weave Panels of a particular dimension

* `gauss`, `random_normal()`, `random_normal(,)`
* `number_bins_fixed`, `timestamp_bins_fixed`
* `\_new_Facet_CellSize`, `\_new_Point2D`, `\_new_Size2D(,)`

**Misc ops**

Ops available in the ecosystem for demo purposes
* `an_example_op`, `food101`, `mnist`, `ca_housing_dataset`, `days`

### Number panels

The Weave Number panel is a single cell with the Number's value centered. This is the fundamental visual unit of Weave Tables and the default
panel type returned for most Weave graphs.

### String

The Weave String type handles text.

```
>>> hello = weave.save("hello", "my_greeting")
>>> world = weave.save("world", "who")
>>> hello_world = hello + " " + world
>>> weave.use(hello_world)
Hello world
```

### String ops

The following Weave ops are available on Strings:

* basic operands: ==, !=, +
* basic type checks: `isAlpha`, `isAlnum`, `isNumeric`
* basic callable ops: `append`, `lStrip`, `rStrip`, `lower`, `len`, `prepend`
* basic formatting:  `json_parse`, `json_parse_list`, `date_parse`
* more sophisticated string search/matching: `contains`, `endsWith`, `findAll`, `levenshtein`, `replace`, `slice`, `split`
* relevant generics: `isNone`, `json_dumps`

```
>>> greet = hello.replace("hello", "Hi").replace("world", "Weave") + "!"
>>> weave.use(greet)
'Hi Weave!'
```

### String panels

The default String panel is a single cell with the String's value left aligned and vertically centered. A String Panel can be converted to a
StringEditor panel in the UI by clicking on the panel type to reveal the panel type menu and selecting `StringEditor`. The contents of a 
StringEditor panel are editable and will save their latest state: click on the StringEditor text once to highlight it, then again to place a cursor
at that index.

## Type Conversion

We can convert between types using ops.

Type conversion ops available so far:

* `toString` for converting Number to String
* `toNumber` for converting String to Number

```
>>> num_as_str = num.toString()
>>> num_as_str.type
String()
```
