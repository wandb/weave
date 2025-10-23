[**weave**](../README.md)

***

[weave](../README.md) / MessagesPrompt

# Class: MessagesPrompt

Defined in: [prompt.ts:30](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L30)

## Extends

- `Prompt`

## Constructors

### Constructor

> **new MessagesPrompt**(`parameters`): `MessagesPrompt`

Defined in: [prompt.ts:33](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L33)

#### Parameters

##### parameters

`MessagesPromptParameters`

#### Returns

`MessagesPrompt`

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

### messages

> **messages**: `Record`\<`string`, `any`\>[]

Defined in: [prompt.ts:31](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L31)

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

> **format**(`values`): `Record`\<`string`, `any`\>[]

Defined in: [prompt.ts:60](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/prompt.ts#L60)

#### Parameters

##### values

`Record`\<`string`, `any`\> = `{}`

#### Returns

`Record`\<`string`, `any`\>[]

***

### saveAttrs()

> **saveAttrs**(): `object`

Defined in: [weaveObject.ts:57](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L57)

#### Returns

`object`

#### Inherited from

`Prompt.saveAttrs`
