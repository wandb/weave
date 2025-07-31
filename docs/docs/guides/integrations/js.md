# TypeScript SDK: Third-Party Integration Guide

This guide describes how to integrate third-party libraries (e.g., OpenAI) with the Weave TypeScript SDK. Weave supports automatic instrumentation, making setup easier and reducing the need for manual configuration.

:::important What changed?
As of [PR #4554](https://github.com/wandb/weave/pull/4554), supported libraries such as OpenAI are automatically patched when Weave is loaded. You no longer need to manually wrap them, as was the case previously:

```ts
weave.wrapOpenAI(new OpenAI());
```

Weave will generally handle this automatically. However, there may be [edge cases](#advanced-usage).
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

## Advanced usage and troubleshooting

This section covers edge cases and workarounds for when the TypeScript SDK's automatic patching doesn’t work as expected. For example, ESM-only environments, bundler setups like Next.js, or constrained runtime environments may cause unexpected issues. If you're seeing missing traces or integration issues, start here.

### Use `NODE_OPTIONS` (only for ESM)

:::warning
Use with `NODE_OPTIONS` with caution, as this affects all Node.js processes in the environment and may introduce side effects.
:::

If you're using an ESM project and cannot pass CLI flags (e.g., due to constraints in CLI tools or frameworks), set the `NODE_OPTIONS` environment variable:

```bash
export NODE_OPTIONS="--import=weave/instrument"
```


### Bundler compatibility (e.g., Next.js)

Some frameworks and bundlers, such as Next.js, may bundle third-party libraries in ways that break Node’s ability to patch them at runtime.

If this describes your setup, try the following steps:

1. Mark LLM libraries as external in your bundler configuration. This prevents them from being bundled, so Weave can patch them correctly at runtime.

   The following example shows how to mark the `openai` package as external in a `next.config.js` configuration, which prevents it from being bundled. The module is loaded at runtime, so Weave can automatically patch and track it. Use this setup when working with frameworks like Next.js to enable auto-instrumentation.

    ```js
    externals: {
    'openai': 'commonjs openai'
    }
    ```


2. If patching still fails, fall back to [manual instrumentation](#manual-patching-fallback-option).


### Manual patching (fallback option)

:::important
Manual patching is the legacy approach and should only be used when auto-patching doesn't work.
:::

In some cases, you may still need to use manual instrumentation:

```ts
import { wrapOpenAI } from 'weave';
const client = wrapOpenAI(new OpenAI());
```
