import {checkWeaveNotebookOutputs} from '../e2e/notebooks/notebooks';

describe('../examples/Simple API test.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Simple API test.ipynb')
    );
});