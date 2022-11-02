import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Table Summary Panel.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Table Summary Panel.ipynb')
    );
});