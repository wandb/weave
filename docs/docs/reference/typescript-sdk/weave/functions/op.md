[**weave**](../README.md)

***

[weave](../README.md) / op

# Function: op()

## Call Signature

> **op**\<`T`\>(`fn`, `options?`): [`Op`](../type-aliases/Op.md)\<`T`\>

Defined in: [op.ts:369](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/op.ts#L369)

### Type Parameters

#### T

`T` *extends* (...`args`) => `any`

### Parameters

#### fn

`T`

#### options?

`OpOptions`\<`T`\>

### Returns

[`Op`](../type-aliases/Op.md)\<`T`\>

## Call Signature

> **op**\<`T`\>(`thisArg`, `fn`, `options?`): [`Op`](../type-aliases/Op.md)\<`T`\>

Defined in: [op.ts:374](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/op.ts#L374)

### Type Parameters

#### T

`T` *extends* (...`args`) => `any`

### Parameters

#### thisArg

`any`

#### fn

`T`

#### options?

`OpOptions`\<`T`\>

### Returns

[`Op`](../type-aliases/Op.md)\<`T`\>

## Call Signature

> **op**(`target`, `propertyKey`, `descriptor`): `TypedPropertyDescriptor`\<`any`\>

Defined in: [op.ts:380](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/op.ts#L380)

### Parameters

#### target

`Object`

#### propertyKey

`string` | `symbol`

#### descriptor

`TypedPropertyDescriptor`\<`any`\>

### Returns

`TypedPropertyDescriptor`\<`any`\>

## Call Signature

> **op**\<`T`\>(`value`, `context`): [`Op`](../type-aliases/Op.md)\<`T`\>

Defined in: [op.ts:386](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/op.ts#L386)

### Type Parameters

#### T

`T` *extends* (...`args`) => `any`

### Parameters

#### value

`T`

#### context

`MethodDecoratorContext`

### Returns

[`Op`](../type-aliases/Op.md)\<`T`\>

## Call Signature

> **op**(`options`): `MethodDecorator`

Defined in: [op.ts:391](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/op.ts#L391)

### Parameters

#### options

`Partial`\<`OpOptions`\<`any`\>\>

### Returns

`MethodDecorator`
