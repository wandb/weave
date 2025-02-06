import os
import subprocess

TOOL_PATH = "./tools/stainless"
ORG_NAME = "weights-biases"
PROJECT_NAME = "weave"

CONFIG_PATH = f"{TOOL_PATH}/openapi.stainless.yml"
OAS_PATH = f"{TOOL_PATH}/openapi.json"
PYTHON_OUTPUT_PATH = os.path.expanduser("~/repos/weave-stainless")
NODE_OUTPUT_PATH = os.path.expanduser("~/repos/weave-stainless-node")
TYPESCRIPT_OUTPUT_PATH = os.path.expanduser("~/repos/weave-stainless-typescript")

# Construct the command
cmd = [
    "node",
    f"{TOOL_PATH}/stainless.js",
    f"--org-name={ORG_NAME}",
    f"--project-name={PROJECT_NAME}",
    f"--config-path={CONFIG_PATH}",
    f"--oas-path={OAS_PATH}",
    f"--output-python={PYTHON_OUTPUT_PATH}",
    f"--output-node={NODE_OUTPUT_PATH}",
    # f"--output-typescript={TYPESCRIPT_OUTPUT_PATH}",
]

# Execute the command
subprocess.run(cmd, check=True)
