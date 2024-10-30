[**weave**](../README.md) • **Docs**

***

[weave](../globals.md) / wrapOpenAI

# Function: wrapOpenAI()

> **wrapOpenAI**\<`T`\>(`openai`): `T`

Wraps the OpenAI API to enable function tracing for OpenAI calls.

## Type Parameters

• **T** *extends* `OpenAIAPI`

## Parameters

• **openai**: `T`

## Returns

`T`

## Example

```ts
const openai = wrapOpenAI(new OpenAI());
const result = await openai.chat.completions.create({
  model: 'gpt-3.5-turbo',
  messages: [{ role: 'user', content: 'Hello, world!' }]
});
```

## Defined in

[integrations/openai.ts:159](https://github.com/wandb/weave/blob/f0de86a1943f1d5c6c828f42faab64acc924c307/sdks/node/src/integrations/openai.ts#L159)
