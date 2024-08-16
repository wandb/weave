---
sidebar_label: query
---
    

# weave.trace_server.interface.query


This file contains the interface definition for the Trace Server Query model. It
is heavily inspired by the MongoDB query language, but is a subset of the full
MongoDB query language. In particular, we have made the following
simplifications:

* We only support the "aggregation" operators, not the "query" operators. This is
    purely for simplicity and because the "aggregation" operators are more powerful.
    The Mongo docs language has evolved over time and the primary query language
    is column-oriented. However, the more expressive aggregation language can be
    used for both direct queries, but also for column comparison and
    calculations. We can add support for the "query" operators in the future if
    needed.

* We only support a subset of the operators / shorthand forms for now. We can add
    more operators in the future as needed.

    * One notable omission here is the lack of support for "$field" as a shorthand for
        the "getField"  operator.

* We have _added_ a `$contains` operator which is not in the MongoDB query
    language. This is a simple substring match operator.


---


# API Overview



## Classes

- [`query.AndOperation`](#class-andoperation)
- [`query.ContainsOperation`](#class-containsoperation)
- [`query.ContainsSpec`](#class-containsspec)
- [`query.ConvertOperation`](#class-convertoperation)
- [`query.ConvertSpec`](#class-convertspec)
- [`query.EqOperation`](#class-eqoperation)
- [`query.GetFieldOperator`](#class-getfieldoperator)
- [`query.GtOperation`](#class-gtoperation)
- [`query.GteOperation`](#class-gteoperation)
- [`query.LiteralOperation`](#class-literaloperation)
- [`query.NotOperation`](#class-notoperation)
- [`query.OrOperation`](#class-oroperation)
- [`query.Query`](#class-query)




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L95"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `AndOperation`





**Pydantic Fields:**

- `$and`: `typing.List[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L128"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContainsOperation`





**Pydantic Fields:**

- `$contains`: `<class 'ContainsSpec'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L132"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContainsSpec`





**Pydantic Fields:**

- `input`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]`
- `substr`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]`
- `case_insensitive`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L81"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ConvertOperation`





**Pydantic Fields:**

- `$convert`: `<class 'ConvertSpec'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L88"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ConvertSpec`





**Pydantic Fields:**

- `input`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]`
- `to`: `typing.Literal['double', 'string', 'int', 'bool', 'exists']`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L110"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EqOperation`





**Pydantic Fields:**

- `$eq`: `typing.Tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L66"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GetFieldOperator`





**Pydantic Fields:**

- `$getField`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L115"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GtOperation`





**Pydantic Fields:**

- `$gt`: `typing.Tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L120"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GteOperation`





**Pydantic Fields:**

- `$gte`: `typing.Tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L48"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LiteralOperation`





**Pydantic Fields:**

- `$literal`: `typing.Union[str, int, float, bool, dict[str, 'LiteralOperation'], list['LiteralOperation'], NoneType]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L105"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `NotOperation`





**Pydantic Fields:**

- `$not`: `typing.Tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L100"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OrOperation`





**Pydantic Fields:**

- `$or`: `typing.List[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L30"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Query`





**Pydantic Fields:**

- `$expr`: `typing.Union[AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, ContainsOperation]`
