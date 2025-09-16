cd ../sdks/node
# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi
npx typedoc src/index.ts \
    --plugin typedoc-plugin-markdown \
    --out ../../docs/docs/reference/typescript-sdk/weave/ \
    --readme none
