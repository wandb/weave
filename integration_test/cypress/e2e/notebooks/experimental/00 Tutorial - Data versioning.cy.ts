import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/00 Tutorial - Data versioning.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/00 Tutorial - Data versioning.ipynb')
    );
});