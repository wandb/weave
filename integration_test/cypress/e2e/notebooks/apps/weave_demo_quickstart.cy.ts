import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/apps/weave_demo_quickstart.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/apps/weave_demo_quickstart.ipynb')
    );
});