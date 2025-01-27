cd ../sdks/node
pnpm typedoc src/index.ts \
    --plugin typedoc-plugin-markdown \
    --out ../../docs/docs/reference/typescript-sdk/weave/ \
    --readme none
