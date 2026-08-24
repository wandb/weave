# Vendored packages

## `weave_server_sdk`

The generated Python client for the Weave Trace API. It is generated from the trace server's OpenAPI spec and Stainless config, both of which live in `wandb/core` under `services/weave-trace`, and it is vendored here rather than depended on because it is not published to PyPI. The commented-out `stainless` extra in `pyproject.toml` is what this replaces; do not un-comment it.

Treat the copy as read-only. It is replaced wholesale on every refresh, so a hand edit is lost the next time somebody regenerates. The two exceptions are the places the generated package names itself: `_utils/_resources_proxy.py` imports its own resources module by absolute name on first resource access, and `__init__.py` rewrites the `__module__` of every non-dunder exported symbol on import. Both have to name the vendored path instead, and the vendoring script applies both and fails if either has nothing to apply to.

`weave_server_sdk.origin.json` records the core revision and the hashes of the spec and the config the output was generated from, so a refresh diff can be checked against them. To refresh the copy, see `scripts/vendor_weave_server_sdk.py`.
