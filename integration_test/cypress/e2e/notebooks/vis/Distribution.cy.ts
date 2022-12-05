import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/vis/Distribution.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/vis/Distribution.ipynb')
    );
});