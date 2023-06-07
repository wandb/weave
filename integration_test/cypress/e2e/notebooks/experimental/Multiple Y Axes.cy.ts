import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Multiple Y Axes.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Multiple Y Axes.ipynb')
    );
});