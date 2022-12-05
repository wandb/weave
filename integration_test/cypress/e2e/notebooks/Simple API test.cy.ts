import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Simple API test.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Simple API test.ipynb')
    );
});