# Weave SDK Code Generator

This tool generates code from the OpenAPI specification for Python, Node.js, and TypeScript using Stainless.

## Quick Start

The simplest way to generate code:

```bash
make generate-bindings
```

This single command will:

1. Retrieve the OpenAPI specification from a temporary FastAPI server
2. Generate Python code using Stainless
3. Create a git branch with the generated code
4. Update `pyproject.toml` with the git SHA reference

The CLI uses a configuration file (`tools/codegen/generate_config.yaml`) and focuses on correctness and simplicity.

## Setup

1. Install weave locally:

   ```
   uv pip install -e .
   ```

2. Set the required environment variables:

   - `STAINLESS_API_KEY`
   - `GITHUB_TOKEN`

3. Configure your local paths:

   ```bash
   # Copy the template configuration file
   cp tools/codegen/generate_config.yaml.template tools/codegen/generate_config.yaml

   # Edit generate_config.yaml with your local repository paths
   ```

   Note: Your local `generate_config.yaml` will be ignored by git to prevent checking in personal paths.

4. Install Stainless CLI:

   ```bash
   brew install stainless-api/tap/stl
   ```

## Usage

The CLI (`generate.py`) provides a single command that handles the entire workflow:

```bash
# Using make (recommended)
make generate-bindings

# Or directly
uv run tools/codegen/generate.py

# With custom config file
uv run tools/codegen/generate.py --config /path/to/config.yaml
```

The CLI:

- Generates Python code (optionally supports Node.js and TypeScript)
- Uses a config file for all settings
- Ensures generated code exists on a referenceable git branch/SHA
- Provides clear error messages and validation
- No interactive prompts - fails fast if configuration is missing
- Automatically sets upstream tracking when pushing branches

## Stainless configuration

In general, you won't need to change the Stainless configuration located at `tools/codegen/openapi.stainless.yml`. This file configures how Stainless will generate code, including options for different languages, security settings, etc.

In the unlikely event that you need to change the configuration, it will probably be to add or remove an endpoint from generation. To do this, navigate to the `resources` key of the config. There, you'll see a list of resources we have like `calls`, `objects`, etc. If you want to manually add or remove a method, you can directly edit the relevant section. For example, you can comment out `calls/methods/start` to remove the `call_start` method from generated clients. You can also add new sections or endpoints entirely.

## Adding new endpoints (TODO)

## Troubleshooting

- Ensure port 6345 is free if the server doesn't start.
- Verify that all required environment variables are set.
