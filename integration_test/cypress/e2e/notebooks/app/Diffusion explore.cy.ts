import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Diffusion explore.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Diffusion explore.ipynb')
    );
});