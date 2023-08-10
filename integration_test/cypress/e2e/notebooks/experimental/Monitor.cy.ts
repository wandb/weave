import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Monitor.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Monitor.ipynb')
    );
});