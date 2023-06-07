import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/slurm.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/slurm.ipynb')
    );
});