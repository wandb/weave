import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Weave geo data.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Weave geo data.ipynb')
    );
});