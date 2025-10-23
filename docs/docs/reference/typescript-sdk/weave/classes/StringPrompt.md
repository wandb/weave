[**weave**](../README.md)

***

[weave](../README.md) / StringPrompt

# Class: StringPrompt

Defined in: [prompt.ts:13](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L13)

## Extends

- `Prompt`

## Constructors

### Constructor

> **new StringPrompt**(`parameters`): `StringPrompt`

Defined in: [prompt.ts:16](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L16)

#### Parameters

##### parameters

`StringPromptParameters`

#### Returns

`StringPrompt`

#### Overrides

`Prompt.constructor`

## Properties

### \_\_savedRef?

> `optional` **\_\_savedRef**: `ObjectRef` \| `Promise`\<`ObjectRef`\>

Defined in: [weaveObject.ts:49](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L49)

#### Inherited from

`Prompt.__savedRef`

***

### \_baseParameters

> `protected` **\_baseParameters**: `WeaveObjectParameters`

Defined in: [weaveObject.ts:51](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L51)

#### Inherited from

`Prompt._baseParameters`

***

### content

> **content**: `string`

Defined in: [prompt.ts:14](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L14)

## Accessors

### description

#### Get Signature

> **get** **description**(): `undefined` \| `string`

Defined in: [weaveObject.ts:80](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L80)

##### Returns

`undefined` \| `string`

#### Inherited from

`Prompt.description`

***

### name

#### Get Signature

> **get** **name**(): `string`

Defined in: [weaveObject.ts:76](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L76)

##### Returns

`string`

#### Inherited from

`Prompt.name`

## Methods

### className()

> **className**(): `any`

Defined in: [weaveObject.ts:53](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L53)

#### Returns

`any`

#### Inherited from

`Prompt.className`

***

### format()

> **format**(`values`): `string`

Defined in: [prompt.ts:21](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L21)

#### Parameters

##### values

`Record`\<`string`, `any`\> = `{}`

#### Returns

`string`

***

### saveAttrs()

> **saveAttrs**(): `object`

Defined in: [weaveObject.ts:57](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L57)

#### Returns

`object`

#### Inherited from

`Prompt.saveAttrs`
