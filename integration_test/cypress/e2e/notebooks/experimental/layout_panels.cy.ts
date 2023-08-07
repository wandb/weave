import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/layout_panels.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/layout_panels.ipynb')
    );
});