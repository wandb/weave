# Contributing to Weave Documentation

## Guidelines
- Ensure tone and style is consistent with existing documentation.
- Ensure that the `sidebar.ts` file is updated if adding new pages

## Installation 
Satisfy the following dependencies to create, build, and locally serve Weave Docs on your local machine:


- (Recommended) Install [`nvm`](https://github.com/nvm-sh/nvm) to manage your node.js versions.
- Install [Node.js](https://nodejs.org/en/download/) version 18.0.0.
  ```node
  nvm install 18.0.0
  ```
- Install Yarn. It is recommended to install Yarn through the [npm package manager](http://npmjs.org/), which comes bundled with [Node.js](https://nodejs.org/) when you install it on your system.
  ```yarn
  npm install --global yarn
  ```
- Install an IDE (e.g. VS Studio) or Text Editor (e.g. Sublime)

&nbsp;

Build and run the docs locally to test that all edits, links etc are working. After you have forked and cloned wandb/weave:

```
cd docs

yarn install
```

Then test that you can build and run the docs locally:

```
yarn start
```

This will return the port number where you can preview your changes to the docs.

## How to edit the docs locally

1. Navigate to your local GitHub repo of `weave` and pull the latest changes from master:

```bash
cd docs
git pull origin main
```

2. Create a feature branch off of `main`.

```bash
git checkout -b <your-feature-branch>
```

3. In a new terminal, start a local preview of the docs with `yarn start`.

```bash
yarn start
```

This will return the port number where you can preview your changes to the docs.

4. Make your changes on the new branch.
5. Check your changes are rendered correctly.

6. Commit the changes to the branch.

```bash
git commit -m 'chore(docs): Useful commit message.'
```

7. Push the branch to GitHub.

```bash
git push origin <your-feature-branch>
```

8. Open a pull request from the new branch to the original repo.
