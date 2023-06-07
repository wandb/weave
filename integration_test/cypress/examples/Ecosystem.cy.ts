import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Ecosystem.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Ecosystem.ipynb')
    );
});