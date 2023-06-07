import {checkWeaveNotebookOutputs} from '../../e2e/notebooks/notebooks';

describe('../examples/app/Diffusion explore 2.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Diffusion explore 2.ipynb')
    );
});