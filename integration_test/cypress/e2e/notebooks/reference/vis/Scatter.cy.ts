import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/vis/Scatter.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/vis/Scatter.ipynb')
    );
});