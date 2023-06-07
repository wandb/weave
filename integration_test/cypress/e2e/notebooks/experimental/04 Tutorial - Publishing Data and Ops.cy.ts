import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/04 Tutorial - Publishing Data and Ops.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/04 Tutorial - Publishing Data and Ops.ipynb')
    );
});