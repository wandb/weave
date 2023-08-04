import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/getting_started/0_weave_demo_quickstart.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/getting_started/0_weave_demo_quickstart.ipynb')
    );
});