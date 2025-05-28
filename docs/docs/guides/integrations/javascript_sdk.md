This is the JavaScript/TypeScript set up guide especially focus on setting up 3rd party intergrations.

With the rolling out of the stack of PRs from https://github.com/wandb/weave/pull/4554

User no longer has to manually do `weave.wrapOpenAI(new OpenAI());`, OpenAI library will be automatically patched.

For a CommonJS project, they don't need any special set up. The auto-patching will work out of the box.
For a ESM project, a user has to do:

```
node --import=weave/instrument dist/main.js
```

`weave/instrument` is a fixed name and it exists as long as user has installed weave npm package.

Please note that whether it will be a form of CommonJS or ESM project is totally user's choice.

The description in https://github.com/wandb/weave/pull/4554 and this doc https://www.notion.so/wandbai/Weave-TypeScrip-SDK-Competitive-Analysis-1eee2f5c7ef38077ac3fe055a6c8d5ba#1fbe2f5c7ef380889219fef69ad285f1
explained the pertinent mechanism. It is for gaining context on writing the docs. The details do not have to be part of the documentation.

In terms of the actual documentation. There are two sources of prior art on explaining these topics:

https://docs.datadoghq.com/tracing/trace_collection/automatic_instrumentation/dd_libraries/nodejs/
https://github.com/getsentry/sentry-javascript/tree/master/packages/node

Some important points we should also cover:

1. The differences in CommonJS and ESM project setup and ways for adotpion.
2. The `NODE_OPTIONS` hatch door to work around the cases a cli arg cannot be easily added. There is a potential drawback that setting the `NODE_OPTIONS` would apply to every `node` executions which might bring in unwanted side effects.
3. In case of CommonJS setup, `require` might be rewritten in the bundling system. So the workaround need to be mentioned, especially for Next JS user base (which is kinda important)
4. In extreme cases, user might need to give up automatic patching and still adopt the old way of manual patching.

Lastly, all the occurences of `weave.wrapOpenAI` should be inspected and check for obsolescence.
