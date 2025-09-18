[**weave**](../README.md)

***

[weave](../README.md) / Op

# Type Alias: Op\<T\>

> **Op**\<`T`\> = `object` & `T` & (...`args`) => `ReturnType`\<`T`\> *extends* `AsyncIterable`\<infer U\> ? `AsyncIterable`\<`Awaited`\<`U`\>\> : `Promise`\<`Awaited`\<`ReturnType`\<`T`\>\>\>

Defined in: [opType.ts:7](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/opType.ts#L7)

## Type declaration

### \_\_boundThis?

> `optional` **\_\_boundThis**: [`WeaveObject`](../classes/WeaveObject.md)

### \_\_isOp

> **\_\_isOp**: `true`

### \_\_name

> **\_\_name**: `string`

### \_\_parameterNames?

> `optional` **\_\_parameterNames**: `ParameterNamesOption`

### \_\_savedRef?

> `optional` **\_\_savedRef**: `OpRef` \| `Promise`\<`OpRef`\>

### \_\_wrappedFunction

> **\_\_wrappedFunction**: `T`

### invoke

> **invoke**: `CallMethod`\<`T`\>

## Type Parameters

### T

`T` *extends* (...`args`) => `any`
