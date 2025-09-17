[**weave**](../README.md)

***

[weave](../README.md) / wrapOpenAI

# Function: wrapOpenAI()

> **wrapOpenAI**\<`T`\>(`openai`): `T`

Defined in: [integrations/openai.ts:469](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/integrations/openai.ts#L469)

Wraps the OpenAI API to enable function tracing for OpenAI calls.

## Type Parameters

### T

`T` *extends* `OpenAIAPI`

## Parameters

### openai

`T`

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
