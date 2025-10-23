[**weave**](../README.md)

***

[weave](../README.md) / Evaluation

# Class: Evaluation\<R, E, M\>

Defined in: [evaluation.ts:137](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/evaluation.ts#L137)

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

### R

`R` *extends* `DatasetRow`

### E

`E` *extends* `DatasetRow`

### M

`M`

## Constructors

### Constructor

> **new Evaluation**\<`R`, `E`, `M`\>(`parameters`): `Evaluation`\<`R`, `E`, `M`\>

Defined in: [evaluation.ts:148](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/evaluation.ts#L148)

#### Parameters

##### parameters

`EvaluationParameters`\<`R`, `E`, `M`\>

#### Returns

`Evaluation`\<`R`, `E`, `M`\>

#### Overrides

[`WeaveObject`](WeaveObject.md).[`constructor`](WeaveObject.md#constructor)

## Properties

### \_\_savedRef?

> `optional` **\_\_savedRef**: `ObjectRef` \| `Promise`\<`ObjectRef`\>

Defined in: [weaveObject.ts:49](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L49)

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`__savedRef`](WeaveObject.md#__savedref)

***

### \_baseParameters

> `protected` **\_baseParameters**: `WeaveObjectParameters`

Defined in: [weaveObject.ts:51](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L51)

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`_baseParameters`](WeaveObject.md#_baseparameters)

## Accessors

### description

#### Get Signature

> **get** **description**(): `undefined` \| `string`

Defined in: [weaveObject.ts:80](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L80)

##### Returns

`undefined` \| `string`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`description`](WeaveObject.md#description)

***

### name

#### Get Signature

> **get** **name**(): `string`

Defined in: [weaveObject.ts:76](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L76)

##### Returns

`string`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`name`](WeaveObject.md#name)

## Methods

### className()

> **className**(): `any`

Defined in: [weaveObject.ts:53](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L53)

#### Returns

`any`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`className`](WeaveObject.md#classname)

***

### evaluate()

> **evaluate**(`__namedParameters`): `Promise`\<`Record`\<`string`, `any`\>\>

Defined in: [evaluation.ts:163](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/evaluation.ts#L163)

#### Parameters

##### \_\_namedParameters

###### maxConcurrency?

`number` = `5`

###### model

`WeaveCallable`\<(...`args`) => `Promise`\<`M`\>\>

###### nTrials?

`number` = `1`

#### Returns

`Promise`\<`Record`\<`string`, `any`\>\>

***

### predictAndScore()

> **predictAndScore**(`__namedParameters`): `Promise`\<\{ `model_latency`: `number`; `model_output`: `any`; `model_success`: `boolean`; `scores`: \{[`key`: `string`]: `any`; \}; \}\>

Defined in: [evaluation.ts:231](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/evaluation.ts#L231)

#### Parameters

##### \_\_namedParameters

###### columnMapping?

`ColumnMapping`\<`R`, `E`\>

###### example

`R`

###### model

`WeaveCallable`\<(...`args`) => `Promise`\<`M`\>\>

#### Returns

`Promise`\<\{ `model_latency`: `number`; `model_output`: `any`; `model_success`: `boolean`; `scores`: \{[`key`: `string`]: `any`; \}; \}\>

***

### saveAttrs()

> **saveAttrs**(): `object`

Defined in: [weaveObject.ts:57](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L57)

#### Returns

`object`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`saveAttrs`](WeaveObject.md#saveattrs)
