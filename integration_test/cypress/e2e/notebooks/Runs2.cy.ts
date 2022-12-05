import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Runs2.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Runs2.ipynb')
    );
});