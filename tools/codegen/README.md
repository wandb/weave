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

## Commands

- **get-openapi-spec**: Starts a temporary server to fetch and save the OpenAPI spec.
- **generate-code**: Generates client code using Stainless. You can specify the path for code generation for each language.
- **update-pyproject**: Updates pyproject.toml with either the generated git SHA (normal dev) or the published pypi version (release).
- **all**: Runs the full pipeline. Configuration can be provided via a YAML file (default: tools/codegen/generate_config.yaml).

## Usage

For help, run:

```
codegen --help
```

To run the full pipeline:

```bash
codegen all
```

## Troubleshooting

- Ensure port 6345 is free if the server doesn't start.
- Verify that all required environment variables are set.
