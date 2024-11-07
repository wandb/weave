[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / op

# Function: op()

## op(fn, options)

> **op**\<`T`\>(`fn`, `options`?): [`Op`](../type-aliases/Op.md)\<(...`args`) => `Promise`\<`Awaited`\<`ReturnType`\<`T`\>\>\>\>

A wrapper to weave op-ify a function or method that works on sync and async functions.

Wrapped functions:
 1. Take the same inputs and return the same outputs as the original function.
 2. Will automatically track calls in the Weave UI.

If you don't call `weave.init` then the function will behave as if it were not wrapped.

### Type Parameters

• **T** *extends* (...`args`) => `any`

### Parameters

• **fn**: `T`

The function to wrap

• **options?**: `OpOptions`\<`T`\>

Optional configs like call and param naming

### Returns

[`Op`](../type-aliases/Op.md)\<(...`args`) => `Promise`\<`Awaited`\<`ReturnType`\<`T`\>\>\>\>

The wrapped function

### Example

```ts
// Basic usage
import OpenAI from 'openai';
import * as weave from 'weave';

const client = await weave.init({ project: 'my-project' });
const oaiClient = weave.wrapOpenAI(new OpenAI());

const extract = weave.op(async function extract() {
  return await oaiClient.chat.completions.create({
    model: 'gpt-4-turbo',
    messages: [{ role: 'user', content: 'Create a user as JSON' }],
  });
});

await extract();

// You can also wrap methods by passing the object as the first argument.
// This will bind the method to the object and wrap it with op.
class MyModel {
  private oaiClient: OpenAI;

  constructor() {
    this.oaiClient = weave.wrapOpenAI(new OpenAI());
    this.invoke = weave.op(this, this.invoke);
  }

  async invoke() {
    return await this.oaiClient.chat.completions.create({
      model: 'gpt-4-turbo',
      messages: [{ role: 'user', content: 'Create a user as JSON' }],
    });
  }
}

const model = new MyModel();
const res = await model.invoke();
```

### Defined in

[op.ts:58](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/op.ts#L58)

## op(thisArg, fn, options)

> **op**\<`T`\>(`thisArg`, `fn`, `options`?): [`Op`](../type-aliases/Op.md)\<(...`args`) => `Promise`\<`Awaited`\<`ReturnType`\<`T`\>\>\>\>

### Type Parameters

• **T** *extends* (...`args`) => `any`

### Parameters

• **thisArg**: `any`

• **fn**: `T`

• **options?**: `OpOptions`\<`T`\>

### Returns

[`Op`](../type-aliases/Op.md)\<(...`args`) => `Promise`\<`Awaited`\<`ReturnType`\<`T`\>\>\>\>

### Defined in

[op.ts:62](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/op.ts#L62)
