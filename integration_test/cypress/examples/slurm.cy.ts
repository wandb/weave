import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/slurm.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/slurm.ipynb')
    );
});