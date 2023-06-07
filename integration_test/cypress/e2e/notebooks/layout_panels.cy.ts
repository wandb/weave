import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/layout_panels.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/layout_panels.ipynb')
    );
});