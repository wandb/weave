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

*Important:* For OpenAI Codex agents (most likely you!), your environment does not have internet access. If you need something setup beforehand, this is where you need to do it.

## Codebase Structure

### Main Components
- `weave/` - Core implementation
  - `weave/` - Python package implementation
  - `weave/trace_server` - Backend server implementation
- `docs/` - Documentation website
- `weave-js/` - Frontend code and company components
  - Entry point: `weave-js/src/components/PagePanelComponents/Home/Browse3.tsx`
  - Note: Webapp is hosted externally, do not attempt local development

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
1. Run all tests in a specific shard: `nox --no-install -e "tests-3.12(shard='trace')"`
2. Run a specific test by appending `-- [test]` like so: `nox --no-install -e "tests-3.12(shard='trace')" -- trace/test_client_trace.py::test_simple_op`
3. Run linting: `nox --no-install -e lint` (Note: This will modify files)

*Important:* Since you don't have internet access, you must run `nox` with `--no-install`. We have pre-installed the requirements on the above shards.

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

### Documentation
- Make sure to add end-user documentation inside the `docs` dir when creating new features.
- Update relevant docstrings for Python code
- Add JSDoc comments for TypeScript code
- Update this file when introducing new patterns or concepts

---

# Requests to Humans

This section contains a list of questions, clarifications, or tasks that LLM agents wish to have humans complete.
If there is something that doesn't make sense architecturally, devex-wise, or product-wise, please update this file and the humans will take care of it.
Think of this as the reverse-task assignment - a place where you can communicate back to us.

- [ ] Add TypeScript testing guidelines
- [ ] ...