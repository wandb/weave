import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/vis/Confusion.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/vis/Confusion.ipynb')
    );
});