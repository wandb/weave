import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/art_explore.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/app/art_explore.ipynb')
    );
});