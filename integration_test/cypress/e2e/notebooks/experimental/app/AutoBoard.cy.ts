import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/AutoBoard.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/AutoBoard.ipynb')
    );
});