import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/AutoBoard.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/AutoBoard.ipynb')
    );
});