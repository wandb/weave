# Contributing to Weave Documentation

Thanks for contributing to Weave Docs 💛! 

## Contribution guidelines

- Ensure tone and style is consistent with existing documentation.
- Update the `sidebar.ts` file if you add new pages.
- **Always run** `make docs` before submitting a PR to ensure all auto-generated docs are fresh.

## Setup

Set up your environment to build and serve the Weave documentation locally:

1. (Recommended) Install [`nvm`](https://github.com/nvm-sh/nvm) to manage Node.js versions.
2. Install [Node.js](https://nodejs.org/en/download/) version 18.0.0.
    ```bash
    nvm install 18.0.0
    ```
3. Install Yarn:
    ```bash
    npm install --global yarn
    ```
4. Set up your Python environment:
    ```bash
    pip install -r requirements.dev.txt
    pip install -e .
    ```
5. Install Playwright:
    ```bash
    playwright install
    ```
6. Build and run the docs locally:
    ```bash
    cd docs
    yarn install
    yarn start
    ```

In successful `yarn start` output, you'll see a port number where you can preview your changes.

## How to edit the docs locally

1. Navigate to your local `weave` repo and pull the latest changes:
   ```bash
   cd docs
   git pull origin master
   ```
2. Create a feature branch off `master`:
   ```bash
   git checkout -b <your-feature-branch>
   ```
3. Start a local preview:
   ```bash
   yarn start
   ```
4. Preview and review your changes in the docs UI. 
5. Run `make docs` to regenerate API and notebook docs. 

    > Our CI builds and deploys the current state of the documentation but does not automatically regenerate API or notebook docs. If you skip `make docs`, stale or missing docs might be deployed. For more information, see [`make docs`](#make-docs).

6. Commit the changes:
   ```bash
   git commit -m 'chore(docs): Useful commit message.'
   ```
7. Push your branch:
   ```bash
   git push origin <your-feature-branch>
   ```
8. Open a pull request to the Weave repository.
9. A Weave team member will review your pull request and either approve, deny, or request changes / more information.

## `make docs`

The `make docs` command will:

- Generate fresh API reference docs (Python and TypeScript).
- Convert notebooks into Markdown docs.
- Build the docs locally to catch issues.

When to run `make docs`:

- On any Python, Service, SDK, or docs-related changes.
- Always run before opening a documentation pull request.

## Doc generation details

### Python SDK doc generation

- Script: `docs/scripts/generate_python_sdk_docs.py`
- Output: `docs/reference/python-sdk`
- Uses `lazydocs`.

> Tip: Add triple-quoted (`"""`) docstrings to modules, classes, and functions.

### Service doc generation

- Script: `docs/scripts/generate_service_api_spec.py`
- Output: `docs/reference/service-api`
- Based on `openapi.json` and FastAPI docs.

### Notebook doc generation

- Script: `docs/scripts/generate_notebooks.py`
- Converts `.ipynb` files from `docs/notebooks` to Markdown in `docs/reference/gen_notebooks`.

You can convert a single notebook:

```bash
python docs/scripts/generate_notebooks.py path/to/your_notebook.ipynb
```

To add Docusaurus metadata to a notebook, include:

```markdown
<!-- docusaurus_head_meta::start
---
title: My Notebook Title
---
docusaurus_head_meta::end -->
```

### Playground model list sync

The model list in [`playground.md`](https://weave-docs.wandb.ai/guides/tools/playground#select-an-llm) is updated by running:

```bash
make update_playground_models
```

This regenerates the model list section automatically.
