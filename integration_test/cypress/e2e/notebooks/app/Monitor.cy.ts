import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Monitor.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Monitor.ipynb')
    );
});