import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Table Data Passing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Table Data Passing.ipynb')
    );
});