import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/skip_test/Diffusion explore 2.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/skip_test/Diffusion explore 2.ipynb')
    );
});