import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Composable Python panels.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Composable Python panels.ipynb')
    );
});