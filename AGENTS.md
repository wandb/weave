# Agent instructions for `weave` repository

## Core Rules

- When you learn something new about the codebase or introduce a new concept, update this file (`AGENTS.md`) to reflect the new knowledge. This is YOUR FILE! It should grow and evolve with you.
- If there is something that doesn't make sense architecturally, devex-wise, or product-wise, please update the `Requests to Humans` section below.
- Always follow the established coding patterns and conventions in the codebase.
- Document any significant architectural decisions or changes.

## Development Setup

- Your machine should be setup for you automatically via `bin/codex_setup.sh`
- If you encounter any setup issues:
  1. Check the setup script for potential problems
  2. Update `bin/codex_setup.sh` with necessary fixes
  3. Document any manual steps required in this section

_Important:_ For OpenAI Codex agents (most likely you!), your environment does not have internet access. If you need something setup beforehand, this is where you need to do it.

## Codebase Structure

### Main Components

- `weave/` - Core implementation
  - `weave/` - Python package implementation
  - `weave/trace_server` - Backend server implementation

### Legacy Code

- `weave_query/` - Legacy codebase (DO NOT EDIT)
  - Marked for future refactoring
  - Avoid making changes to this directory

## Python Testing Guidelines

### Test Framework

- Testing is managed by `nox` with multiple shards for different Python versions
- Each shard represents specific package configurations

### Key Test Shards

Focus on these primary test shards:

- `tests-3.12(shard='trace')` - Core tracing functionality
- `tests-3.12(shard='flow')` - Higher level work"flow" objects
- `tests-3.12(shard='trace_server')` - Server implementation
- `tests-3.12(shard='trace_server_bindings')` - Server bindings

### Running Tests

**IMPORTANT**: Any test depending on the `client` fixture runs against either SQLite backend or Clickhouse. By default it will run against SQLite for performance. However, it is critical to test both. Use the pytest custom flag `--trace-server=clickhouse` with `--clickhouse-process=true` to run tests against the clickhouse implementation.

1. Run all tests in a specific shard: `nox --no-install -e "tests-3.12(shard='trace')"`
2. Run a specific test by appending `-- [test]` like so: `nox --no-install -e "tests-3.12(shard='trace')" -- trace/test_client_trace.py::test_simple_op`
3. Run linting: `nox --no-install -e lint` (Note: This will modify files)

_Important:_ Since you don't have internet access, you must run `nox` with `--no-install`. We have pre-installed the requirements on the above shards.

Therefore, a basic text command would look like: `nox --no-install -e "tests-3.12(shard='trace')" -- trace/test_client_trace.py::test_simple_op --trace-server=clickhouse --clickhouse-process=true`

## Typescript Testing Guidelines

TODO: need to fill this out

## Code Review & PR Guidelines

### PR Requirements

- Title format: Must start with one of:
  - `chore(weave):` - For maintenance tasks
  - `feat(weave):` - For new features
  - `fix(weave):` - For bug fixes
- Provide detailed PR summaries including:
  - Purpose of changes
  - Testing performed
  - Any breaking changes
  - Related issues/PRs

### Pre-commit Checklist

1. Run lint
2. Ensure all tests pass
3. Update documentation if needed
4. Check for any breaking changes

## Common Development Patterns

### Code Organization

- Python code follows standard module organization
- TypeScript/React components are organized by feature
- Shared utilities should be placed in appropriate common directories

### Error Handling

- Use appropriate error types from `weave.errors`
- Include meaningful error messages
- Add error handling tests

### Integration Testing

- Since autopatching was removed from `weave.init()`, integration tests must explicitly patch their integrations
- Add a fixture with `autouse=True` at the top of each integration test file to enable patching
- Example pattern:
  ```python
  @pytest.fixture(autouse=True)
  def patch_integration() -> Generator[None, None, None]:
      patcher = get_integration_patcher()
      patcher.attempt_patch()
      yield
      patcher.undo_patch()
  ```
- Some integrations (like instructor) may need to patch multiple libraries

### Documentation

- Update relevant docstrings for Python code
- Add JSDoc comments for TypeScript code
- Update this file when introducing new patterns or concepts

---

## Integration Patching

### Automatic Implicit Patching

Weave provides automatic implicit patching for all supported integrations using an import hook mechanism:

- **Automatic Patching**: Libraries are automatically patched regardless of when they are imported
- **Import Hook**: An import hook intercepts library imports and applies patches automatically
- **Explicit Patching**: Optional manual patching is still available for fine-grained control

Example:

```python
# Automatic patching - works regardless of import order!

# Option 1: Import before weave.init()
import openai
import weave
weave.init('my-project')  # OpenAI is automatically patched!

# Option 2: Import after weave.init()
import weave
weave.init('my-project')
import anthropic  # Automatically patched via import hook!

# Option 3: Explicit patching (optional)
import weave
weave.init('my-project')
weave.patch_openai()  # Manually patch if needed
```

### Available Patch Functions

All integrations have corresponding patch functions for explicit control: `patch_openai()`, `patch_anthropic()`, `patch_mistral()`, etc.

### Technical Implementation

The import hook uses Python's `sys.meta_path` to intercept imports and automatically apply patches when supported libraries are imported. This ensures seamless integration tracking without requiring users to manage import order or make explicit patch calls.

### Disabling Implicit Patching

If you prefer explicit control over which integrations are patched, you can disable implicit patching:

```python
# Via settings parameter
weave.init('my-project', settings={'implicitly_patch_integrations': False})

# Via environment variable
export WEAVE_IMPLICITLY_PATCH_INTEGRATIONS=false
```

When disabled, you must explicitly call patch functions like `weave.patch_openai()` to enable tracing for integrations.

# Requests to Humans

This section contains a list of questions, clarifications, or tasks that LLM agents wish to have humans complete.
If there is something that doesn't make sense architecturally, devex-wise, or product-wise, please update this file and the humans will take care of it.
Think of this as the reverse-task assignment - a place where you can communicate back to us.

- [ ] Add TypeScript testing guidelines
- [ ] ...
