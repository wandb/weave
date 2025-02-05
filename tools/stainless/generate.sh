TOOL_PATH=./tools/stainless
PYTHON_PATH=~/repos/weave-stainless

node $TOOL_PATH/stainless.js \
    --org-name weights-biases \
    --project-name weave \
    --config-path $TOOL_PATH/openapi.stainless.yml \
    --oas-path $TOOL_PATH/openapi.json \
    --output-python $PYTHON_PATH
# --output-node $TOOL_PATH/generated/node
