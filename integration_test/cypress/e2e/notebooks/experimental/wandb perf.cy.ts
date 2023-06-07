import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/wandb perf.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/wandb perf.ipynb')
    );
});