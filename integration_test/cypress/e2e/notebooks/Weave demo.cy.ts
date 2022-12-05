import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Weave demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Weave demo.ipynb')
    );
});