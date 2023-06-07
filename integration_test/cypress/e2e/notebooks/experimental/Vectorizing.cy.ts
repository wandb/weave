import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Vectorizing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Vectorizing.ipynb')
    );
});