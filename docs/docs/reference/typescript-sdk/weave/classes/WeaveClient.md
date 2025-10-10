[**weave**](../README.md)

***

[weave](../README.md) / WeaveClient

# Class: WeaveClient

Defined in: [weaveClient.ts:81](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L81)

## Constructors

### Constructor

> **new WeaveClient**(`traceServerApi`, `wandbServerApi`, `projectId`, `settings`): `WeaveClient`

Defined in: [weaveClient.ts:91](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L91)

#### Parameters

##### traceServerApi

`Api`\<`any`\>

##### wandbServerApi

`WandbServerApi`

##### projectId

`string`

##### settings

`Settings` = `...`

#### Returns

`WeaveClient`

## Properties

### projectId

> **projectId**: `string`

Defined in: [weaveClient.ts:94](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L94)

***

### settings

> **settings**: `Settings`

Defined in: [weaveClient.ts:95](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L95)

***

### traceServerApi

> **traceServerApi**: `Api`\<`any`\>

Defined in: [weaveClient.ts:92](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L92)

## Methods

### createCall()

> **createCall**(`internalCall`, `opRef`, `params`, `parameterNames`, `thisArg`, `currentCall`, `parentCall`, `startTime`, `displayName?`): `Promise`\<`void`\>

Defined in: [weaveClient.ts:700](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L700)

#### Parameters

##### internalCall

`InternalCall`

##### opRef

`any`

##### params

`any`[]

##### parameterNames

`ParameterNamesOption`

##### thisArg

`any`

##### currentCall

`CallStackEntry`

##### parentCall

`undefined` | `CallStackEntry`

##### startTime

`Date`

##### displayName?

`string`

#### Returns

`Promise`\<`void`\>

***

### finishCall()

> **finishCall**(`call`, `result`, `currentCall`, `parentCall`, `summarize`, `endTime`, `startCallPromise`): `Promise`\<`void`\>

Defined in: [weaveClient.ts:741](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L741)

#### Parameters

##### call

`InternalCall`

##### result

`any`

##### currentCall

`CallStackEntry`

##### parentCall

`undefined` | `CallStackEntry`

##### summarize

`undefined` | (`result`) => `Record`\<`string`, `any`\>

##### endTime

`Date`

##### startCallPromise

`Promise`\<`void`\>

#### Returns

`Promise`\<`void`\>

***

### finishCallWithException()

> **finishCallWithException**(`call`, `error`, `currentCall`, `parentCall`, `endTime`, `startCallPromise`): `Promise`\<`void`\>

Defined in: [weaveClient.ts:781](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L781)

#### Parameters

##### call

`InternalCall`

##### error

`any`

##### currentCall

`CallStackEntry`

##### parentCall

`undefined` | `CallStackEntry`

##### endTime

`Date`

##### startCallPromise

`Promise`\<`void`\>

#### Returns

`Promise`\<`void`\>

***

### get()

> **get**(`ref`): `Promise`\<`any`\>

Defined in: [weaveClient.ts:280](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L280)

#### Parameters

##### ref

`ObjectRef`

#### Returns

`Promise`\<`any`\>

***

### getCall()

> **getCall**(`callId`, `includeCosts`): `Promise`\<`Call`\>

Defined in: [weaveClient.ts:211](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L211)

#### Parameters

##### callId

`string`

##### includeCosts

`boolean` = `false`

#### Returns

`Promise`\<`Call`\>

***

### getCalls()

> **getCalls**(`filter`, `includeCosts`, `limit`): `Promise`\<`Call`[]\>

Defined in: [weaveClient.ts:221](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L221)

#### Parameters

##### filter

[`CallsFilter`](../interfaces/CallsFilter.md) = `{}`

##### includeCosts

`boolean` = `false`

##### limit

`number` = `1000`

#### Returns

`Promise`\<`Call`[]\>

***

### getCallsIterator()

> **getCallsIterator**(`filter`, `includeCosts`, `limit`): `AsyncIterableIterator`\<[`CallSchema`](../interfaces/CallSchema.md)\>

Defined in: [weaveClient.ts:235](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L235)

#### Parameters

##### filter

[`CallsFilter`](../interfaces/CallsFilter.md) = `{}`

##### includeCosts

`boolean` = `false`

##### limit

`number` = `1000`

#### Returns

`AsyncIterableIterator`\<[`CallSchema`](../interfaces/CallSchema.md)\>

***

### getCallStack()

> **getCallStack**(): `CallStack`

Defined in: [weaveClient.ts:628](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L628)

#### Returns

`CallStack`

***

### publish()

> **publish**(`obj`, `objId?`): `Promise`\<`ObjectRef`\>

Defined in: [weaveClient.ts:199](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L199)

#### Parameters

##### obj

`any`

##### objId?

`string`

#### Returns

`Promise`\<`ObjectRef`\>

***

### pushNewCall()

> **pushNewCall**(): `object`

Defined in: [weaveClient.ts:632](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L632)

#### Returns

`object`

##### currentCall

> **currentCall**: `CallStackEntry`

##### newStack

> **newStack**: `CallStack`

##### parentCall?

> `optional` **parentCall**: `CallStackEntry`

***

### runWithCallStack()

> **runWithCallStack**\<`T`\>(`callStack`, `fn`): `T`

Defined in: [weaveClient.ts:636](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L636)

#### Type Parameters

##### T

`T`

#### Parameters

##### callStack

`CallStack`

##### fn

() => `T`

#### Returns

`T`

***

### saveOp()

> **saveOp**(`op`, `objId?`): `Promise`\<`any`\>

Defined in: [weaveClient.ts:666](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L666)

#### Parameters

##### op

[`Op`](../type-aliases/Op.md)\<(...`args`) => `any`\>

##### objId?

`string`

#### Returns

`Promise`\<`any`\>

***

### updateCall()

> **updateCall**(`callId`, `displayName`): `Promise`\<`void`\>

Defined in: [weaveClient.ts:817](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L817)

#### Parameters

##### callId

`string`

##### displayName

`string`

#### Returns

`Promise`\<`void`\>

***

### waitForBatchProcessing()

> **waitForBatchProcessing**(): `Promise`\<`void`\>

Defined in: [weaveClient.ts:112](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/weaveClient.ts#L112)

#### Returns

`Promise`\<`void`\>
