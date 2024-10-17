# Contributing to `weave`

- [Contributing to `weave`](#contributing-to-weave)
  - [Issues](#issues)
  - [PRs](#prs)
    - [Conventional Commits](#conventional-commits)
      - [Types](#types)
  - [Setting up your environment](#setting-up-your-environment)
    - [Working with the `weave` package](#working-with-the-weave-package)
    - [Linting](#linting)
    - [Building the `weave` package](#building-the-weave-package)
    - [Testing](#testing)
    - [Deprecating features](#deprecating-features)

## Issues
1. Check the [issues](https://github.com/wandb/weave/issues) and [PRs](https://github.com/wandb/weave/pulls) to see if the feature/bug has already been requested/fixed. If not, [open an issue](https://github.com/wandb/weave/issues/new/choose). This helps us keep track of feature requests and bugs!
2. If you're having issues, the best way we can help is when you can share a reproducible example.
   1. In general, it's helpful to use this format:
      ```
      <short description of the issue>
      <link to your project>
      <system info, including weave version, python version, and OS>

      <reproducible code snippet>

      <any other info you think is relevant>
      ```
   2. For SDK issues, a reproducible script like [example_error_script.py](examples/contributing/example_error_script.py) is helpful.  We use `uv` which can run the script with the dependencies included.  If you know the dependencies, you can add them to the script.  [See the `uv` docs for more details](https://docs.astral.sh/uv/guides/scripts/).

## PRs
1. If you are a first-time contributor, welcome! To get started, make a fork and point to the main `weave` repo:
   ```sh
   git clone https://github.com/<your-username>/weave.git
   cd weave
   git remote add upstream https://github.com/wandb/weave.git
   ```
3. Build!
   1. Keep your fork up to date with the main `weave` repo:
      ```sh
      git checkout master
      git pull upstream master
      ```
   2. Create a branch for your changes:
      ```sh
      git checkout -b <your-username>/<your-branch>
      ```
   3. Commit changes to your branch and push:
      ```sh
      git add your_file.py
      git commit -m "feat(integrations): Add new integration for <your-package>"
      git push origin <your-username>/<your-branch>
      ```
   4. Open a PR!

### Conventional Commits

All PR titles should conform to the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) spec. Conventional Commits is a lightweight convention on top of commit messages.

**Structure**

The commit message should be structured as follows:

```jsx
<type>(<scope>): <description>
```

<aside>
⭐ **TLDR:** Every commit that has type `feat` or `fix` is **user-facing**.
If notes are user-facing, please make sure users can clearly understand your commit message.

</aside>

#### Types

Only certain types are permitted.

<aside>
⭐ User-facing notes such as `fix` and `feat` should be written so that a user can clearly understand the changes.
If the feature or fix does not directly impact users, consider using a different type.
Examples can be found in the section below.

</aside>

| Type     | Name             | Description                                                                         | User-facing? |
| -------- | ---------------- | ----------------------------------------------------------------------------------- | ------------ |
| feat     | ✨ Feature       | Changes that add new functionality that directly impacts users                      | Yes          |
| fix      | 🐛 Fix           | Changes that fix existing issues                                                    | Yes          |
| refactor | 💎 Code Refactor | A code change that neither fixes a bug nor adds a new feature                       | No           |
| docs     | 📜 Documentation | Documentation changes only                                                          | Maybe        |
| style    | 💅 Style         | Changes that do not affect the meaning of the code (e.g. linting)                   | Maybe        |
| chore    | ⚙️ Chores        | Changes that do not modify source code (e.g. CI configuration files, build scripts) | No           |
| revert   | ♻️ Reverts       | Reverts a previous commit                                                           | Maybe        |
| security | 🔒 Security      | Security fix/feature                                                                | Maybe        |

## Setting up your environment

We use:

1. [`uv`](<(https://astral.sh/blog/uv)>) for package and env management -- follow the [uv guide to bootstrap an environment](https://docs.astral.sh/uv/getting-started/installation/)
   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. [`nox`](https://nox.thea.codes/en/stable/tutorial.html#installation) for running tests
   ```sh
   uv tool install nox
   ```

### Working with the `weave` package

We recommend installing the package in editable mode:

```sh
uv pip install -e .
```

### Linting

We use pre-commit. You can install with:

```sh
uv tool install pre-commit
```

Then run:

```sh
pre-commit run --hook-stage=pre-push --all-files
```

You can also use the `lint` nox target to run linting.

```sh
nox -e lint
```

### Building the `weave` package

Use `uv`:

```sh
uv build
```

### Testing

We use pytest and nox to run tests. To see a list of test environments:

```sh
nox -l
```

Then to run a specific environment:

```sh
nox -e "$TARGET_ENV"  # e.g. nox -e "tests-3.12(shard='trace')"
```

Tests are split up into shards, which include:

1. `trace` -- all of the trace SDK tests
2. `trace_server` -- tests for trace server backend
3. various integrations, like `openai`, `instructor`, etc -- these envs are isolated to simplify testing

### Deprecating features

`weave` is moving quickly, and sometimes features need to be deprecated.

To deprecate a feature, use the `deprecated` decorator from `weave.trace.util`. This is currently used primarily for renames.

```python
from weave.trace.util import deprecated

@deprecated("new_func_name")
def old_func():
    pass
```
