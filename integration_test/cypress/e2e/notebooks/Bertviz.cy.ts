import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/bertviz.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/bertviz.ipynb')
    );
});