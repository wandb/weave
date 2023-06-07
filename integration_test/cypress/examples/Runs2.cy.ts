import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Runs2.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Runs2.ipynb')
    );
});