# Vendored packages

## `weave-server-sdk`

The generated TypeScript client for the Weave Trace API. It is generated from
the trace server's OpenAPI spec and Stainless config, both of which live in
`wandb/core` under `services/weave-trace`, and it is vendored here rather than
depended on because it is not published to npm.

Treat the copy as read-only. It is replaced wholesale on every refresh, so a
hand edit is lost the next time somebody regenerates.

`weave-server-sdk.origin.json` records the core revision and the hashes of the
spec and the config the output was generated from, so a refresh diff can be
checked against them. The hashes are of the generator inputs, not of this
tree: equal hashes do not prove this copy came from that build. Generate from
the same checkout you then pass as `--core`.

To refresh the copy:

```
make -C core/services/weave-trace/tools/codegen build \
    SDK_TARGETS=typescript SDK_OUTPUT=/tmp/weave-sdk

python scripts/vendor_node_weave_server_sdk.py \
    --sdk-output /tmp/weave-sdk --core ../core
```
