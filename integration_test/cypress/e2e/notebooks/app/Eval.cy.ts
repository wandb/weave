import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Eval.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Eval.ipynb')
    );
});