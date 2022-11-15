import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/Scatter.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Scatter.ipynb')
    );
});