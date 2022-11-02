import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/WB_API.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/WB_API.ipynb')
    );
});