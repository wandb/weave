## Weave TypeScript SDK: Third-Party Integration Guide

This guide describes how to integrate third-party libraries (e.g., OpenAI) with the Weave TypeScript SDK. Weave supports automatic instrumentation, making setup easier and reducing the need for manual configuration.

:::important What changed?
As of [PR #4554](https://github.com/wandb/weave/pull/4554), supported libraries such as OpenAI are automatically patched when Weave is loaded. You no longer need to manually wrap them, as was the case previously:

```ts
weave.wrapOpenAI(new OpenAI());
```

Weave will handle this automatically, as shown below:
:::

## Usage instructions

You can either use CommonJS and ESM.

### CommonJS 

For CommonJS, no special configuration is required. Automatic patching works out of the box. Simply install Weave:

```bash
npm install weave
```

### ESM 

For ESM, use Node's `--import` flag to enable auto-instrumentation. The `weave/instrument` module is available as long as the `weave` package is installed.

1. Install Weave:
    ```bash
    npm install weave
    ```
2. Import the `weave/instrument` module:
    ```bash
    node --import=weave/instrument dist/main.js
    ```

## Advanced usage

### Use `NODE_OPTIONS` as an alternate hook

:::warning
Setting `export NODE_OPTIONS="--import=weave/instrument"` will affect all Node.js processes and may cause unintended side effects.
:::

If you can't pass `--import` directly (e.g., inside CLI scripts or toolchains), you can use the `NODE_OPTIONS` environment variable:

```bash
export NODE_OPTIONS="--import=weave/instrument"
```

### CommonJS bundler compatibility (e.g., Next.js)

Some bundlers such as Next.js may rewrite `require` statements in ways that interfere with auto-patching. In the case, try the following:

- [Use `NODE_OPTIONS` as a workaround.](#use-node_options-as-an-alternate-hook)
- If needed, fall back to manual patching.

### Manual Patching (Fallback Option)

:::important
Manual patching is the legacy approach and should only be used when auto-patching doesn't work.
:::

In some cases, you may still need to use manual instrumentation:

```ts
import { wrapOpenAI } from 'weave';
const client = wrapOpenAI(new OpenAI());
```
