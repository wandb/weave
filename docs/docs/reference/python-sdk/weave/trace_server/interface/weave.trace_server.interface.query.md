---
sidebar_position: 0
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

- [`query.AndOperation`](./weave.trace_server.interface.query.md#class-andoperation)
- [`query.ContainsOperation`](./weave.trace_server.interface.query.md#class-containsoperation)
- [`query.ContainsSpec`](./weave.trace_server.interface.query.md#class-containsspec)
- [`query.ConvertOperation`](./weave.trace_server.interface.query.md#class-convertoperation)
- [`query.ConvertSpec`](./weave.trace_server.interface.query.md#class-convertspec)
- [`query.EqOperation`](./weave.trace_server.interface.query.md#class-eqoperation)
- [`query.GetFieldOperator`](./weave.trace_server.interface.query.md#class-getfieldoperator)
- [`query.GtOperation`](./weave.trace_server.interface.query.md#class-gtoperation)
- [`query.GteOperation`](./weave.trace_server.interface.query.md#class-gteoperation)
- [`query.LiteralOperation`](./weave.trace_server.interface.query.md#class-literaloperation)
- [`query.NotOperation`](./weave.trace_server.interface.query.md#class-notoperation)
- [`query.OrOperation`](./weave.trace_server.interface.query.md#class-oroperation)
- [`query.Query`](./weave.trace_server.interface.query.md#class-query)




---

## <kbd>class</kbd> `AndOperation`
            
```python
class AndOperation(BaseModel):
    and_: typing.List["Operand"] = Field(alias="$and")

```
            
---
## <kbd>class</kbd> `ContainsOperation`
            
```python
class ContainsOperation(BaseModel):
    contains_: "ContainsSpec" = Field(alias="$contains")

```
            
---
## <kbd>class</kbd> `ContainsSpec`
            
```python
class ContainsSpec(BaseModel):
    input: "Operand"
    substr: "Operand"
    case_insensitive: typing.Optional[bool] = False

```
            
---
## <kbd>class</kbd> `ConvertOperation`
            
```python
class ConvertOperation(BaseModel):
    convert_: "ConvertSpec" = Field(alias="$convert")

```
            
---
## <kbd>class</kbd> `ConvertSpec`
            
```python
class ConvertSpec(BaseModel):
    input: "Operand"
    # Subset of https://www.mongodb.com/docs/manual/reference/bson-types/#std-label-bson-types
    to: CastTo

```
            
---
## <kbd>class</kbd> `EqOperation`
            
```python
class EqOperation(BaseModel):
    eq_: typing.Tuple["Operand", "Operand"] = Field(alias="$eq")

```
            
---
## <kbd>class</kbd> `GetFieldOperator`
            
```python
class GetFieldOperator(BaseModel):
    # Tim: We will likely want to revisit this before making it public. Here are some concerns:
    # 1. Mongo explicitly says that `getField` is used to access fields without dot notation - this
    #    is not how we are handling it here - we are using dot notation - this could be resolved by
    #    supporting the `$field.with.path` shorthand.
    # 2. As Jamie pointed out, the parsing of this field is not very robust and susceptible to issues when:
    #    - The field part name contains a dot
    #    - The field part name is a valid integer (currently interpreted as a list index)
    #    - The field part name contains a double quote (will result in failed lookup - see `_quote_json_path` in `clickhouse_trace_server_batched.py`)
    #    These issues could be resolved by using an alternative syntax (perhaps backticks, square brackets, etc.). However
    #    this would diverge from the current Mongo syntax.
    get_field_: str = Field(alias="$getField")

```
            
---
## <kbd>class</kbd> `GtOperation`
            
```python
class GtOperation(BaseModel):
    gt_: typing.Tuple["Operand", "Operand"] = Field(alias="$gt")

```
            
---
## <kbd>class</kbd> `GteOperation`
            
```python
class GteOperation(BaseModel):
    gte_: typing.Tuple["Operand", "Operand"] = Field(alias="$gte")

```
            
---
## <kbd>class</kbd> `LiteralOperation`
            
```python
class LiteralOperation(BaseModel):
    literal_: typing.Union[
        str,
        int,
        float,
        bool,
        dict[str, "LiteralOperation"],
        list["LiteralOperation"],
        None,
    ] = Field(alias="$literal")

```
            
---
## <kbd>class</kbd> `NotOperation`
            
```python
class NotOperation(BaseModel):
    not_: typing.Tuple["Operand"] = Field(alias="$not")

```
            
---
## <kbd>class</kbd> `OrOperation`
            
```python
class OrOperation(BaseModel):
    or_: typing.List["Operand"] = Field(alias="$or")

```
            
---
## <kbd>class</kbd> `Query`
            
```python
class Query(BaseModel):
    # Here, we use `expr_` to match the MongoDB query language's "aggregation" operator syntax.
    # This is certainly a subset of the full MongoDB query language, but it is a good starting point.
    # https://www.mongodb.com/docs/manual/reference/operator/query/expr/#mongodb-query-op.-expr
    expr_: "Operation" = Field(alias="$expr")
    # In the future, we could have other top-level Query Operators as described here:
    # https://www.mongodb.com/docs/manual/reference/operator/query/

```
            