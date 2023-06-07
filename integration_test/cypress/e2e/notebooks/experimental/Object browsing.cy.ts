import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Object browsing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Object browsing.ipynb')
    );
});