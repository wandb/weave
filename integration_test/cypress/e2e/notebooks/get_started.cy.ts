import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/get_started.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/get_started.ipynb')
    );
});