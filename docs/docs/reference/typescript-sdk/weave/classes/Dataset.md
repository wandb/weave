[**weave**](../README.md)

***

[weave](../README.md) / Dataset

# Class: Dataset\<R\>

Defined in: [dataset.ts:48](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L48)

Dataset object with easy saving and automatic versioning

## Example

```ts
// Create a dataset
const dataset = new Dataset({
  id: 'grammar-dataset',
  rows: [
    { id: '0', sentence: "He no likes ice cream.", correction: "He doesn't like ice cream." },
    { id: '1', sentence: "She goed to the store.", correction: "She went to the store." },
    { id: '2', sentence: "They plays video games all day.", correction: "They play video games all day." }
  ]
})

// Access a specific example
const exampleLabel = dataset.getRow(2).sentence;

// Save the dataset
const ref = await dataset.save()
```

## Extends

- [`WeaveObject`](WeaveObject.md)

## Type Parameters

### R

`R` *extends* `DatasetRow`

## Constructors

### Constructor

> **new Dataset**\<`R`\>(`parameters`): `Dataset`\<`R`\>

Defined in: [dataset.ts:51](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L51)

#### Parameters

##### parameters

`DatasetParameters`\<`R`\>

#### Returns

`Dataset`\<`R`\>

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

***

### rows

> **rows**: `Table`\<`R`\>

Defined in: [dataset.ts:49](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L49)

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

### length

#### Get Signature

> **get** **length**(): `number`

Defined in: [dataset.ts:64](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L64)

##### Returns

`number`

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

### \[asyncIterator\]()

> **\[asyncIterator\]**(): `AsyncIterator`\<`any`\>

Defined in: [dataset.ts:68](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L68)

#### Returns

`AsyncIterator`\<`any`\>

***

### className()

> **className**(): `any`

Defined in: [weaveObject.ts:53](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L53)

#### Returns

`any`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`className`](WeaveObject.md#classname)

***

### getRow()

> **getRow**(`index`): `R`

Defined in: [dataset.ts:74](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L74)

#### Parameters

##### index

`number`

#### Returns

`R`

***

### save()

> **save**(): `Promise`\<`ObjectRef`\>

Defined in: [dataset.ts:60](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/dataset.ts#L60)

#### Returns

`Promise`\<`ObjectRef`\>

***

### saveAttrs()

> **saveAttrs**(): `object`

Defined in: [weaveObject.ts:57](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveObject.ts#L57)

#### Returns

`object`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`saveAttrs`](WeaveObject.md#saveattrs)
