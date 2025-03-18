# Weave SDK Code Generator

This tool generates code from the OpenAPI specification for Python, Node.js, and TypeScript using Stainless.

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

## Commands / ARGS

Note: If you run `make generate-bindings` from the weave root directory as suggested below, you'll need to pass the commands as with `ARGS=`, for example `ARGS="all"`. See more below.

- **get-openapi-spec**: Starts a temporary server to fetch and save the OpenAPI spec.
- **generate-code**: Generates client code using Stainless. You can specify the path for code generation for each language.
- **update-pyproject**: Updates pyproject.toml with either the generated git SHA (normal dev) or the published pypi version (release).
- **all**: Runs the full pipeline. Configuration can be provided via a YAML file (default: tools/codegen/generate_config.yaml).

## Usage

For help, run (from the weave root directory):

```
make generate-bindings ARGS="--help"
```

To run the full pipeline:

```bash
make generate-bindings ARGS="all"
```

## Stainless configuration

In general, you won't need to change the Stainless configuration located at `tools/codegen/openapi.stainless.yml`. This file configures how Stainless will generate code, including options for different languages, security settings, etc.

In the unlikely event that you need to change the configuration, it will probably be to add or remove an endpoint from generation. To do this, navigate to the `resources` key of the config. There, you'll see a list of resources we have like `calls`, `objects`, etc. If you want to manually add or remove a method, you can directly edit the relevant section. For example, you can comment out `calls/methods/start` to remove the `call_start` method from generated clients. You can also add new sections or endpoints entirely.

## Adding new endpoints (TODO)

## Troubleshooting

- Ensure port 6345 is free if the server doesn't start.
- Verify that all required environment variables are set.
