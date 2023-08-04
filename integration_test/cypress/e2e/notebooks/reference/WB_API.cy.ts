import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/WB_API.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/WB_API.ipynb')
    );
});