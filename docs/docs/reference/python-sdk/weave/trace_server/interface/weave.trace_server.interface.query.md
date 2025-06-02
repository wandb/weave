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

- [`query.AndOperation`](#class-andoperation): Logical AND. All conditions must evaluate to true.
- [`query.ContainsOperation`](#class-containsoperation): Case-insensitive substring match.
- [`query.ContainsSpec`](#class-containsspec): Specification for the `$contains` operation.
- [`query.ConvertOperation`](#class-convertoperation): Convert the input value to a specific type (e.g., `int`, `bool`, `string`).
- [`query.ConvertSpec`](#class-convertspec): Specifies conversion details for `$convert`.
- [`query.EqOperation`](#class-eqoperation): Equality check between two operands.
- [`query.GetFieldOperator`](#class-getfieldoperator): Access a field on the traced call.
- [`query.GtOperation`](#class-gtoperation): Greater than comparison.
- [`query.GteOperation`](#class-gteoperation): Greater than or equal comparison.
- [`query.InOperation`](#class-inoperation): Membership check.
- [`query.LiteralOperation`](#class-literaloperation): Represents a constant value in the query language.
- [`query.NotOperation`](#class-notoperation): Logical NOT. Inverts the condition.
- [`query.OrOperation`](#class-oroperation): Logical OR. At least one condition must be true.
- [`query.Query`](#class-query): The top-level object for querying traced calls.




---


<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L132"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `AndOperation`
Logical AND. All conditions must evaluate to true. 



**Example:**
 ```
     {
         "$and": [
             {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]},
             {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]}
         ]
     }
    ``` 


**Pydantic Fields:**

- `$and`: `list[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L260"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContainsOperation`
Case-insensitive substring match. 

Not part of MongoDB. Weave-specific addition. 



**Example:**
 ```
     {
         "$contains": {
             "input": {"$getField": "display_name"},
             "substr": {"$literal": "llm"},
             "case_insensitive": true
         }
     }
    ``` 


**Pydantic Fields:**

- `$contains`: `<class 'ContainsSpec'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L281"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ContainsSpec`
Specification for the `$contains` operation. 


- `input`: The string to search. 
- `substr`: The substring to search for. 
- `case_insensitive`: If true, match is case-insensitive. 


**Pydantic Fields:**

- `input`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]`
- `substr`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]`
- `case_insensitive`: `typing.Optional[bool]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L97"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ConvertOperation`
Convert the input value to a specific type (e.g., `int`, `bool`, `string`). 



**Example:**
 ```
     {
         "$convert": {
             "input": {"$getField": "inputs.value"},
             "to": "int"
         }
     }
    ``` 


**Pydantic Fields:**

- `$convert`: `<class 'ConvertSpec'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L118"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `ConvertSpec`
Specifies conversion details for `$convert`. 


- `input`: The operand to convert. 
- `to`: The type to convert to. 


**Pydantic Fields:**

- `input`: `typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]`
- `to`: `typing.Literal['double', 'string', 'int', 'bool', 'exists']`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L188"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `EqOperation`
Equality check between two operands. 



**Example:**
 ```
     {
         "$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]
     }
    ``` 


**Pydantic Fields:**

- `$eq`: `tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L67"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GetFieldOperator`
Access a field on the traced call. 

Supports dot notation for nested access, e.g. `summary.usage.tokens`. 

Only works on fields present in the `CallSchema`, including: 
- Top-level fields like `op_name`, `trace_id`, `started_at` 
- Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc. 



**Example:**
 ```
     {"$getField": "op_name"}
    ``` 


**Pydantic Fields:**

- `$getField`: `<class 'str'>`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L204"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GtOperation`
Greater than comparison. 



**Example:**
 ```
     {
         "$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
     }
    ``` 


**Pydantic Fields:**

- `$gt`: `tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L220"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `GteOperation`
Greater than or equal comparison. 



**Example:**
 ```
     {
         "$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
     }
    ``` 


**Pydantic Fields:**

- `$gte`: `tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation], typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L236"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `InOperation`
Membership check. 

Returns true if the left operand is in the list provided as the second operand. 



**Example:**
 ```
     {
         "$in": [
             {"$getField": "op_name"},
             [{"$literal": "predict"}, {"$literal": "generate"}]
         ]
     }
    ``` 


**Pydantic Fields:**

- `$in`: `tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation], list[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L38"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `LiteralOperation`
Represents a constant value in the query language. 

This can be any standard JSON-serializable value. 



**Example:**
 ```
     {"$literal": "predict"}
    ``` 


**Pydantic Fields:**

- `$literal`: `typing.Union[str, int, float, bool, dict[str, LiteralOperation], list[LiteralOperation], NoneType]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L170"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `NotOperation`
Logical NOT. Inverts the condition. 



**Example:**
 ```
     {
         "$not": [
             {"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}
         ]
     }
    ``` 


**Pydantic Fields:**

- `$not`: `tuple[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L151"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `OrOperation`
Logical OR. At least one condition must be true. 



**Example:**
 ```
     {
         "$or": [
             {"$eq": [{"$getField": "op_name"}, {"$literal": "a"}]},
             {"$eq": [{"$getField": "op_name"}, {"$literal": "b"}]}
         ]
     }
    ``` 


**Pydantic Fields:**

- `$or`: `list[typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]]`

---

<a href="https://github.com/wandb/weave/blob/master/weave/trace_server/interface/query.py#L321"><img align="right" src="https://img.shields.io/badge/-source-cccccc?style=flat-square" /></a>

## <kbd>class</kbd> `Query`
The top-level object for querying traced calls. 

The `Query` wraps a single `$expr`, which uses Mongo-style aggregation operators to filter calls. This expression can combine logical conditions, comparisons, type conversions, and string matching. 



**Examples:**
 ```
     # Filter calls where op_name == "predict"
     {
         "$expr": {
             "$eq": [
                 {"$getField": "op_name"},
                 {"$literal": "predict"}
             ]
         }
     }

     # Filter where a call's display name contains "llm"
     {
         "$expr": {
             "$contains": {
                 "input": {"$getField": "display_name"},
                 "substr": {"$literal": "llm"},
                 "case_insensitive": true
             }
         }
     }
    ``` 


**Pydantic Fields:**

- `$expr`: `typing.Union[AndOperation, OrOperation, NotOperation, EqOperation, GtOperation, GteOperation, InOperation, ContainsOperation]`
