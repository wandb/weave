import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Table Summary Panel.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Table Summary Panel.ipynb')
    );
});