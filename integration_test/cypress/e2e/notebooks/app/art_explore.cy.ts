import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/art_explore.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/art_explore.ipynb')
    );
});