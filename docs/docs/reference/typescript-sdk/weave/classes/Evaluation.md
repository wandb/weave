[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / Evaluation

# Class: Evaluation\<R, E, M\>

Sets up an evaluation which includes a set of scorers and a dataset.

Calling evaluation.evaluate(model) will pass in rows form a dataset into a model matching
the names of the columns of the dataset to the argument names in model.predict.

Then it will call all of the scorers and save the results in weave.

## Example

```ts
// Collect your examples into a dataset
const dataset = new weave.Dataset({
  id: 'my-dataset',
  rows: [
    { question: 'What is the capital of France?', expected: 'Paris' },
    { question: 'Who wrote "To Kill a Mockingbird"?', expected: 'Harper Lee' },
    { question: 'What is the square root of 64?', expected: '8' },
  ],
});

// Define any custom scoring function
const scoringFunction = weave.op(function isEqual({ modelOutput, datasetRow }) {
  return modelOutput == datasetRow.expected;
});

// Define the function to evaluate
const model = weave.op(async function alwaysParisModel({ question }) {
  return 'Paris';
});

// Start evaluating
const evaluation = new weave.Evaluation({
  id: 'my-evaluation',
  dataset: dataset,
  scorers: [scoringFunction],
});

const results = await evaluation.evaluate({ model });
```

## Extends

- [`WeaveObject`](WeaveObject.md)

## Type Parameters

• **R** *extends* `DatasetRow`

• **E** *extends* `DatasetRow`

• **M**

## Constructors

### new Evaluation()

> **new Evaluation**\<`R`, `E`, `M`\>(`parameters`): [`Evaluation`](Evaluation.md)\<`R`, `E`, `M`\>

#### Parameters

• **parameters**: `EvaluationParameters`\<`R`, `E`, `M`\>

#### Returns

[`Evaluation`](Evaluation.md)\<`R`, `E`, `M`\>

#### Overrides

[`WeaveObject`](WeaveObject.md).[`constructor`](WeaveObject.md#constructors)

#### Defined in

[evaluation.ts:148](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/evaluation.ts#L148)

## Properties

### \_\_savedRef?

> `optional` **\_\_savedRef**: `ObjectRef` \| `Promise`\<`ObjectRef`\>

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`__savedRef`](WeaveObject.md#__savedref)

#### Defined in

[weaveObject.ts:49](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L49)

***

### \_baseParameters

> `protected` **\_baseParameters**: `WeaveObjectParameters`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`_baseParameters`](WeaveObject.md#_baseparameters)

#### Defined in

[weaveObject.ts:51](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L51)

## Accessors

### description

> `get` **description**(): `undefined` \| `string`

#### Returns

`undefined` \| `string`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`description`](WeaveObject.md#description)

#### Defined in

[weaveObject.ts:89](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L89)

***

### id

> `get` **id**(): `string`

#### Returns

`string`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`id`](WeaveObject.md#id)

#### Defined in

[weaveObject.ts:85](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L85)

## Methods

### className()

> **className**(): `any`

#### Returns

`any`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`className`](WeaveObject.md#classname)

#### Defined in

[weaveObject.ts:53](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L53)

***

### evaluate()

> **evaluate**(`__namedParameters`): `Promise`\<`Record`\<`string`, `any`\>\>

#### Parameters

• **\_\_namedParameters**

• **\_\_namedParameters.maxConcurrency?**: `number` = `5`

• **\_\_namedParameters.model**: `WeaveCallable`\<(...`args`) => `Promise`\<`M`\>\>

• **\_\_namedParameters.nTrials?**: `number` = `1`

#### Returns

`Promise`\<`Record`\<`string`, `any`\>\>

#### Defined in

[evaluation.ts:163](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/evaluation.ts#L163)

***

### predictAndScore()

> **predictAndScore**(`__namedParameters`): `Promise`\<`object`\>

#### Parameters

• **\_\_namedParameters**

• **\_\_namedParameters.columnMapping?**: `ColumnMapping`\<`R`, `E`\>

• **\_\_namedParameters.example**: `R`

• **\_\_namedParameters.model**: `WeaveCallable`\<(...`args`) => `Promise`\<`M`\>\>

#### Returns

`Promise`\<`object`\>

##### model\_latency

> **model\_latency**: `number` = `modelLatency`

##### model\_output

> **model\_output**: `any` = `modelOutput`

##### model\_success

> **model\_success**: `boolean` = `!modelError`

##### scores

> **scores**: `object`

###### Index Signature

 \[`key`: `string`\]: `any`

#### Defined in

[evaluation.ts:232](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/evaluation.ts#L232)

***

### saveAttrs()

> **saveAttrs**(): `object`

#### Returns

`object`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`saveAttrs`](WeaveObject.md#saveattrs)

#### Defined in

[weaveObject.ts:57](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L57)
