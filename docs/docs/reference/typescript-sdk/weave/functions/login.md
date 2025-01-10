[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / login

# Function: login()

> **login**(`apiKey`, `host`?): `Promise`\<`void`\>

Log in to Weights & Biases (W&B) using the provided API key.
This function saves the credentials to your netrc file for future use.

## Parameters

• **apiKey**: `string`

Your W&B API key.

• **host?**: `string` = `defaultHost`

(Optional) The host name (usually only needed if you're using a custom W&B server).

## Returns

`Promise`\<`void`\>

## Throws

If the API key is not specified or if the connection to the weave trace server cannot be verified.

## Defined in

[clientApi.ts:22](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/clientApi.ts#L22)
