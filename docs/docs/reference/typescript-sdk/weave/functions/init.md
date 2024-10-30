[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / init

# Function: init()

> **init**(`project`, `settings`?): `Promise`\<[`WeaveClient`](../classes/WeaveClient.md)\>

Initialize the Weave client, which is required for weave tracing to work.

## Parameters

• **project**: `string`

The W&B project name (can be project or entity/project).

• **settings?**: `Settings`

(Optional) Weave tracing settings

## Returns

`Promise`\<[`WeaveClient`](../classes/WeaveClient.md)\>

A promise that resolves to the initialized Weave client.

## Throws

If the initialization fails

## Defined in

[clientApi.ts:57](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/clientApi.ts#L57)
