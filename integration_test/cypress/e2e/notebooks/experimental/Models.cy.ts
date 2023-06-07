import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Models.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Models.ipynb')
    );
});