import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Monitor2.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Monitor2.ipynb')
    );
});