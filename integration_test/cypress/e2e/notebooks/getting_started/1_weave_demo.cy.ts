import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/getting_started/1_weave_demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/getting_started/1_weave_demo.ipynb')
    );
});