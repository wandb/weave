[**weave**](../README.md)

***

[weave](../README.md) / init

# Function: init()

> **init**(`project`, `settings?`): `Promise`\<[`WeaveClient`](../classes/WeaveClient.md)\>

Defined in: [clientApi.ts:80](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/clientApi.ts#L80)

Initialize the Weave client, which is required for weave tracing to work.

## Parameters

### project

`string`

The W&B project name (can be project or entity/project).

### settings?

`Settings`

(Optional) Weave tracing settings

## Returns

`Promise`\<[`WeaveClient`](../classes/WeaveClient.md)\>

A promise that resolves to the initialized Weave client.

## Throws

If the initialization fails
