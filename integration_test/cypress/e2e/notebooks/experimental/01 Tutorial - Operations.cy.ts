import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/01 Tutorial - Operations.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/01 Tutorial - Operations.ipynb')
    );
});