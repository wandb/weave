import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/object_version_compare.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/object_version_compare.ipynb')
    );
});