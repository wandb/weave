[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / Dataset

# Class: Dataset\<R\>

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

• **R** *extends* `DatasetRow`

## Constructors

### new Dataset()

> **new Dataset**\<`R`\>(`parameters`): [`Dataset`](Dataset.md)\<`R`\>

#### Parameters

• **parameters**: `DatasetParameters`\<`R`\>

#### Returns

[`Dataset`](Dataset.md)\<`R`\>

#### Overrides

[`WeaveObject`](WeaveObject.md).[`constructor`](WeaveObject.md#constructors)

#### Defined in

[dataset.ts:51](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L51)

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

***

### rows

> **rows**: `Table`\<`R`\>

#### Defined in

[dataset.ts:49](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L49)

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

***

### length

> `get` **length**(): `number`

#### Returns

`number`

#### Defined in

[dataset.ts:64](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L64)

## Methods

### \[asyncIterator\]()

> **\[asyncIterator\]**(): `AsyncIterator`\<`any`, `any`, `undefined`\>

#### Returns

`AsyncIterator`\<`any`, `any`, `undefined`\>

#### Defined in

[dataset.ts:68](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L68)

***

### className()

> **className**(): `any`

#### Returns

`any`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`className`](WeaveObject.md#classname)

#### Defined in

[weaveObject.ts:53](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L53)

***

### getRow()

> **getRow**(`index`): `R`

#### Parameters

• **index**: `number`

#### Returns

`R`

#### Defined in

[dataset.ts:74](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L74)

***

### save()

> **save**(): `Promise`\<`ObjectRef`\>

#### Returns

`Promise`\<`ObjectRef`\>

#### Defined in

[dataset.ts:60](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/dataset.ts#L60)

***

### saveAttrs()

> **saveAttrs**(): `object`

#### Returns

`object`

#### Inherited from

[`WeaveObject`](WeaveObject.md).[`saveAttrs`](WeaveObject.md#saveattrs)

#### Defined in

[weaveObject.ts:57](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveObject.ts#L57)
