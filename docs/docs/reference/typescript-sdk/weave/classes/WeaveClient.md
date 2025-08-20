[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / WeaveClient

# Class: WeaveClient

## Constructors

### new WeaveClient()

> **new WeaveClient**(`traceServerApi`, `wandbServerApi`, `projectId`, `settings`): [`WeaveClient`](WeaveClient.md)

#### Parameters

• **traceServerApi**: `Api`\<`any`\>

• **wandbServerApi**: `WandbServerApi`

• **projectId**: `string`

• **settings**: `Settings` = `...`

#### Returns

[`WeaveClient`](WeaveClient.md)

#### Defined in

[weaveClient.ts:82](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L82)

## Properties

### projectId

> **projectId**: `string`

#### Defined in

[weaveClient.ts:85](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L85)

***

### settings

> **settings**: `Settings`

#### Defined in

[weaveClient.ts:86](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L86)

***

### traceServerApi

> **traceServerApi**: `Api`\<`any`\>

#### Defined in

[weaveClient.ts:83](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L83)

## Methods

### createCall()

> **createCall**(`opRef`, `params`, `parameterNames`, `thisArg`, `currentCall`, `parentCall`, `startTime`, `displayName`?): `Promise`\<`void`\>

#### Parameters

• **opRef**: `any`

• **params**: `any`[]

• **parameterNames**: `ParameterNamesOption`

• **thisArg**: `any`

• **currentCall**: `CallStackEntry`

• **parentCall**: `undefined` \| `CallStackEntry`

• **startTime**: `Date`

• **displayName?**: `string`

#### Returns

`Promise`\<`void`\>

#### Defined in

[weaveClient.ts:610](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L610)

***

### finishCall()

> **finishCall**(`result`, `currentCall`, `parentCall`, `summarize`, `endTime`, `startCallPromise`): `Promise`\<`void`\>

#### Parameters

• **result**: `any`

• **currentCall**: `CallStackEntry`

• **parentCall**: `undefined` \| `CallStackEntry`

• **summarize**: `undefined` \| (`result`) => `Record`\<`string`, `any`\>

• **endTime**: `Date`

• **startCallPromise**: `Promise`\<`void`\>

#### Returns

`Promise`\<`void`\>

#### Defined in

[weaveClient.ts:648](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L648)

***

### finishCallWithException()

> **finishCallWithException**(`error`, `currentCall`, `parentCall`, `endTime`, `startCallPromise`): `Promise`\<`void`\>

#### Parameters

• **error**: `any`

• **currentCall**: `CallStackEntry`

• **parentCall**: `undefined` \| `CallStackEntry`

• **endTime**: `Date`

• **startCallPromise**: `Promise`\<`void`\>

#### Returns

`Promise`\<`void`\>

#### Defined in

[weaveClient.ts:677](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L677)

***

### get()

> **get**(`ref`): `Promise`\<`any`\>

#### Parameters

• **ref**: `ObjectRef`

#### Returns

`Promise`\<`any`\>

#### Defined in

[weaveClient.ts:229](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L229)

***

### getCalls()

> **getCalls**(`filter`, `includeCosts`, `limit`): `Promise`\<[`CallSchema`](../interfaces/CallSchema.md)[]\>

#### Parameters

• **filter**: [`CallsFilter`](../interfaces/CallsFilter.md) = `{}`

• **includeCosts**: `boolean` = `false`

• **limit**: `number` = `1000`

#### Returns

`Promise`\<[`CallSchema`](../interfaces/CallSchema.md)[]\>

#### Defined in

[weaveClient.ts:172](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L172)

***

### getCallsIterator()

> **getCallsIterator**(`filter`, `includeCosts`, `limit`): `AsyncIterableIterator`\<[`CallSchema`](../interfaces/CallSchema.md)\>

#### Parameters

• **filter**: [`CallsFilter`](../interfaces/CallsFilter.md) = `{}`

• **includeCosts**: `boolean` = `false`

• **limit**: `number` = `1000`

#### Returns

`AsyncIterableIterator`\<[`CallSchema`](../interfaces/CallSchema.md)\>

#### Defined in

[weaveClient.ts:184](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L184)

***

### getCallStack()

> **getCallStack**(): `CallStack`

#### Returns

`CallStack`

#### Defined in

[weaveClient.ts:537](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L537)

***

### publish()

> **publish**(`obj`, `objId`?): `Promise`\<`ObjectRef`\>

#### Parameters

• **obj**: `any`

• **objId?**: `string`

#### Returns

`Promise`\<`ObjectRef`\>

#### Defined in

[weaveClient.ts:160](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L160)

***

### pushNewCall()

> **pushNewCall**(): `object`

#### Returns

`object`

##### currentCall

> **currentCall**: `CallStackEntry`

##### newStack

> **newStack**: `CallStack`

##### parentCall?

> `optional` **parentCall**: `CallStackEntry`

#### Defined in

[weaveClient.ts:541](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L541)

***

### runWithCallStack()

> **runWithCallStack**\<`T`\>(`callStack`, `fn`): `T`

#### Type Parameters

• **T**

#### Parameters

• **callStack**: `CallStack`

• **fn**

#### Returns

`T`

#### Defined in

[weaveClient.ts:545](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L545)

***

### saveOp()

> **saveOp**(`op`, `objId`?): `Promise`\<`any`\>

#### Parameters

• **op**: [`Op`](../type-aliases/Op.md)\<(...`args`) => `any`\>

• **objId?**: `string`

#### Returns

`Promise`\<`any`\>

#### Defined in

[weaveClient.ts:575](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L575)

***

### waitForBatchProcessing()

> **waitForBatchProcessing**(): `Promise`\<`void`\>

#### Returns

`Promise`\<`void`\>

#### Defined in

[weaveClient.ts:103](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/weaveClient.ts#L103)
