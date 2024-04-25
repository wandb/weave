# Weave Grammar

`grammar.js` defines a tree-sitter grammar for weave expression language. `web-tree-sitter` creates `wasm` bindings so we can run tree-sitter in the browser!

You'll need to run `yarn install` in this directory to install the tree-sitter CLI. At time of writing, the CLI is not available for ARM Linux.

### TODO

- [ ] Consolidate tree-sitter-related source files and properly encapsulate this dependency

# Regenerate files

## Script

The steps described below can be run via `yarn generate` in this directory.

## Manually

Almost everything in this directory is the output of `tree-sitter generate`:

```
tree-sitter generate
```

This yields a bunch of intermediate files. Then we need to use `web-tree-sitter` to create a `wasm` binding:

```
npx tree-sitter build-wasm .
```

HACK: For now, we need to copy the result (`tree-sitter-weave.wasm`) to the parent directory:

```
frontends/app/weave/src/core/language/js/parser/tree-sitter-weave.wasm
```
