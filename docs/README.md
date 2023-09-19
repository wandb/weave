Welcome to the Weave Ecosystem!

This is a breadth-first outline of everything Weave is and can do—to be deepened.

# What is Weave?

Weave is new kind of visual development environment, designed for developing AI-powered software. 
Working in Weave means composing, manipulating, and extending a compute graph of typed objects, or Weave Nodes:
A Weave Node represents a Weave Expression, which you can view by converting a Weave Node to a string.

# Loading and manipulating data in Weave

## weave.save
`weave.save()` - save any object into Weave, optionally giving it a name

## weave.use()

# Types

Every object in Weave is a Weave Node which has a more specific Weave Type, such as String, Number, List, etc.
* `weave_node.type` - see a Weave Node's type attribute	 

## Working with Types

## Basic Types

### Number

Number handles numeric types, including Python integers and floats

### String

String handles text

### Weave Bool

## Container types

## Custom types

# Ops

## Number Ops

### Operands

Relations between two Weave Numbers
1. basic mathematical functions
  1. `+` - addition
  2. `-` - subtraction
  3. `*` - multiplication
  4. `/` or `//` - division
  5. `%` - mod
  6. `^` - exponential
2. comparison by value
  1. `==` - equality
  2. `!=` - inequality
  3. `>`, `>=` - greater than, greater than or equal to
  4. `<`, `<=` - less than, less than or equal to

1. more advanced mathematical functions
  1. sin
  2. cos
2. formatting numerical values: abs, ceil, round, toString, toTimestamp
relevant generics: isNone, json_dumps
Making histograms & panels
May not be relevant for every instance of a number

number_bins_fixed, timestamp_bins_fixed
gauss, random_normal(), random_normal(,)
_new_Facet_CellSize(), _new_Point2D, _new_Size2D(,)

### Strings

## Multi-Table

### Join

# Panels

# Using Weave

## Weave from Python

## Rich interactive visualization in notebooks

## EDA with Weave Boards

## Query layer for W&B data

## Make new Weave Ops & Weave Panels

## Build and share interactive apps
