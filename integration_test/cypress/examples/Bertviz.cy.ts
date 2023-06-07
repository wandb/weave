import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Bertviz.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Bertviz.ipynb')
    );
});