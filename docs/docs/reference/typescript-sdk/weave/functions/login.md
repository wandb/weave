[**weave**](../README.md)

***

[weave](../README.md) / login

# Function: login()

> **login**(`apiKey`, `host?`): `Promise`\<`void`\>

Defined in: [clientApi.ts:23](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/clientApi.ts#L23)

Log in to Weights & Biases (W&B) using the provided API key.
This function attempts to save the credentials to your netrc file for future use,
but will continue even if it cannot write to the file system.

## Parameters

### apiKey

`string`

Your W&B API key.

### host?

`string`

(Optional) The host name (usually only needed if you're using a custom W&B server).

## Returns

`Promise`\<`void`\>

## Throws

If the API key is not specified or if the connection to the weave trace server cannot be verified.
