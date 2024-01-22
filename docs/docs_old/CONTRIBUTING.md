# Weave Contribution Guide

---

Hello, fellow coder! 👋

First off, thank you for considering contributing to Weave, the performant, interactive data exploration toolkit by Weights and Biases. Open-source projects like Weave thrive because of contributors like you. This document aims to provide you with all the necessary information to make the contribution process smooth and efficient.

## Quicklinks

- [Getting Started](#getting-started)
- [Development](#development)
- [How Can I Contribute?](#how-can-i-contribute)
- [Creating a Pull Request](#creating-a-pull-request)
- [Creating an Issue](#creating-an-issue)

---

## Getting Started

Before you can contribute to Weave, you'll need to fork the repository and clone it to your local machine. For more details, please refer to the GitHub documentation on [Forking](https://docs.github.com/en/github/getting-started-with-github/fork-a-repo) and [Cloning](https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/cloning-a-repository) a repository.

## Development

### Setup instructions

First, setup your python environment:

```
pyenv install 3.9.7
pyenv virtualenv 3.9.7 weave_dev
pyenv local weave_dev
pip install -e .
pip install -r requirements.dev.txt
pre-commit install
```

Next, install node dependencies to run the frontend

```
cd weave-js && yarn install
```

Finally, if you are working on any integrations with Weights and Biases, you will want to be logged in on your machine. Do so with

```
wandb init
```

### Active Development

In order to develop against Weave, you will want 3 terminal sessions:

1. `cd weave-js && yarn dev`: This will start a local server serving the frontend application (rendered in the notebook iframe)
2. `./weave_server.sh`: This will start an in-process server running the weave execution engine
3. `jupyter notebook`: This will start a notebook server - useful for interacting with your code!
   - note: you will want to use `weave.use_frontend_devmode()` at the top of development notebooks to ensure you hit the frontend server.

### Testing & Style

Style and lint is enforced using pre-commit hooks. All tests can be run via `cd weave && pytest`

### Notebook Style & Tests

To successfully commit a Jupyter notebook:
* make sure the notebook runs end-to-end-locally
* make sure there is no empty cell at the end of the notebook (remove it if it appeared)
* merge any sequences of consecutive markdown/non-code cells into a single markdown cell
* reset kernel and clear output
* then save the notebook and commit

## How Can I Contribute?

There are many ways you can contribute to Weave, from writing code and fixing bugs, to improving documentation, to submitting bug reports and feature requests. No contribution is too small – we appreciate them all!

## Creating a Pull Request

Ready to make a pull request (PR)? Great! Here's a step-by-step guide:

1. Fork the Weave repository and clone it to your local machine.
2. Create a new branch for your feature or bugfix. Use a descriptive name, such as `add-feature-x` or `fix-bug-y`.
3. After you've made your changes, push them to your fork.
4. Head over to the Weave repository on GitHub and click the 'New Pull Request' button.
5. Choose your fork and the branch you created as the source of the PR.
6. Provide a brief description of the changes you've made. If your PR closes an existing issue, include the text `closes #ISSUE_NUMBER`.
7. Submit your PR. Our team will review it as soon as possible.

## Creating an Issue

Found a bug 🐞? Or have an idea for a new feature 💡? We'd love to hear about it! Here's how to create an issue:

1. Go to the [Issue Tracker](issue_tracker_link) on our GitHub page.
2. Click the 'New Issue' button.
3. Provide a descriptive title that summarizes the issue.
4. In the body of the issue, provide as much detail as possible. If you're reporting a bug, include steps to reproduce it, and any error messages you've seen. If you're suggesting a new feature, explain your idea in detail.
5. Submit the issue. We'll respond as soon as we can.

---

Thanks again for your interest in contributing to Weave. We're excited to see what you bring to our community!

Happy coding! 🚀
