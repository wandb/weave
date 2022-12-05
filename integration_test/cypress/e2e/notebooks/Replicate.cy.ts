import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Replicate.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Replicate.ipynb')
    );
});