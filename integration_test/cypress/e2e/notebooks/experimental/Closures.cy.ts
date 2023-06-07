import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Closures.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Closures.ipynb')
    );
});