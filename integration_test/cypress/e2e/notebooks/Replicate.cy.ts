import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/replicate.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/replicate.ipynb')
    );
});