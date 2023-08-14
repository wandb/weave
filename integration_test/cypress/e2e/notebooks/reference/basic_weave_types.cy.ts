import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/basic_weave_types.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/basic_weave_types.ipynb')
    );
});