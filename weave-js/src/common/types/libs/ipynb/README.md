As of this writing (2022/09/26), our Jupyter renderer component (JupyterViewer) only supports V4 ipynb files. However, there are occasional minor and major updates which caused our hard-coded typing to be out of date. This directory is
intended to help mitigate these issues. The official format docs are here: https://nbformat.readthedocs.io/en/latest/format_description.html which fully describes this versioning.

Furthermore, the highest minor-version of any major version is located at `https://github.com/jupyter/nbformat/blob/main/nbformat/v[VERSION_NUMBER]/nbformat.[VERSION_NUMBER].schema.json`.

So, there are two cases which you may need to update the spec:
1. In the case that there is a new minor version of the spec, we should replace the existing spec in `./schemas`
2. In the case that there is a new major version of the spec, we should add a new spec to `./schemas`

In both cases, you will want to run `yarn generate:ipynb` from the `common` package to generate new TS types in `./types_gen`. These outputs are exported via `./index.ts` and therefore can be imported similar to `import * as NBTypes from './types_gen/libs/ipynb'`. This pattern will allow us to add new schemas as jupyter develops and strictly enforce correct typing in the client components.