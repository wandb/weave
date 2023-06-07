import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Performance profiling.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Performance profiling.ipynb')
    );
});