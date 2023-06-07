import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/Hack demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/Hack demo.ipynb')
    );
});