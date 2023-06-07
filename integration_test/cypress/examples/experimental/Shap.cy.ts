import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/experimental/Shap.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Shap.ipynb')
    );
});