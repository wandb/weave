import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/layout_panels.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/layout_panels.ipynb')
    );
});