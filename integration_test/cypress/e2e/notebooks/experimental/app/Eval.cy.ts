import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/Eval.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/Eval.ipynb')
    );
});