import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/AutoBoard.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/AutoBoard.ipynb')
    );
});