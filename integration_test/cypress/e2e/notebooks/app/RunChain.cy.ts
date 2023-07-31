import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/RunChain.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/RunChain.ipynb')
    );
});