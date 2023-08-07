import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/vis/Distribution.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/vis/Distribution.ipynb')
    );
});