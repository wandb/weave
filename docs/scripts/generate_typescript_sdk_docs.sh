cd ../sdks/node
# Install dependencies if node_modules doesn't exist
pnpm typedoc src/index.ts \
    --plugin typedoc-plugin-markdown \
    --out ../../docs/docs/reference/typescript-sdk/weave/ \
    --readme none
